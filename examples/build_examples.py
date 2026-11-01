# SPDX-License-Identifier: LGPL-2.1-or-later
"""Build the example documents of the OpenRadioss workbench.

Run from the repository root with FreeCAD's command line:

    freecadcmd examples/build_examples.py

It (re)creates in examples/:

  cantilever_beam.FCStd        FEM workbench, hexahedra, quasi-static ramp load
  plate_sudden_pressure.FCStd  FEM workbench, shells, pressure applied suddenly
  taylor_impact.FCStd          keyword deck: a plastic bar hits a rigid wall

The meshes are generated here (structured, no mesher needed) so the examples
are identical on every machine. Units: mm, t, s, N, MPa.
"""

import os

import FreeCAD as App

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

try:
    import freecad.ORfemn  # noqa: F401  (installed in FreeCAD's Mod directory)
except ImportError:
    import freecad
    freecad.__path__.append(os.path.join(ROOT, "freecad"))

import Fem
import ObjectsFem
import Part

from freecad.ORfemn.fem import solver as radioss_solver

STEEL = {"Name": "Steel", "YoungsModulus": "210000 MPa", "PoissonRatio": "0.3", "Density": "7900 kg/m^3"}


def structured_hexa_mesh(lx, ly, lz, nx, ny, nz):
    """A FemMesh of nx*ny*nz hexahedra filling the box [0,lx]x[0,ly]x[0,lz]."""
    mesh = Fem.FemMesh()
    nid = {}
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                n = len(nid) + 1
                nid[i, j, k] = n
                mesh.addNode(lx * i / nx, ly * j / ny, lz * k / nz, n)
    eid = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                eid += 1
                mesh.addVolume([nid[i, j, k], nid[i + 1, j, k], nid[i + 1, j + 1, k], nid[i, j + 1, k],
                                nid[i, j, k + 1], nid[i + 1, j, k + 1], nid[i + 1, j + 1, k + 1],
                                nid[i, j + 1, k + 1]], eid)
    return mesh


def structured_quad_mesh(lx, ly, nx, ny):
    """A FemMesh of nx*ny quadrilaterals on the rectangle [0,lx]x[0,ly] at z = 0."""
    mesh = Fem.FemMesh()
    nid = {}
    for j in range(ny + 1):
        for i in range(nx + 1):
            n = len(nid) + 1
            nid[i, j] = n
            mesh.addNode(lx * i / nx, ly * j / ny, 0.0, n)
    eid = 0
    for j in range(ny):
        for i in range(nx):
            eid += 1
            mesh.addFace([nid[i, j], nid[i + 1, j], nid[i + 1, j + 1], nid[i, j + 1]], eid)
    return mesh


def sub_element(shape, kind, predicate):
    """Name ("Face3", "Edge1", ...) of the first face/edge of ``shape`` matching ``predicate``."""
    for i, element in enumerate(getattr(shape, kind + "s")):
        if predicate(element):
            return f"{kind}{i + 1}"
    raise RuntimeError(f"no {kind} found")


def add_material(doc, analysis, values):
    mat = ObjectsFem.makeMaterialSolid(doc, values["Name"])
    m = mat.Material
    m.update(values)
    mat.Material = m
    analysis.addObject(mat)
    return mat


def add_mesh(doc, analysis, femmesh, label):
    mesh = doc.addObject("Fem::FemMeshObject", "Mesh")
    mesh.Label = label
    mesh.FemMesh = femmesh
    analysis.addObject(mesh)
    return mesh


def add_solver(doc, analysis, **props):
    solver = radioss_solver.create(doc)
    for name, value in props.items():
        setattr(solver, name, value)
    analysis.addObject(solver)
    return solver


def finish(doc, name, hide=()):
    doc.recompute()
    if App.GuiUp:
        for obj in hide:
            obj.ViewObject.Visibility = False
    path = os.path.join(HERE, name + ".FCStd")
    doc.saveAs(path)
    App.closeDocument(doc.Name)
    print(f"written {path}")
    return path


def cantilever_beam():
    """Steel cantilever 100 x 10 x 10 mm, fixed at x = 0, 100 N downwards at the free end.

    Beam theory (incl. shear): tip deflection 0.192 mm. Ramp load over 10 ms, about eight periods
    of the first bending mode (833 Hz), so the response is quasi-static.
    """
    doc = App.newDocument("cantilever_beam")
    beam = doc.addObject("Part::Box", "Beam")
    beam.Length, beam.Width, beam.Height = 100, 10, 10
    doc.recompute()

    analysis = ObjectsFem.makeAnalysis(doc, "Analysis")
    add_material(doc, analysis, STEEL)
    fixed = ObjectsFem.makeConstraintFixed(doc, "Fixed")
    fixed.References = [(beam, sub_element(beam.Shape, "Face", lambda f: abs(f.CenterOfMass.x) < 1e-9))]
    analysis.addObject(fixed)
    force = ObjectsFem.makeConstraintForce(doc, "TipForce")
    force.References = [(beam, sub_element(beam.Shape, "Face", lambda f: abs(f.CenterOfMass.x - 100) < 1e-9))]
    force.Force = "100 N"
    force.Direction = (beam, [sub_element(beam.Shape, "Edge", lambda e: abs(e.tangentAt(0).z) > 0.99)])
    force.Reversed = force.DirectionVector.z > 0  # point downwards (-z)
    analysis.addObject(force)
    add_mesh(doc, analysis, structured_hexa_mesh(100, 10, 10, 20, 2, 2), "Mesh (40 hexahedra)")
    add_solver(doc, analysis, EndTime="0.01 s", LoadCurve="Ramp", OutputFrames=20)
    return finish(doc, "cantilever_beam", hide=[beam])


