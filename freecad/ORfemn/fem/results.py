"""
Load an OpenRadioss result frame (.vtu written by radioss_runner) as a FEM
mechanical result object, like the CalculiX solver does.

FreeCAD 1.0 cannot colour a FemPostPipeline that was read directly from such
a file (its field list stays empty), so the result goes through
Fem::ResultMechanical: node displacements by NODE_ID, element stress tensors
averaged to the nodes, von Mises / principal stresses and statistics computed
by FreeCAD's resulttools, and a post-processing pipeline built from it.
"""

import threading
import xml.etree.ElementTree as ET

import FreeCAD

# vtk cell type -> number of nodes, element kind
_VTK_CELLS = {3: (2, "edge"), 5: (3, "face"), 9: (4, "face"), 10: (4, "volume"),
              12: (8, "volume"), 13: (6, "volume"), 14: (5, "volume"), 24: (10, "volume")}


def read_vtu(path):
    """Arrays of an ASCII .vtu as {name: (components, [floats])} plus points, cells and types."""
    root = ET.parse(path).getroot()
    arrays = {}
    for array in root.iter("DataArray"):
        values = (array.text or "").split()
        arrays[array.get("Name")] = (int(array.get("NumberOfComponents") or 1), values)
    connectivity = [int(v) for v in arrays["connectivity"][1]]
    offsets = [int(v) for v in arrays["offsets"][1]]
    cells, start = [], 0
    for end in offsets:
        cells.append(connectivity[start:end])
        start = end
    return {
        "arrays": arrays,
        "points": [float(v) for v in arrays["Points"][1]],
        "cells": cells,
        "types": [int(v) for v in arrays["types"][1]],
    }


def _tuples(array, size):
    values = [float(v) for v in array[1]]
    return [values[i:i + size] for i in range(0, len(values), size)]


def _tensor_to_voigt(t):
    """3x3 row-major tensor -> (xx, yy, zz, xy, xz, yz)."""
    return (t[0], t[4], t[8], t[1], t[2], t[5])


def _von_mises(s):
    xx, yy, zz, xy, xz, yz = s
    return (0.5 * ((xx - yy) ** 2 + (yy - zz) ** 2 + (zz - xx) ** 2) + 3 * (xy ** 2 + xz ** 2 + yz ** 2)) ** 0.5


def element_stresses(data):
    """{element id: (xx, yy, zz, xy, xz, yz)} from solid or shell stress tensors."""
    arrays = data["arrays"]
    ids = [int(float(v)) for v in arrays["ELEMENT_ID"][1]] if "ELEMENT_ID" in arrays else []
    stresses = {}
    if "3DELEM_Stress" in arrays:
        for eid, t in zip(ids, _tuples(arrays["3DELEM_Stress"], 9)):
            stresses[eid] = _tensor_to_voigt(t)
    for upper_name, lower_name in (("2DELEM_Stress_(upper)", "2DELEM_Stress_(lower)"),):
        if upper_name in arrays:
            upper = [_tensor_to_voigt(t) for t in _tuples(arrays[upper_name], 9)]
            lower = ([_tensor_to_voigt(t) for t in _tuples(arrays[lower_name], 9)]
                     if lower_name in arrays else upper)
            for eid, u, low in zip(ids, upper, lower):
                if eid not in stresses:  # shells: the more stressed surface
                    stresses[eid] = u if _von_mises(u) >= _von_mises(low) else low
    return stresses


def femmesh_from_vtu(data, node_ids, displacement):
    """A FemMesh in the undeformed configuration from the result's own geometry."""
    import Fem
    mesh = Fem.FemMesh()
    points = data["points"]
    for i, nid in enumerate(node_ids):
        d = displacement.get(nid, (0.0, 0.0, 0.0))
        mesh.addNode(points[3 * i] - d[0], points[3 * i + 1] - d[1], points[3 * i + 2] - d[2], nid)
    element_ids = [int(float(v)) for v in data["arrays"]["ELEMENT_ID"][1]]
    for eid, cell, vtk_type in zip(element_ids, data["cells"], data["types"]):
        n, kind = _VTK_CELLS.get(vtk_type, (0, None))
        nodes = [node_ids[i] for i in cell[:n]]
        if kind == "volume":
            mesh.addVolume(nodes, eid)
        elif kind == "face":
            mesh.addFace(nodes, eid)
        elif kind == "edge":
            mesh.addEdge(nodes, eid)
    return mesh


