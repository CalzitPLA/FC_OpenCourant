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

import json
import math
import os
import platform
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from xml.sax.saxutils import quoteattr

# OpenRadioss was discontinued in October 2026; OpenCourant is its community continuation
# with the same release layout and executable names. Both folder names are looked for.
INSTALL_DIR_NAMES = ("OpenCourant", "OpenRadioss")
DEFAULT_INSTALL = os.path.join(os.path.expanduser("~"), INSTALL_DIR_NAMES[0])
RELEASES_API = "https://api.github.com/repos/OpenCourant/OpenCourant/releases"
RELEASES_PAGE = "https://github.com/OpenCourant/OpenCourant/releases"

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
    """An OpenRadioss / OpenCourant installation (the unpacked release directory).

    Without ``path`` the first usable folder of ``candidate_paths()`` is taken
    (``DEFAULT_INSTALL`` if there is none).
    """

    def __init__(self, path=None):
        if path is None:
            found = detect_installation()
            path = found.path if found else DEFAULT_INSTALL
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

    def requisites(self):
        """What a run needs, as a list of (name, ok, detail) for display."""
        items = [("Solver folder", os.path.isdir(self.path), self.path)]
        for tool in ("starter", "engine", "anim_to_vtk"):
            exe = self.executable(tool)
            if not os.path.isfile(exe):
                items.append((f"{tool} executable", False, f"missing: {exe}"))
            else:
                runnable = self.ext == ".exe" or os.access(exe, os.X_OK)
                items.append((f"{tool} executable", runnable, exe if runnable else f"not executable: {exe}"))
        cfg = os.path.join(self.path, "hm_cfg_files", "config", "CFG")
        items.append(("Reader configuration", os.path.isdir(cfg), cfg if os.path.isdir(cfg) else f"missing: {cfg}"))
        for name, sub in (("hm_reader library", ("hm_reader", self.libdir)), ("h3d library", ("h3d", "lib", self.libdir))):
            folder = os.path.join(self.path, "extlib", *sub)
            items.append((name, os.path.isdir(folder), folder if os.path.isdir(folder) else f"missing: {folder}"))
        if in_flatpak() and self.arch == "linux64_gf":
            for lib in FLATPAK_MISSING_LIBS:
                copied = os.path.exists(os.path.join(self.flatpak_compat_dir, lib))
                on_host = os.path.exists(os.path.join(FLATPAK_HOST_LIB_DIR, lib))
                detail = ("copied to " + self.flatpak_compat_dir if copied else
                          "found on the host, copied before the first run" if on_host else
                          f"not found in {FLATPAK_HOST_LIB_DIR}: install it on the host system")
                items.append((f"{lib} (Flatpak)", copied or on_host, detail))
        return items

    def test_run(self, deck_text, timeout=120):
        """Run the starter on ``deck_text`` in a temporary folder. Returns (ok, message).

        This finds problems a file check cannot, e.g. reader configuration files
        that do not match the executables.
        """
        problems = self.problems()
        if problems:
            return False, "; ".join(problems)
        try:
            self.prepare_flatpak()
        except OSError as e:
            return False, f"Cannot copy the Flatpak compatibility libraries: {e}"
        with tempfile.TemporaryDirectory(prefix="orfe_check_") as tmp:
            deck = os.path.join(tmp, "install_check.k")
            with open(deck, "w") as f:
                f.write(deck_text)
            try:
                result = subprocess.run(self.starter_command(deck), cwd=tmp, env=self.environment(1),
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                        errors="replace", timeout=timeout)
            except (OSError, subprocess.TimeoutExpired) as e:
                return False, f"The starter could not be run: {e}"
            output = result.stdout or ""
            commit = re.search(r"CommitID:\s*(\w+)", output)
            version = f" (commit {commit.group(1)[:10]})" if commit else ""
            listing = os.path.join(tmp, "install_check_0000.out")
            errors, warnings = listing_summary(listing)
            if result.returncode == 0 and errors == 0:
                return True, f"The starter{version} read the test deck: 0 errors, {warnings or 0} warnings."
            messages = listing_messages(listing) or [
                " ".join(line.strip() for line in block.splitlines() if line.strip())
                for block in re.findall(r"ERROR :(.*?)-{20,}", output, re.S)]
            detail = "; ".join(m for m in messages if m)
            if not detail:
                tail = output.strip().splitlines()
                detail = tail[-1].strip() if tail else "no output"
            return False, f"The starter{version} failed (exit code {result.returncode}): {detail}"

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


