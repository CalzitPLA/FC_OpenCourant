# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI test of the workbench with the shipped examples, run inside the FreeCAD GUI.

    FreeCAD tests/freecad_gui_test.py
    flatpak run org.freecad.FreeCAD tests/freecad_gui_test.py   (Flatpak)

Needs the workbench installed in FreeCAD's Mod folder and a solver that the
preferences find (Edit > Preferences > OpenRadioss). It drives FreeCAD like a
user: the preference page (Test installation), "Run solver calculations" on the
two FEM examples, the Run OpenRadioss dialog with "Load Results in FEM" on the
Taylor impact deck, and the Keyword and Template Editors. Message boxes are
recorded instead of shown. The report and screenshots go to $ORFE_OUT (default:
a new folder in the home directory); FreeCAD exits with 0 if everything passed.
The example files are copied there, the shipped ones stay untouched.

ORFE_DEMO_PAUSE=<seconds> pauses after each step and shows captions in the
status bar, for watching or recording the test (tests/run_gui_test.sh --record).
With ORFE_SYNC_RECORDER=1 the test writes $ORFE_OUT/.ready when its window is
set up and waits for .recording; at the end it writes .finished and waits for
.recording_stopped, so a screen recording shows nothing but the test.
"""

import os
import shutil
import time
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

import freecad.ORfemn as package

REPO = os.environ.get("ORFE_REPO") or os.path.dirname(os.path.dirname(os.path.dirname(package.__file__)))
OUT = os.environ.get("ORFE_OUT") or os.path.join(os.path.expanduser("~"), "orfe_gui_test_" + time.strftime("%Y%m%d_%H%M%S"))
SHOTS = os.path.join(OUT, "shots")
os.makedirs(SHOTS, exist_ok=True)
REPORT = os.path.join(OUT, "report.txt")
DEMO_PAUSE = float(os.environ.get("ORFE_DEMO_PAUSE") or 0)
lines, messages = [], []
mw = Gui.getMainWindow()


def _record(kind):
    def box(_parent, title, text, *args, **kwargs):
        messages.append(f"{kind}: {title}: {str(text)[:200]}")
        return QtWidgets.QMessageBox.Ok
    return staticmethod(box)


for _kind in ("information", "warning", "critical", "question"):
    setattr(QtWidgets.QMessageBox, _kind, _record(_kind))


def pump(seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.02)


def announce(text, pause=1.0):
    """Caption in the status bar; in demo mode also wait so the step can be seen."""
    mw.statusBar().showMessage(f"OpenRadioss GUI test: {text}")
    App.Console.PrintMessage(f"OpenRadioss GUI test: {text}\n")
    pump(0.2 + DEMO_PAUSE * pause)


def log(text):
    lines.append(text)
    with open(REPORT, "w") as f:
        f.write("\n".join(lines) + "\n")


def check(name, fn):
    announce(name, 0.5)
    try:
        log(f"[PASS] {name}: {fn() or ''}")
        announce(f"PASS - {name}", 1.0)
    except Exception as e:
        log(f"[FAIL] {name}: {e}\n{traceback.format_exc()}")
        announce(f"FAIL - {name}: {e}", 2.0)


def expect(value, low, high, what):
    if not low <= value <= high:
        raise AssertionError(f"{what} = {value:.4g}, expected {low:g} ... {high:g}")


def snap(name, widget=None):
    pump(0.5)
    path = os.path.join(SHOTS, name + ".png")
    (widget or mw).grab().save(path)
    return path


def save_view(name):
    Gui.activeDocument().activeView().saveImage(os.path.join(SHOTS, name + ".png"), 1400, 900, "White")


def open_example(name):
    dst = os.path.join(OUT, name + ".FCStd")
    shutil.copy(os.path.join(REPO, "examples", name + ".FCStd"), dst)
    doc = App.openDocument(dst)
    Gui.activeDocument().activeView().viewIsometric()
    return doc


def show_result(doc, field_hint, warp=None, view="isometric"):
    """Show the newest pipeline (through a warp filter if ``warp``) coloured by ``field_hint``."""
    pipelines = [o for o in doc.Objects if o.isDerivedFrom("Fem::FemPostPipeline")]
    if not pipelines:
        raise RuntimeError("no post-processing pipeline")
    shown = pipelines[-1]
    if warp:
        import ObjectsFem
        w = ObjectsFem.makePostVtkFilterWarp(doc, pipelines[-1])
        doc.recompute()
        w.Vector = [v for v in w.getEnumerationsOfProperty("Vector") if v.startswith("Displacement")][0]
        setattr(w, "Factor" if hasattr(w, "Factor") else "Scale", warp)
        doc.recompute()
        shown = w
    for o in doc.Objects:
        if getattr(o, "ViewObject", None) is not None:
            o.ViewObject.Visibility = o is shown
    vo = shown.ViewObject
    vo.DisplayMode = "Surface"
    match = [f for f in vo.getEnumerationsOfProperty("Field") if field_hint.lower() in f.lower()]
    if match:
        vo.Field = match[0]
    getattr(Gui.activeDocument().activeView(), "view" + view.capitalize())()
    pump(0.5)
    Gui.SendMsgToActiveView("ViewFit")
    return f"shown {vo.Field}" + (f", deformation x{warp}" if warp else "")


def preferences():
    """Edit > Preferences > OpenRadioss: the solver is found and passes Test installation."""
    from freecad.ORfemn import settings
    state = {}

    def inspect():  # runs inside the modal preferences dialog
        dlg = QtWidgets.QApplication.activeModalWidget()
        edits = [w for w in dlg.findChildren(QtWidgets.QLineEdit)
                 if w.placeholderText().startswith("folder that contains exec/")]
        state["path"] = edits[0].text() if edits else None
        buttons = {b.text(): b for b in dlg.findChildren(QtWidgets.QPushButton)}
        if "Test installation" in buttons:
            buttons["Test installation"].click()
            QtWidgets.QApplication.processEvents()
        end = time.time() + DEMO_PAUSE * 1.5
        while time.time() < end:
            QtWidgets.QApplication.processEvents()
            time.sleep(0.02)
        labels = [label.text() for label in dlg.findChildren(QtWidgets.QLabel)]
        state["test"] = [t for t in labels if "read the test deck" in t or "starter" in t and "failed" in t]
        state["requisites"] = "".join(t for t in labels if "<table" in t)
        dlg.grab().save(os.path.join(SHOTS, "preferences.png"))
        dlg.reject()

    QtCore.QTimer.singleShot(int(2500 + 1000 * DEMO_PAUSE), inspect)
    Gui.showPreferences("OpenRadioss")
    if not state.get("path"):
        raise RuntimeError(f"OpenRadioss preference page not shown: {state}")
    missing = state["requisites"].count("10008")
    if missing or not state["test"] or "read the test deck" not in state["test"][0]:
        raise RuntimeError(f"installation not ok: {state}")
    source = "configured" if settings.configured_path() else "auto-detected"
    return f"solver folder {state['path']} ({source}), {state['requisites'].count('10004')} requisites ok, test run ok"


def fem_example(name, field_hint, warp, view, check_result):
    doc = open_example(name)
    solver = [o for o in doc.Objects if getattr(getattr(o, "Proxy", None), "Type", "") == "Fem::SolverOpenRadioss"][0]
    Gui.activateWorkbench("FemWorkbench")
    import FemGui
    FemGui.setActiveAnalysis([o for o in doc.Objects if o.isDerivedFrom("Fem::FemAnalysis")][0])
    Gui.SendMsgToActiveView("ViewFit")
    announce(f"{name}: analysis set up, running the OpenRadioss solver...", 1.5)
    snap(f"{name}_setup")
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(solver)
    pump(0.3)  # lets the command see the selection
    t0 = time.time()
    Gui.runCommand("FEM_SolverRun")
    pump(1.0)  # the result pipeline is built in the main thread when the command returns
    results = [o for o in doc.Objects if o.isDerivedFrom("Fem::FemResultObjectPython")]
    if not results:
        raise RuntimeError(f"no result after Run solver calculations; messages: {messages[-3:]}")
    info = check_result(results[-1])
    shown = show_result(doc, field_hint, warp, view)
    announce(f"{name}: {info}; {shown}", 3.0)
    snap(f"{name}_result")
    save_view(f"{name}_view")
    return f"{time.time() - t0:.1f} s; {info}; {shown}"


def check_cantilever(res):
    tip = max(res.DisplacementLengths)
    expect(tip, 0.18, 0.20, "tip deflection [mm] (beam theory 0.192)")
    return f"tip deflection {tip:.4f} mm (beam theory 0.192)"


def check_plate(res):
    centre = max(res.DisplacementLengths)
    expect(centre, 0.0, 0.30, "centre deflection at 10 ms [mm] (oscillates 0 ... 2 x 0.131)")
    return f"centre deflection at 10 ms {centre:.4f} mm (oscillates between 0 and about 0.26)"


def taylor_example():
    doc = open_example("taylor_impact")
    Gui.activateWorkbench("OpenRadiossWorkbench")
    deck = [o for o in doc.Objects if o.TypeId == "App::TextDocument"][0]
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(deck)
    pump(0.3)
    Gui.runCommand("RunOpenRadioss")
    pump(1.0)
    from freecad.ORfemn.gui.run_dialog import RunDialog
    dialogs = [w for w in QtWidgets.QApplication.topLevelWidgets() if isinstance(w, RunDialog) and w.isVisible()]
    if not dialogs:
        raise RuntimeError("the Run OpenRadioss dialog did not open")
    dlg = dialogs[-1]
    dlg.workdir_edit.setText(os.path.join(OUT, "taylor_run"))
    t0 = time.time()
    dlg.run_button.click()
    while time.time() - t0 < 300:
        pump(0.5)
        if time.time() - t0 > 2 and dlg.run_button.isEnabled():
            break
    announce("taylor_impact: solver finished, loading the last frame into FEM post-processing", 1.5)
    snap("taylor_impact_run_dialog", dlg)
    if not dlg.vtk_files:
        raise RuntimeError(f"no result frames; solver folder {dlg.install_edit.text()!r}; "
                           f"status {dlg.status_label.text()!r}; log: {dlg.log.toPlainText()[-600:]}")
    dlg.results_button.click()
    pump(1.5)
    res = [o for o in doc.Objects if o.isDerivedFrom("Fem::FemResultObjectPython")][-1]
    peeq = max(res.Peeq or [0])
    expect(peeq, 0.3, 2.0, "maximum equivalent plastic strain")
    dlg.showMinimized()
    shown = show_result(doc, "plastic", 1)
    announce(f"taylor_impact: max. equivalent plastic strain {peeq:.2f}; {shown}", 3.0)
    snap("taylor_impact_result")
    save_view("taylor_impact_view")
    dlg.close()
    return f"{time.time() - t0:.1f} s, {len(dlg.vtk_files)} frames, max plastic strain {peeq:.2f}; {shown}"


def editors():
    from freecad.ORfemn.gui.keyword_editor import KeywordEditorDialog
    from freecad.ORfemn.gui.template_editor import TemplateEditorDialog
    for name, cls in (("keyword_editor", KeywordEditorDialog), ("template_editor", TemplateEditorDialog)):
        dialog = cls(mw)
        dialog.show()
        pump(1.0 + DEMO_PAUSE * 1.5)
        snap(name, dialog)
        dialog.close()
    return "both dialogs open"


def handshake(write, wait_for, timeout):
    """Marker files shared with tests/run_gui_test.sh --record."""
    if os.environ.get("ORFE_SYNC_RECORDER") != "1":
        return
    open(os.path.join(OUT, write), "w").close()
    end = time.time() + timeout
    while time.time() < end and not os.path.exists(os.path.join(OUT, wait_for)):
        pump(0.2)


mw.showMaximized()
pump(1.0)
handshake(".ready", ".recording", 20)
log(f"===== FreeCAD {'.'.join(App.Version()[:3])} GUI test ({QtGui.QGuiApplication.platformName()}), "
    f"{time.strftime('%Y-%m-%d %H:%M')} =====")
check("Preferences: solver found, Test installation", preferences)
check("cantilever_beam: Run solver calculations",
      lambda: fem_example("cantilever_beam", "von mises", 100, "front", check_cantilever))
check("plate_sudden_pressure: Run solver calculations",
      lambda: fem_example("plate_sudden_pressure", "displacement magnitude", 200, "isometric", check_plate))
check("taylor_impact: Run OpenRadioss dialog, Load Results in FEM", taylor_example)
check("Keyword Editor and Template Editor", editors)
log(f"message boxes: {messages}")
passed = all(line.startswith("[PASS]") for line in lines if line.startswith("["))
log("ALL PASS" if passed else "SOME FAILED")
announce("ALL PASS" if passed else "SOME FAILED - see " + REPORT, 3.0)
handshake(".finished", ".recording_stopped", 20)
App.Console.PrintMessage(f"OpenRadioss GUI test: {'ALL PASS' if passed else 'SOME FAILED'}, report {REPORT}\n")
for d in list(App.listDocuments()):
    App.closeDocument(d)
os._exit(0 if passed else 1)
