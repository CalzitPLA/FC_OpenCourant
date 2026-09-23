"""Dialog that runs OpenRadioss on a .k deck and shows its progress."""

import os
import re

import FreeCAD
from PySide import QtCore, QtGui, QtWidgets

from .. import radioss_runner

PARAMS = "User parameter:BaseApp/Preferences/Mod/ORfemn"


def params():
    return FreeCAD.ParamGet(PARAMS)


def installation():
    """The configured OpenRadioss installation."""
    return radioss_runner.Installation(params().GetString("OpenRadiossPath", radioss_runner.DEFAULT_INSTALL))


def default_workdir(doc, name):
    """<document folder>/<document>_radioss/<name>, or ~/OpenRadioss_runs/<name> for unsaved documents."""
    if doc is not None and doc.FileName:
        base = os.path.join(os.path.dirname(doc.FileName), f"{os.path.splitext(os.path.basename(doc.FileName))[0]}_radioss")
    else:
        base = os.path.join(os.path.expanduser("~"), "OpenRadioss_runs")
    return os.path.join(base, re.sub(r"[^A-Za-z0-9_.-]+", "_", name) or "job")


def load_vtk_result(doc, vtk_file, name="OpenRadiossResult", analysis=None):
    """Load a VTK result file into a FEM post-processing pipeline and return it (None without FEM)."""
    try:
        import Fem  # noqa: F401  (registers the Fem:: types)
    except ImportError:
        FreeCAD.Console.PrintWarning("FEM module not available; results not loaded\n")
        return None
    pipeline = doc.addObject("Fem::FemPostPipeline", name)
    pipeline.read(vtk_file)
    pipeline.Label = f"{name} ({os.path.basename(vtk_file)})"
    if analysis is not None:
        analysis.addObject(pipeline)
    doc.recompute()
    return pipeline