def _post_vtk_result_data(res):
    """Argument for ObjectsFem.makePostVtkResult: FreeCAD 1.0 takes the result object,
    1.1 a list that it expands (``[result]`` or a multi-step ``[results, values, unit, description]``)."""
    major, minor = (int(v) for v in FreeCAD.Version()[:2])
    return [res] if (major, minor) >= (1, 1) else res


def load_result(doc, vtu_path, name="OpenRadiossResult", analysis=None, femmesh=None, time=None):
    """Create a Fem::ResultMechanical (+ result mesh and pipeline) from ``vtu_path``.

    ``femmesh`` is the analysis mesh (node and element ids match the deck);
    without it the mesh is rebuilt from the result file. Returns (result, pipeline).
    """
    import ObjectsFem
    from femresult import resulttools

    data = read_vtu(vtu_path)
    arrays = data["arrays"]
    node_ids = [int(float(v)) for v in arrays["NODE_ID"][1]]
    displacement = dict(zip(node_ids, _tuples(arrays["Displacement"], 3))) if "Displacement" in arrays else {}
    stresses = element_stresses(data)

    if femmesh is None:
        femmesh = femmesh_from_vtu(data, node_ids, displacement)
    elements = {eid: list(femmesh.getElementNodes(eid))
                for eid in (femmesh.Volumes if femmesh.VolumeCount else femmesh.Faces)}

    # nodes missing from the result (midside nodes of reduced second-order elements):
    # take the mean of the nodes of their element that have values
    for nodes in elements.values():
        known = [displacement[n] for n in nodes if n in displacement]
        for n in nodes:
            if n not in displacement and known:
                displacement[n] = [sum(d[k] for d in known) / len(known) for k in range(3)]

    node_stress, count = {}, {}
    for eid, nodes in elements.items():
        s = stresses.get(eid)
        if s is None:
            continue
        for n in nodes:
            acc = node_stress.setdefault(n, [0.0] * 6)
            for k in range(6):
                acc[k] += s[k]
            count[n] = count.get(n, 0) + 1
    node_numbers = sorted(femmesh.Nodes)

    res = ObjectsFem.makeResultMechanical(doc, name)
    mesh_obj = ObjectsFem.makeMeshResult(doc, name + "_Mesh")
    mesh_obj.FemMesh = femmesh
    res.Mesh = mesh_obj
    res.NodeNumbers = node_numbers
    res.DisplacementVectors = [FreeCAD.Vector(*displacement.get(n, (0.0, 0.0, 0.0))) for n in node_numbers]
    components = ("NodeStressXX", "NodeStressYY", "NodeStressZZ", "NodeStressXY", "NodeStressXZ", "NodeStressYZ")
    for k, prop in enumerate(components):
        setattr(res, prop, [node_stress[n][k] / count[n] if n in count else 0.0 for n in node_numbers])
    if time is not None and hasattr(res, "Time"):
        res.Time = time
    if analysis is not None:
        analysis.addObject(res)
        analysis.addObject(mesh_obj)
    res = resulttools.add_disp_apps(res)
    res = resulttools.add_von_mises(res)
    res = resulttools.add_principal_stress_std(res)
    res = resulttools.fill_femresult_stats(res)

    pipeline = ObjectsFem.makePostVtkResult(doc, _post_vtk_result_data(res), name)
    if analysis is not None:
        analysis.addObject(pipeline)
    pipeline.recomputeChildren()
    pipeline.recompute()
    mesh_obj.Visibility = False
    # The FEM solver framework runs the Results task in a worker thread; view objects
    # (Qt) must only be touched from the main thread.
    if FreeCAD.GuiUp and threading.current_thread() is threading.main_thread():
        pipeline.ViewObject.updateColorBars()
    doc.recompute()
    return res, pipeline
