# Installation

Three parts: **FreeCAD**, the **workbench**, and the solver **OpenCourant** (the community continuation of
OpenRadioss). About five minutes.

> Tested on Linux (Debian 13; FreeCAD 1.0.0 package and 1.1.4 Flatpak). The Windows and macOS commands
> follow the standard FreeCAD folders but have not been tested yet – please report problems.

## 1. FreeCAD 1.0 or newer

| OS | Command (or download from [freecad.org](https://www.freecad.org/downloads.php)) |
|---|---|
| Linux | `flatpak install flathub org.freecad.FreeCAD` (or your distribution's package) |
| Windows | `winget install --id FreeCAD.FreeCAD` |
| macOS | `brew install --cask freecad` |

## 2. The workbench

**Any OS, no git needed:** open FreeCAD, *View → Panels → Python console*, paste this and press Enter, then
restart FreeCAD. Running it again updates the workbench (it replaces the `FC_OpenCourant` folder).

```python
import FreeCAD, os, io, shutil, zipfile, urllib.request
mod = os.path.join(FreeCAD.getUserAppDataDir(), "Mod"); target = os.path.join(mod, "FC_OpenCourant")
data = urllib.request.urlopen("https://github.com/CalzitPLA/FC_OpenCourant/archive/refs/heads/main.zip").read()
shutil.rmtree(target, ignore_errors=True); zipfile.ZipFile(io.BytesIO(data)).extractall(mod)
os.rename(os.path.join(mod, "FC_OpenCourant-main"), target); print("Installed to", target)
```

**With git** (update later with `git pull`), clone into FreeCAD's `Mod` folder:

| OS | Command (FreeCAD 1.1; for FreeCAD 1.0 leave out `v1-1/`) |
|---|---|
| Linux | `git clone https://github.com/CalzitPLA/FC_OpenCourant ~/.local/share/FreeCAD/v1-1/Mod/FC_OpenCourant` |
| Linux, Flatpak | `git clone https://github.com/CalzitPLA/FC_OpenCourant ~/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/Mod/FC_OpenCourant` |
| Windows (PowerShell) | `git clone https://github.com/CalzitPLA/FC_OpenCourant "$env:APPDATA\FreeCAD\v1-1\Mod\FC_OpenCourant"` |
| macOS | `git clone https://github.com/CalzitPLA/FC_OpenCourant ~/Library/Application\ Support/FreeCAD/v1-1/Mod/FC_OpenCourant` |

Not sure which folder? In FreeCAD's Python console: `print(FreeCAD.getUserAppDataDir() + "Mod")`.

## 3. The solver: OpenCourant

**Easiest (Linux, Windows):** *Edit → Preferences → OpenRadioss → Download OpenCourant...*, choose a
folder. The newest release for your platform is downloaded, unpacked, selected and tested.

**By hand:** unpack a release into your home folder; `~/OpenCourant` is found automatically.

| OS | Command |
|---|---|
| Linux x86-64 | `curl -L https://github.com/OpenCourant/OpenCourant/releases/latest/download/OpenCourant_linux64.zip -o /tmp/oc.zip && unzip -q /tmp/oc.zip -d ~` |
| Linux arm64 | same with `OpenCourant_linuxa64.zip` |
| Windows (PowerShell) | `Invoke-WebRequest https://github.com/OpenCourant/OpenCourant/releases/latest/download/OpenCourant_win64.zip -OutFile $env:TEMP\oc.zip; Expand-Archive $env:TEMP\oc.zip -DestinationPath $HOME` |
| macOS | OpenCourant has no macOS release. Keyword editor, templates and deck export work; run the exported `.k` on Linux or Windows, or build OpenCourant from source and set its folder in the preferences (untested). |

Elsewhere? Set the folder (the one containing `exec/` and `hm_cfg_files/`) in *Edit → Preferences →
OpenRadioss*. With the FreeCAD Flatpak the two host libraries the solver needs are copied automatically.

## 4. Check

1. *Edit → Preferences → OpenRadioss*: every line has a green tick; **Test installation** reports
   "read the test deck: 0 errors".
2. Open `examples/cantilever_beam.FCStd` (in the workbench folder), switch to the FEM workbench, select
   *SolverOpenRadioss*, click *Run solver calculations*: tip deflection about 0.187 mm.
3. Optional, the full GUI test (about a minute): `tests/run_gui_test.sh` (Linux), or start FreeCAD with
   `tests/freecad_gui_test.py` as argument on any OS. It ends with `ALL PASS`.

## If something fails

| Message | Fix |
|---|---|
| *Missing in .../exec* | Wrong folder: select the folder that contains `exec/` and `hm_cfg_files/`. |
| *Reader configuration files are not available* (Test installation) | `hm_cfg_files` from another release: unpack one complete release, do not mix versions. |
| *libcrypt.so.1 / libapr-1.so.0 not found* (Flatpak) | Install them on the host, e.g. `sudo apt install libcrypt1 libapr1` (Debian/Ubuntu) or `sudo dnf install libxcrypt-compat apr` (Fedora). |
| Workbench missing after restart | Check the folder (step 2) and *View → Panels → Report view* for errors. |

The workbench comes with no warranty (LGPL-2.1-or-later); check simulation results before relying on them.