class RunDialog(QtWidgets.QDialog):
    """Write a deck to a working directory and run starter, engine and anim_to_vtk."""

    def __init__(self, deck_text, job_name, doc=None, parent=None):
        super(RunDialog, self).__init__(parent)
        self.setWindowTitle(f"Run OpenRadioss – {job_name}")
        self.setMinimumSize(900, 650)
        self.setModal(False)
        self.deck_text = deck_text
        self.job_name = re.sub(r"[^A-Za-z0-9_-]+", "_", job_name) or "job"
        self.doc = doc
        self.process = None
        self.queue = []
        self.vtk_files = []
        self.stopped = False

        self.setup_ui()
        self.check_installation()

    # ------------------------------------------------------------------
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        self.install_edit = QtWidgets.QLineEdit(installation().path)
        self.install_edit.editingFinished.connect(self.check_installation)
        browse_install = QtWidgets.QPushButton("Browse...")
        browse_install.clicked.connect(lambda: self.browse(self.install_edit, self.check_installation))
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.install_edit)
        row.addWidget(browse_install)
        form.addRow("OpenRadioss folder:", row)

        self.workdir_edit = QtWidgets.QLineEdit(default_workdir(self.doc, self.job_name))
        browse_work = QtWidgets.QPushButton("Browse...")
        browse_work.clicked.connect(lambda: self.browse(self.workdir_edit))
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.workdir_edit)
        row.addWidget(browse_work)
        form.addRow("Working folder:", row)

        self.threads_spin = QtWidgets.QSpinBox()
        self.threads_spin.setRange(1, max(1, os.cpu_count() or 1))
        self.threads_spin.setValue(min(params().GetInt("Threads", 2), self.threads_spin.maximum()))
        form.addRow("Threads:", self.threads_spin)

        self.vtk_check = QtWidgets.QCheckBox("Convert animation frames to VTK")
        self.vtk_check.setChecked(params().GetBool("ConvertToVtk", True))
        form.addRow("", self.vtk_check)
        layout.addLayout(form)

        self.status_label = QtWidgets.QLabel()
        layout.addWidget(self.status_label)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(20000)
        self.log.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        layout.addWidget(self.log)

        buttons = QtWidgets.QHBoxLayout()
        self.run_button = QtWidgets.QPushButton("Run")
        self.run_button.clicked.connect(self.start)
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop)
        self.stop_button.setEnabled(False)
        self.folder_button = QtWidgets.QPushButton("Open Folder")
        self.folder_button.clicked.connect(self.open_folder)
        self.results_button = QtWidgets.QPushButton("Load Results in FEM")
        self.results_button.setToolTip("Load the last frame into a FEM post-processing pipeline "
                                       "(all frames: open the .pvd file in ParaView)")
        self.results_button.clicked.connect(self.load_results)
        self.results_button.setEnabled(False)
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.close)
        for button in (self.run_button, self.stop_button, self.folder_button, self.results_button):
            buttons.addWidget(button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def browse(self, line_edit, then=None):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder", line_edit.text())
        if path:
            line_edit.setText(path)
            if then:
                then()

    def installation(self):
        return radioss_runner.Installation(self.install_edit.text())

    def check_installation(self):
        problems = self.installation().problems()
        if problems:
            self.status_label.setText("<b style='color:#d9534f'>" + "<br>".join(problems) + "</b><br>"
                                      "Download OpenRadioss from github.com/OpenRadioss/OpenRadioss/releases "
                                      "and select the unpacked OpenRadioss folder.")
        else:
            self.status_label.setText("Ready.")
        self.run_button.setEnabled(not problems and self.process is None)
        return not problems

    def append(self, text):
        self.log.appendPlainText(text.rstrip("\n"))

    # ------------------------------------------------------------------
    def start(self):
        if not self.check_installation():
            return
        inst = self.installation()
        params().SetString("OpenRadiossPath", inst.path)
        params().SetInt("Threads", self.threads_spin.value())
        params().SetBool("ConvertToVtk", self.vtk_check.isChecked())

        self.workdir = self.workdir_edit.text()
        try:
            os.makedirs(self.workdir, exist_ok=True)
            for f in os.listdir(self.workdir):  # old results of the same job would be mixed in
                if radioss_runner.is_result_file(f, self.job_name):
                    os.remove(os.path.join(self.workdir, f))
            self.deck = os.path.join(self.workdir, self.job_name + ".k")
            with open(self.deck, "w") as f:
                f.write(self.deck_text)
            copied = inst.prepare_flatpak()
        except OSError as e:
            QtWidgets.QMessageBox.critical(self, "Run OpenRadioss", f"Cannot prepare {self.workdir}:\n{e}")
            return
        if copied:
            self.append(f"Copied host libraries for the Flatpak sandbox: {', '.join(copied)}")

        self.inst, self.threads, self.stopped = inst, self.threads_spin.value(), False
        self.vtk_files, self.frames = [], []
        self.log.clear()
        self.append(f"Deck: {self.deck}")
        self.queue = [("Starter", inst.starter_command(self.deck, self.threads), None, self.after_starter)]
        self.set_running(True)
        self.next_step()

    def set_running(self, running):
        self.run_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.progress.setVisible(running)
        self.results_button.setEnabled(not running and bool(self.vtk_files))

    def next_step(self):
        if self.stopped:
            return
        if not self.queue:
            if self.vtk_files:
                radioss_runner.write_pvd(self.frames, os.path.join(self.workdir, self.job_name + ".pvd"))
            self.finish(True, f"Finished. {len(self.vtk_files)} result frames (.vtu, {self.job_name}.pvd) in {self.workdir}")
            return
        title, argv, stdout_file, on_done = self.queue.pop(0)
        self.status_label.setText(f"Running {title} ...")
        if not title.startswith("anim_to_vtk") or "(1/" in title:  # log the conversion command once
            self.append(f"\n$ {' '.join(argv)}")
        self.process = QtCore.QProcess(self)
        self.process.setWorkingDirectory(self.workdir)
        env = QtCore.QProcessEnvironment()
        for key, value in self.inst.environment(self.threads).items():
            env.insert(key, value)
        self.process.setProcessEnvironment(env)
        if stdout_file:
            self.process.setStandardOutputFile(stdout_file)
        else:
            self.process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
            self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(lambda code, _status: self.step_finished(title, code, on_done))
        self.process.errorOccurred.connect(lambda error: self.step_error(title, error))
        self.process.start(argv[0], argv[1:])

    def read_output(self):
        if self.process:
            self.append(bytes(self.process.readAllStandardOutput()).decode(errors="replace"))

    def step_error(self, title, error):
        if error == QtCore.QProcess.FailedToStart:
            self.finish(False, f"{title} could not be started.")

    def step_finished(self, title, code, on_done):
        self.read_output()
        self.process = None
        if self.stopped:
            return
        if code != 0:
            detail = ""
            if title == "Starter":
                listing = os.path.join(self.workdir, f"{radioss_runner.job_name(self.deck)}_0000.out")
                errors, _warnings = radioss_runner.listing_summary(listing)
                if errors:
                    detail = f" - {errors} error(s) in the deck, see {os.path.basename(listing)}"
                    for message in radioss_runner.listing_messages(listing):
                        self.append("  " + message)
            self.finish(False, f"{title} failed with exit code {code}{detail}.")
            return
        if on_done and not on_done():
            return
        self.next_step()

    def after_starter(self):
        name = radioss_runner.job_name(self.deck)
        out = os.path.join(self.workdir, f"{name}_0000.out")
        errors, warnings = radioss_runner.listing_summary(out)
        self.append(f"Starter: {errors} errors, {warnings} warnings (listing: {out})")
        for message in radioss_runner.listing_messages(out, "WARNING"):
            self.append("  " + message)
        if errors:
            for message in radioss_runner.listing_messages(out):
                self.append("  " + message)
            self.finish(False, f"The starter found {errors} error(s) in the deck. See {os.path.basename(out)}.")
            return False
        inputs = radioss_runner.engine_inputs(self.workdir, name)
        if not inputs:
            self.finish(False, "The starter wrote no engine input file.")
            return False
        for engine_input in inputs:
            self.queue.append(("Engine", self.inst.engine_command(engine_input, self.threads), None,
                               lambda f=engine_input: self.after_engine(f)))
        return True

    def after_engine(self, engine_input):
        out = os.path.splitext(engine_input)[0] + ".out"
        if not radioss_runner.normal_termination(out):
            self.finish(False, f"The engine did not terminate normally. See {os.path.basename(out)}.")
            return False
        if self.vtk_check.isChecked() and not self.queue:
            animations = radioss_runner.animation_files(self.workdir, radioss_runner.job_name(self.deck))
            for n, animation in enumerate(animations, 1):
                self.queue.append((f"anim_to_vtk {os.path.basename(animation)} ({n}/{len(animations)})",
                                   self.inst.anim_to_vtk_command(animation), animation + ".vtk",
                                   lambda a=animation: self.convert_frame(a)))
        return True

    def convert_frame(self, animation):
        """Convert the legacy VTK written by anim_to_vtk to .vtu (keeps all result arrays)."""
        legacy, vtu = animation + ".vtk", animation + ".vtu"
        try:
            time = radioss_runner.legacy_vtk_to_vtu(legacy, vtu)
            os.remove(legacy)
        except (OSError, ValueError) as e:
            self.finish(False, f"Converting {os.path.basename(legacy)} failed: {e}")
            return False
        self.frames.append((time, vtu))
        self.vtk_files.append(vtu)
        return True

    def finish(self, ok, message):
        self.queue = []
        self.set_running(False)
        color = "#5cb85c" if ok else "#d9534f"
        self.status_label.setText(f"<b style='color:{color}'>{message}</b>")
        self.append(("\n" if ok else "\nERROR: ") + message)
        (FreeCAD.Console.PrintMessage if ok else FreeCAD.Console.PrintError)(f"OpenRadioss: {message}\n")

    def stop(self):
        self.stopped = True
        self.queue = []
        if self.process is not None:
            self.process.kill()
            self.process.waitForFinished(3000)
            self.process = None
        self.finish(False, "Stopped by user.")

    def open_folder(self):
        folder = self.workdir_edit.text()
        if os.path.isdir(folder):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))

    def load_results(self):
        if not self.vtk_files:
            return
        doc = self.doc or FreeCAD.ActiveDocument or FreeCAD.newDocument("OpenRadiossResults")
        pipeline = load_vtk_result(doc, self.vtk_files[-1], f"{self.job_name}_result")
        if pipeline is not None:
            self.append(f"Loaded {os.path.basename(self.vtk_files[-1])} into '{pipeline.Label}'. "
                        "Use the FEM workbench to colour it by Displacement or Stress.")

    def closeEvent(self, event):
        if self.process is not None:
            reply = QtWidgets.QMessageBox.question(self, "Run OpenRadioss", "A job is running. Stop it and close?",
                                                   QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if reply != QtWidgets.QMessageBox.Yes:
                event.ignore()
                return
            self.stop()
        event.accept()