def plate_sudden_pressure():
    """Square steel plate 200 x 200 x 2 mm, clamped edges, 0.01 MPa applied suddenly.

    Plate theory: static centre deflection 0.00126 q a^4 / D = 0.131 mm; a load applied suddenly
    makes the plate oscillate around it with peaks of about twice that (no damping).
    First mode about 450 Hz, so 10 ms show about four oscillations.
    """
    doc = App.newDocument("plate_sudden_pressure")
    plate = doc.addObject("Part::Plane", "Plate")
    plate.Length, plate.Width = 200, 200
    doc.recompute()

    analysis = ObjectsFem.makeAnalysis(doc, "Analysis")
    add_material(doc, analysis, STEEL)
    thickness = ObjectsFem.makeElementGeometry2D(doc, 2.0, "Thickness")
    analysis.addObject(thickness)
    fixed = ObjectsFem.makeConstraintFixed(doc, "ClampedEdges")
    fixed.References = [(plate, [f"Edge{i + 1}" for i in range(len(plate.Shape.Edges))])]
    analysis.addObject(fixed)
    pressure = ObjectsFem.makeConstraintPressure(doc, "Pressure")
    pressure.References = [(plate, "Face1")]
    pressure.Pressure = "0.01 MPa"
    analysis.addObject(pressure)
    add_mesh(doc, analysis, structured_quad_mesh(200, 200, 20, 20), "Mesh (400 shells)")
    add_solver(doc, analysis, EndTime="0.01 s", LoadCurve="Constant", OutputFrames=50)
    return finish(doc, "plate_sudden_pressure", hide=[plate])


def taylor_deck(a=10.0, length=40.0, n_side=4, n_length=16, velocity=2.0e5):
    """LS-DYNA deck: a steel bar a x a x length mm (hexahedra) hits a rigid wall at z = 0."""
    lines = ["*KEYWORD", "*TITLE", "Taylor impact: steel bar hits a rigid wall at 200 m/s",
             "$ units: mm, t, s, N, MPa",
             "*CONTROL_TERMINATION", "$   endtim", "6.0e-5",
             "*CONTROL_TIMESTEP", "$   dtinit    tssfac", "0.0, 0.9",
             "*DATABASE_BINARY_D3PLOT", "$       dt", "2.0e-6",
             "*PART", "Bar", "$      pid     secid       mid", "1, 1, 1",
             "*SECTION_SOLID", "$    secid    elform", "1, 1",
             "*MAT_PLASTIC_KINEMATIC",
             "$      mid        ro         e        pr      sigy      etan",
             "1, 7.85e-9, 210000.0, 0.3, 400.0, 1000.0",
             "*NODE"]
    nid = {}
    for k in range(n_length + 1):
        for j in range(n_side + 1):
            for i in range(n_side + 1):
                n = len(nid) + 1
                nid[i, j, k] = n
                x, y, z = a * i / n_side - a / 2, a * j / n_side - a / 2, 0.01 + length * k / n_length
                lines.append(f"{n:8d}{x:16.6f}{y:16.6f}{z:16.6f}")
    lines.append("*ELEMENT_SOLID")
    eid = 0
    for k in range(n_length):
        for j in range(n_side):
            for i in range(n_side):
                eid += 1
                corners = [nid[i, j, k], nid[i + 1, j, k], nid[i + 1, j + 1, k], nid[i, j + 1, k],
                           nid[i, j, k + 1], nid[i + 1, j, k + 1], nid[i + 1, j + 1, k + 1], nid[i, j + 1, k + 1]]
                lines.append("".join(f"{v:8d}" for v in [eid, 1] + corners))
    lines += ["*SET_NODE_LIST", "$      sid", "1"]
    ids = list(nid.values())
    for start in range(0, len(ids), 8):
        lines.append("".join(f"{v:10d}" for v in ids[start:start + 8]))
    lines += ["*INITIAL_VELOCITY", "$     nsid", "1", "$       vx        vy        vz", f"0.0, 0.0, {-velocity}",
              "*RIGIDWALL_PLANAR", "$     nsid", "0", "$       xt        yt        zt        xh        yh        zh",
              "0.0, 0.0, 0.0, 0.0, 0.0, 1.0",
              "*END"]
    return "\n".join(lines) + "\n"


def taylor_impact():
    """Keyword-deck example: run it with the 'Run OpenRadioss' command of the OpenRadioss workbench."""
    doc = App.newDocument("taylor_impact")
    deck = doc.addObject("App::TextDocument", "TaylorImpact")
    deck.Label = "Taylor impact deck"
    deck.Text = taylor_deck()
    return finish(doc, "taylor_impact")


cantilever_beam()
plate_sudden_pressure()
taylor_impact()
