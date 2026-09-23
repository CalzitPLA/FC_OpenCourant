"""
Run OpenRadioss on an LS-DYNA format (.k) deck.

For a .k deck OpenRadioss works in three steps:

1. starter  ``-i job.k``         checks the deck, writes job_0000.out, the
                                 restart file and the engine input job_0001.rad
2. engine   ``-i job_0001.rad``  runs the simulation, writes job_0001.out and
                                 animation files jobA001, jobA002, ...
3. anim_to_vtk ``jobA001``       converts each animation file to legacy VTK (stdout)

The legacy files are then converted to XML .vtu (``legacy_vtk_to_vtu``),
because VTK's legacy reader - and so FreeCAD's FEM post-processing - only
reads the first vector/scalar/tensor array of a file (e.g. Velocity but not
Displacement). A .pvd file lists all frames with their time for ParaView.

This module has no FreeCAD or Qt imports: it builds the commands and the
environment, and ``run_job`` runs everything synchronously (used by the tests
and for scripting). The FreeCAD dialog runs the same commands with QProcess.
"""

import math
import os
import platform
import re
import shutil
import subprocess
from xml.sax.saxutils import quoteattr

DEFAULT_INSTALL = os.path.join(os.path.expanduser("~"), "OpenRadioss")

# Libraries the OpenRadioss binaries need that the FreeCAD Flatpak runtime lacks.
# They are copied from the host (visible at /run/host inside the sandbox).
FLATPAK_MISSING_LIBS = ("libcrypt.so.1", "libapr-1.so.0")
FLATPAK_HOST_LIB_DIR = "/run/host/usr/lib/x86_64-linux-gnu"

ERRORS = re.compile(r"^\s*(\d+)\s+ERROR\(S\)", re.MULTILINE)
WARNINGS = re.compile(r"^\s*(\d+)\s+WARNING\(S\)", re.MULTILINE)


class OpenRadiossError(Exception):
    """Raised when the installation is unusable or a step fails."""


def in_flatpak():
    return os.path.exists("/.flatpak-info")


class Installation:
    """An OpenRadioss installation (the unpacked release directory)."""

    def __init__(self, path=DEFAULT_INSTALL):
        self.path = os.path.abspath(os.path.expanduser(path))
        system, machine = platform.system(), platform.machine().lower()
        if system == "Windows":
            self.arch, self.ext, self.libdir = "win64", ".exe", "win64"
        elif machine in ("aarch64", "arm64"):
            self.arch, self.ext, self.libdir = "linuxa64", "", "linuxa64"
        else:
            self.arch, self.ext, self.libdir = "linux64_gf", "", "linux64"

    def executable(self, tool, single_precision=False):
        name = f"{tool}_{self.arch}{'_sp' if single_precision else ''}{self.ext}"
        return os.path.join(self.path, "exec", name)

    def problems(self):
        """Human readable reasons why this installation cannot be used (empty if fine)."""
        if not os.path.isdir(self.path):
            return [f"OpenRadioss not found at {self.path}"]
        missing = [os.path.basename(self.executable(t)) for t in ("starter", "engine", "anim_to_vtk")
                   if not os.path.isfile(self.executable(t))]
        return [f"Missing in {os.path.join(self.path, 'exec')}: {', '.join(missing)}"] if missing else []

    @property
    def flatpak_compat_dir(self):
        return os.path.join(self.path, "extlib", "flatpak_compat")

    def prepare_flatpak(self):
        """Inside the FreeCAD Flatpak, copy the host libraries the solver needs. Returns copied names."""
        if not in_flatpak() or self.arch != "linux64_gf":
            return []
        os.makedirs(self.flatpak_compat_dir, exist_ok=True)
        copied = []
        for lib in FLATPAK_MISSING_LIBS:
            target = os.path.join(self.flatpak_compat_dir, lib)
            source = os.path.join(FLATPAK_HOST_LIB_DIR, lib)
            if not os.path.exists(target) and os.path.exists(source):
                shutil.copy2(os.path.realpath(source), target)
                copied.append(lib)
        return copied

    def environment(self, threads=1, base=None):
        """Environment variables for starter, engine and anim_to_vtk (as the OpenRadioss GUI sets them)."""
        env = dict(os.environ if base is None else base)
        h3d = os.path.join(self.path, "extlib", "h3d", "lib", self.libdir)
        hm_reader = os.path.join(self.path, "extlib", "hm_reader", self.libdir)
        paths = [h3d, hm_reader]
        if in_flatpak():
            paths.append(self.flatpak_compat_dir)
        env.update({
            "OPENRADIOSS_PATH": self.path,
            "RAD_CFG_PATH": os.path.join(self.path, "hm_cfg_files"),
            "RAD_H3D_PATH": h3d,
            "OMP_STACKSIZE": "400m",
            "KMP_STACKSIZE": "400m",
            "OMP_NUM_THREADS": str(threads),
        })
        key = "PATH" if self.ext == ".exe" else "LD_LIBRARY_PATH"
        env[key] = os.pathsep.join(paths + ([env[key]] if env.get(key) else []))
        return env

    # --- commands ------------------------------------------------------

    def starter_command(self, deck, threads=1):
        return [self.executable("starter"), "-i", os.path.basename(deck), "-nt", str(threads), "-np", "1"]

    def engine_command(self, engine_input, threads=1):
        return [self.executable("engine"), "-i", os.path.basename(engine_input), "-nt", str(threads)]

    def anim_to_vtk_command(self, animation_file):
        return [self.executable("anim_to_vtk"), os.path.basename(animation_file)]