def candidate_paths(environ=None, home=None):
    """Folders where an installation is looked for, in order."""
    environ = os.environ if environ is None else environ
    home = home or os.path.expanduser("~")
    paths = [environ.get("OPENCOURANT_PATH"), environ.get("OPENRADIOSS_PATH")]
    paths += [os.path.join(home, name) for name in INSTALL_DIR_NAMES]
    if platform.system() != "Windows":
        paths += [os.path.join("/opt", name) for name in INSTALL_DIR_NAMES]
    unique = []
    for path in paths:
        if path and path not in unique:
            unique.append(path)
    return unique


def detect_installation(environ=None, home=None):
    """The first usable installation in ``candidate_paths()``, or None."""
    for path in candidate_paths(environ, home):
        installation = Installation(path)
        if not installation.problems():
            return installation
    return None


# --- downloading a release ---------------------------------------------

def release_asset_name(system=None, machine=None):
    """Name of the release archive for this platform, e.g. OpenCourant_linux64.zip."""
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    if system == "Darwin":
        raise OpenRadiossError("OpenCourant provides no macOS release (Linux x86-64/arm64 and Windows only). "
                               "On macOS the deck tools work; run the solver on Linux or Windows, or build "
                               "OpenCourant from source.")
    if system == "Windows":
        return "OpenCourant_win64.zip"
    if machine in ("aarch64", "arm64"):
        return "OpenCourant_linuxa64.zip"
    return "OpenCourant_linux64.zip"


def latest_release(asset_name=None, fetch=None):
    """(tag, download url, size in bytes) of the newest OpenCourant release with ``asset_name``.

    ``fetch(url)`` returns the response body; by default the GitHub API is asked.
    """
    asset_name = asset_name or release_asset_name()
    if fetch is None:
        def fetch(url):
            request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                           "User-Agent": "FreeCAD-ORfemn"})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
    releases = json.loads(fetch(RELEASES_API + "?per_page=10"))
    for release in releases:
        if release.get("draft") or release.get("prerelease"):
            continue
        for asset in release.get("assets", []):
            if asset.get("name") == asset_name:
                return release["tag_name"], asset["browser_download_url"], int(asset.get("size") or 0)
    raise OpenRadiossError(f"No OpenCourant release with {asset_name} found at {RELEASES_PAGE}")


def download(url, target, progress=None, chunk_size=1 << 20):
    """Download ``url`` to ``target``. ``progress(done, total)`` may return False to cancel."""
    partial = target + ".part"
    cancelled = False
    request = urllib.request.Request(url, headers={"User-Agent": "FreeCAD-ORfemn"})
    with urllib.request.urlopen(request, timeout=60) as response, open(partial, "wb") as f:
        total, done = int(response.headers.get("Content-Length") or 0), 0
        while True:
            block = response.read(chunk_size)
            if not block:
                break
            f.write(block)
            done += len(block)
            if progress is not None and progress(done, total) is False:
                cancelled = True
                break
    if cancelled or (total and done < total):
        os.remove(partial)
        raise OpenRadiossError("Download cancelled" if cancelled else f"Download incomplete ({done} of {total} bytes)")
    os.replace(partial, target)
    return target


def extract_release(archive, parent):
    """Unpack a release archive into ``parent`` (keeping executable bits); returns the installation folder.

    The folder is the one that contains ``exec/`` (``<parent>/OpenCourant`` for the official archives).
    """
    parent = os.path.abspath(parent)
    os.makedirs(parent, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            target = os.path.abspath(os.path.join(parent, info.filename))
            if os.path.commonpath([parent, target]) != parent:
                raise OpenRadiossError(f"Unsafe path in archive: {info.filename}")
            z.extract(info, parent)
            mode = (info.external_attr >> 16) & 0o777
            if mode and not info.is_dir():
                os.chmod(target, mode)
    for root, dirs, _files in os.walk(parent):
        if "exec" in dirs and "hm_cfg_files" in dirs:
            return root
    raise OpenRadiossError(f"No OpenCourant installation (exec/ and hm_cfg_files/) found in {archive}")


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
