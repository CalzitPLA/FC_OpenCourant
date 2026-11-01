# Testing your installation

Three levels, from one minute to fully automatic. Do at least the first after installing.

## 1. Quick check in FreeCAD (1–2 minutes, no terminal)

1. *Edit → Preferences → OpenRadioss*: every line has a green tick. Click **Test installation**:
   it must report *"The starter ... read the test deck: 0 errors"*.
2. *File → Open* `examples/cantilever_beam.FCStd` from the workbench folder
   (where it is: `print(FreeCAD.getUserAppDataDir() + "Mod/FC_OpenCourant/examples")` in the Python console).
3. Switch to the **FEM** workbench, double-click *Analysis*, select *SolverOpenRadioss*, click
   **Run solver calculations**. After a few seconds the analysis contains *OpenRadiossResult* and a
   pipeline. Double-click the result: the maximum displacement is about **0.187 mm**
   (beam theory 0.192 mm).

All three steps pass, so the workbench and the solver work. The other two examples
(`plate_sudden_pressure`, `taylor_impact`) are described in [examples/README.md](examples/README.md).

## 2. Automatic GUI test (about 1 minute)

The test opens its own FreeCAD window and runs the same steps a user would: the preference page with
*Test installation*, *Run solver calculations* on the cantilever and the plate, the *Run OpenRadioss*
dialog with *Load Results in FEM* on the Taylor impact, and the Keyword and Template Editors. It
checks the results against theory and closes FreeCAD at the end. It works on copies of the examples,
so nothing in the workbench folder changes. Do not click into the window while it runs.

| Installed with | Command |
|---|---|
| FreeCAD Flatpak (Linux) | `sh ~/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/Mod/FC_OpenCourant/tests/run_gui_test.sh --flatpak` |
| FreeCAD from the distribution / AppImage as `freecad` (Linux) | `sh ~/.local/share/FreeCAD/v1-1/Mod/FC_OpenCourant/tests/run_gui_test.sh --native` |
| Windows (PowerShell, untested) | `& "C:\Program Files\FreeCAD 1.1\bin\freecad.exe" "$env:APPDATA\FreeCAD\v1-1\Mod\FC_OpenCourant\tests\freecad_gui_test.py"` |
| macOS | needs a solver, and OpenCourant has no macOS release: the GUI test cannot pass there |

For FreeCAD 1.0 leave out `v1-1/` (or `v1-1\`). `sh ...` is needed because the one-line installer does not
keep the executable bit; with a git clone `tests/run_gui_test.sh` works directly.

**Expected result**: the terminal (or `report.txt`) ends with

```
[PASS] Preferences: solver found, Test installation: ...
[PASS] cantilever_beam: Run solver calculations: ...; tip deflection 0.1868 mm (beam theory 0.192); ...
[PASS] plate_sudden_pressure: Run solver calculations: ...
[PASS] taylor_impact: Run OpenRadioss dialog, Load Results in FEM: ..., 30 frames, max plastic strain 0.81; ...
[PASS] Keyword Editor and Template Editor: both dialogs open
ALL PASS
```

The report and screenshots of every step are written to `~/orfe_gui_test_<date>/` (set `ORFE_OUT` to
choose another folder; with the Flatpak it must be inside your home folder). The exit code is 0 when
everything passed.

**Record a video** of the test (GNOME desktops): add `--record test.mp4`. It records only while the test
runs, but captures whatever is on screen in that time: keep other windows away, tick *"Don't show this
start page again"* on FreeCAD's Start page (it lists your recent files) and watch the video before you
share it.

## 3. Unit tests (developers, seconds)

FreeCAD is not needed, only Python 3:

```shell
python3 tests/tests.py      # in the workbench folder
```

54 tests of the `.k` formatting, templates, deck writer, result conversion, solver detection and the
release download; three of them run the real solver and are skipped when none is found. Expected:
`OK` (or `OK (skipped=3)` without a solver).

## Report the result

Please report results – passed or failed – in the [FreeCAD forum thread](https://forum.freecad.org/viewforum.php?f=18)
or as a [GitHub issue](https://github.com/CalzitPLA/FC_OpenCourant/issues), with:

- operating system, FreeCAD version (*Help → About FreeCAD → Copy to clipboard*), how FreeCAD is installed
- OpenCourant release (shown by *Test installation*)
- `report.txt` of the GUI test, or the error message

Reports from Windows are especially welcome: it has not been tested yet.