def job_name(deck):
    return os.path.splitext(os.path.basename(deck))[0]


def engine_inputs(workdir, jobname):
    """Engine input files written by the starter: job_0001.rad, job_0002.rad, ..."""
    pattern = re.compile(re.escape(jobname) + r"_(\d{4})\.rad$")
    files = [f for f in os.listdir(workdir) if pattern.match(f) and pattern.match(f).group(1) != "0000"]
    return [os.path.join(workdir, f) for f in sorted(files)]


def animation_files(workdir, jobname):
    """Animation files written by the engine: jobA001, jobA002, ..."""
    pattern = re.compile(re.escape(jobname) + r"A(\d{3,4})$")
    return [os.path.join(workdir, f) for f in sorted(os.listdir(workdir)) if pattern.match(f)]


def is_result_file(filename, jobname):
    """True for files OpenRadioss (or the conversion) writes for ``jobname``: listings, restarts, animations, VTK."""
    return re.match(re.escape(jobname) + r"(_\d{4}(_\d{4})?\.(out|rad|rst|sty)|A\d{3,4}(\.vtk|\.vtu)?|T\d{2}|\.pvd)$",
                    filename) is not None


def listing_summary(out_file):
    """(errors, warnings) reported at the end of a .out listing file, or (None, None)."""
    try:
        with open(out_file, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return None, None
    errors, warnings = ERRORS.findall(text), WARNINGS.findall(text)
    if not errors and "STOP DUE TO INPUT ERROR" in text:
        # The starter stopped early: there is no summary line, count the error blocks instead
        errors = [str(len(re.findall(r"^ERROR ID\s*:", text, re.MULTILINE)) or 1)]
    return (int(errors[-1]) if errors else None, int(warnings[-1]) if warnings else None)


def listing_messages(out_file, kind="ERROR", limit=3):
    """The first ``limit`` ERROR (or WARNING) blocks of a listing file as short texts."""
    try:
        with open(out_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    messages = []
    for i, line in enumerate(lines):
        if line.startswith(f"{kind} ID"):
            block = []
            for follow in lines[i:i + 12]:
                if block and (not follow.strip() or follow.startswith(("ERROR ID", "WARNING ID"))):
                    break
                block.append(follow.strip())
            # an early stop names the entity type (e.g. NODES) in the box just above the error
            above = lines[max(0, i - 4):i]
            context = next((l.strip() for l in reversed(above) if l.strip() and "===" not in l), "") \
                if any("===" in l for l in above) else ""
            text = " ".join(b for b in block if b and not b.startswith("---"))
            messages.append(f"{text} [{context}]" if context and context not in text else text)
            if len(messages) >= limit:
                break
    return messages


def normal_termination(out_file):
    try:
        with open(out_file, "r", encoding="utf-8", errors="replace") as f:
            return "NORMAL TERMINATION" in f.read()
    except OSError:
        return False


# --- VTK conversion -----------------------------------------------------------

_VTK_TYPES = {"float": "Float32", "double": "Float64", "int": "Int32", "long": "Int64",
              "unsigned_char": "UInt8", "char": "Int8", "short": "Int16", "vtkIdType": "Int64"}


def _von_mises(t):
    """Von Mises stress of a 3x3 tensor given row-major as 9 values."""
    xx, xy, xz, _yx, yy, yz, _zx, _zy, zz = t
    return math.sqrt(0.5 * ((xx - yy) ** 2 + (yy - zz) ** 2 + (zz - xx) ** 2) + 3.0 * (xy ** 2 + yz ** 2 + xz ** 2))


def read_legacy_vtk(path):
    """Parse an ASCII legacy VTK unstructured grid as written by anim_to_vtk.

    Returns a dict with ``field`` ({name: values}), ``points`` (flat list),
    ``cells`` (list of node index lists), ``cell_types`` and ``point_data`` /
    ``cell_data`` (lists of (name, vtk type, components, values)).
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    tokens = " ".join(lines[4:]).split()  # skip the 4 header lines
    pos = 0

    def take(n):
        nonlocal pos
        values = tokens[pos:pos + n]
        pos += n
        return values

    data = {"field": {}, "points": [], "cells": [], "cell_types": [], "point_data": [], "cell_data": []}
    section, count = None, 0
    while pos < len(tokens):
        word = tokens[pos]
        pos += 1
        if word == "FIELD":
            _name, n_arrays = take(2)
            for _ in range(int(n_arrays)):
                name, comps, tuples, _type = take(4)
                data["field"][name] = take(int(comps) * int(tuples))
        elif word == "POINTS":
            n, _type = take(2)
            data["points"] = take(3 * int(n))
        elif word == "CELLS":
            n, _size = take(2)
            for _ in range(int(n)):
                k = int(take(1)[0])
                data["cells"].append(take(k))
        elif word == "CELL_TYPES":
            data["cell_types"] = take(int(take(1)[0]))
        elif word in ("POINT_DATA", "CELL_DATA"):
            section, count = ("point_data" if word == "POINT_DATA" else "cell_data"), int(take(1)[0])
        elif word == "SCALARS":
            name, vtk_type = take(2)
            comps = 1
            if tokens[pos] != "LOOKUP_TABLE":
                comps = int(take(1)[0])
            take(2)  # LOOKUP_TABLE default
            data[section].append((name, vtk_type, comps, take(comps * count)))
        elif word in ("VECTORS", "NORMALS"):
            name, vtk_type = take(2)
            data[section].append((name, vtk_type, 3, take(3 * count)))
        elif word == "TENSORS":
            name, vtk_type = take(2)
            values = take(9 * count)
            data[section].append((name, vtk_type, 9, values))
            floats = [float(v) for v in values]
            von_mises = [_von_mises(floats[i:i + 9]) for i in range(0, len(floats), 9)]
            data[section].append((f"{name} von Mises", "float", 1, [f"{v:.6g}" for v in von_mises]))
        else:
            raise ValueError(f"{path}: unexpected token {word!r}")
    return data


def legacy_vtk_to_vtu(source, target):
    """Convert an anim_to_vtk legacy file to XML .vtu keeping all arrays. Returns the frame time or None."""
    data = read_legacy_vtk(source)

    def array(name, vtk_type, comps, values):
        return (f'<DataArray type="{_VTK_TYPES.get(vtk_type, "Float32")}" Name={quoteattr(name)} '
                f'NumberOfComponents="{comps}" format="ascii">{" ".join(values)}</DataArray>')

    offsets, total = [], 0
    for cell in data["cells"]:
        total += len(cell)
        offsets.append(str(total))
    parts = ['<?xml version="1.0"?>',
             '<VTKFile type="UnstructuredGrid" version="0.1" byte_order="LittleEndian">',
             "<UnstructuredGrid>"]
    if data["field"]:
        parts.append("<FieldData>" + "".join(
            f'<DataArray type="Float64" Name={quoteattr(n)} NumberOfTuples="{len(v)}" format="ascii">{" ".join(v)}</DataArray>'
            for n, v in data["field"].items()) + "</FieldData>")
    parts.append(f'<Piece NumberOfPoints="{len(data["points"]) // 3}" NumberOfCells="{len(data["cells"])}">')
    for tag, key in (("PointData", "point_data"), ("CellData", "cell_data")):
        parts.append(f"<{tag}>" + "".join(array(*a) for a in data[key]) + f"</{tag}>")
    parts.append(f'<Points>{array("Points", "float", 3, data["points"])}</Points>')
    parts.append("<Cells>"
                 f'<DataArray type="Int64" Name="connectivity" format="ascii">{" ".join(" ".join(c) for c in data["cells"])}</DataArray>'
                 f'<DataArray type="Int64" Name="offsets" format="ascii">{" ".join(offsets)}</DataArray>'
                 f'<DataArray type="UInt8" Name="types" format="ascii">{" ".join(data["cell_types"])}</DataArray>'
                 "</Cells>")
    parts.append("</Piece></UnstructuredGrid></VTKFile>")
    with open(target, "w", encoding="utf-8") as f:
        f.write("\n".join(parts) + "\n")
    time = data["field"].get("TIME")
    return float(time[0]) if time else None


def write_pvd(frames, target):
    """Write a ParaView collection (.pvd) for [(time, vtu path), ...]."""
    entries = "\n".join(f'  <DataSet timestep="{t if t is not None else i}" file={quoteattr(os.path.basename(p))}/>'
                         for i, (t, p) in enumerate(frames))
    with open(target, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0"?>\n<VTKFile type="Collection" version="0.1">\n<Collection>\n'
                f"{entries}\n</Collection>\n</VTKFile>\n")


def convert_animation(installation, animation, env, cwd):
    """anim_to_vtk + conversion to .vtu. Returns (time, vtu path)."""
    legacy = animation + ".vtk"
    with open(legacy, "w") as out:
        code = subprocess.run(installation.anim_to_vtk_command(animation), cwd=cwd, env=env,
                              stdout=out, stderr=subprocess.DEVNULL).returncode
    if code != 0:
        raise OpenRadiossError(f"anim_to_vtk failed for {animation} (exit {code})")
    vtu = animation + ".vtu"
    time = legacy_vtk_to_vtu(legacy, vtu)
    os.remove(legacy)
    return time, vtu


def run_job(deck, installation=None, threads=1, to_vtk=True, log=print):
    """Run starter, engine(s) and anim_to_vtk in the deck's directory.

    Returns a dict with ``starter_out``, ``engine_outs``, ``animations`` and
    ``vtk_files``. Raises OpenRadiossError when a step fails.
    """
    installation = installation or Installation()
    problems = installation.problems()
    if problems:
        raise OpenRadiossError("; ".join(problems))
    installation.prepare_flatpak()
    workdir = os.path.dirname(os.path.abspath(deck))
    name = job_name(deck)
    env = installation.environment(threads)

    def call(argv):
        log("$ " + " ".join(argv))
        result = subprocess.run(argv, cwd=workdir, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.stdout:
            log(result.stdout.rstrip())
        return result.returncode

    code = call(installation.starter_command(deck, threads))
    starter_out = os.path.join(workdir, f"{name}_0000.out")
    errors, _ = listing_summary(starter_out)
    if code != 0 or errors:
        raise OpenRadiossError(f"Starter failed (exit {code}, {errors} errors), see {starter_out}")

    engine_outs = []
    for engine_input in engine_inputs(workdir, name):
        code = call(installation.engine_command(engine_input, threads))
        engine_out = os.path.splitext(engine_input)[0] + ".out"
        engine_outs.append(engine_out)
        if code != 0 or not normal_termination(engine_out):
            raise OpenRadiossError(f"Engine failed (exit {code}), see {engine_out}")

    animations = animation_files(workdir, name)
    frames = []
    if to_vtk:
        log(f"Converting {len(animations)} animation frames to .vtu")
        frames = [convert_animation(installation, animation, env, workdir) for animation in animations]
        if frames:
            write_pvd(frames, os.path.join(workdir, name + ".pvd"))
    return {"starter_out": starter_out, "engine_outs": engine_outs, "animations": animations,
            "vtk_files": [vtu for _time, vtu in frames], "times": [t for t, _vtu in frames]}
