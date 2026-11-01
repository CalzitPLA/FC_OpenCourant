# SPDX-License-Identifier: LGPL-2.1-or-later
"""Edit > Preferences > OpenRadioss: solver folder, requirements check, OpenCourant download, defaults."""

import html
import os
import tempfile

import FreeCAD
from PySide import QtCore, QtWidgets

from .. import kfile_format, radioss_runner, settings

OK, BAD = "#3c9a3c", "#d9534f"


class PreferencesPage:
    """Preference page (registered with FreeCADGui.addPreferencePage in init_gui.py)."""

    def __init__(self, parent=None):
        self.form = QtWidgets.QWidget(parent)
        self.form.setWindowTitle("OpenRadioss")
        layout = QtWidgets.QVBoxLayout(self.form)

        solver = QtWidgets.QGroupBox("Solver: OpenCourant / OpenRadioss")
        grid = QtWidgets.QGridLayout(solver)
        intro = QtWidgets.QLabel(
            "The workbench runs the starter, engine and anim_to_vtk of an unpacked "
            f"<a href='{radioss_runner.RELEASES_PAGE}'>OpenCourant</a> release (the community "
            "continuation of OpenRadioss; OpenRadioss releases work too). Used by the "
            "<i>Run OpenRadioss</i> dialog and the FEM solver.")
        intro.setWordWrap(True)
        intro.setOpenExternalLinks(True)
        grid.addWidget(intro, 0, 0, 1, 4)

        grid.addWidget(QtWidgets.QLabel("Solver folder:"), 1, 0)
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setPlaceholderText("folder that contains exec/ and hm_cfg_files/")
        self.path_edit.textChanged.connect(self.refresh)
        grid.addWidget(self.path_edit, 1, 1)
        browse = QtWidgets.QPushButton("Browse...")
        browse.clicked.connect(self.browse)
        grid.addWidget(browse, 1, 2)
        detect = QtWidgets.QPushButton("Auto-detect")
        detect.setToolTip("Look in $OPENCOURANT_PATH, $OPENRADIOSS_PATH, ~/OpenCourant, ~/OpenRadioss, "
                          "/opt/OpenCourant, /opt/OpenRadioss")
        detect.clicked.connect(self.auto_detect)
        grid.addWidget(detect, 1, 3)

        self.requisites_label = QtWidgets.QLabel()
        self.requisites_label.setTextFormat(QtCore.Qt.RichText)
        self.requisites_label.setWordWrap(True)
        self.requisites_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        grid.addWidget(self.requisites_label, 2, 0, 1, 4)

        buttons = QtWidgets.QHBoxLayout()
        self.test_button = QtWidgets.QPushButton("Test installation")
        self.test_button.setToolTip("Run the starter on a small deck (a few seconds). This also finds reader "
                                    "configuration files that do not match the executables.")
        self.test_button.clicked.connect(self.test_installation)
        buttons.addWidget(self.test_button)
        download = QtWidgets.QPushButton("Download OpenCourant...")
        download.setToolTip(f"Download and unpack the newest release from {radioss_runner.RELEASES_PAGE}")
        download.clicked.connect(self.download)
        buttons.addWidget(download)
        buttons.addStretch()
        grid.addLayout(buttons, 3, 0, 1, 4)
        self.test_label = QtWidgets.QLabel()
        self.test_label.setWordWrap(True)
        self.test_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        grid.addWidget(self.test_label, 4, 0, 1, 4)
        grid.setColumnStretch(1, 1)
        layout.addWidget(solver)

        defaults = QtWidgets.QGroupBox("Run OpenRadioss dialog defaults")
        form = QtWidgets.QFormLayout(defaults)
        self.threads_spin = QtWidgets.QSpinBox()
        self.threads_spin.setRange(1, max(1, os.cpu_count() or 1))
        form.addRow("Threads:", self.threads_spin)
        self.vtk_check = QtWidgets.QCheckBox("Convert animation frames to VTK (.vtu, .pvd)")
        form.addRow("", self.vtk_check)
        note = QtWidgets.QLabel("The FEM solver object has its own Threads property.")
        note.setEnabled(False)
        form.addRow("", note)
        layout.addWidget(defaults)
        layout.addStretch()

    # --- FreeCAD preference page interface ---------------------------
    def loadSettings(self):
        self.path_edit.setText(settings.installation().path)
        self.threads_spin.setValue(min(settings.threads(), self.threads_spin.maximum()))
        self.vtk_check.setChecked(settings.convert_to_vtk())
        self.refresh()

    def saveSettings(self):
        settings.set_installation_path(self.path_edit.text().strip())
        settings.params().SetInt("Threads", self.threads_spin.value())
        settings.params().SetBool("ConvertToVtk", self.vtk_check.isChecked())

    # --- actions -------------------------------------------------------
    def installation(self):
        return radioss_runner.Installation(self.path_edit.text().strip() or radioss_runner.DEFAULT_INSTALL)

    def refresh(self):
        rows = []
        for name, ok, detail in self.installation().requisites():
            mark = f"<span style='color:{OK if ok else BAD}'>{'&#10004;' if ok else '&#10008;'}</span>"
            rows.append(f"<tr><td>{mark}</td><td>{html.escape(name)}</td>"
                        f"<td><small>{html.escape(detail)}</small></td></tr>")
        self.requisites_label.setText("<table cellspacing='4'>" + "".join(rows) + "</table>")
        self.test_label.clear()

    def browse(self):
        start = self.path_edit.text() or os.path.expanduser("~")
        path = QtWidgets.QFileDialog.getExistingDirectory(self.form, "Solver folder (contains exec/)", start)
        if path:
            self.path_edit.setText(path)

    def auto_detect(self):
        found = radioss_runner.detect_installation()
        if found is None:
            self.test_label.setText(f"<span style='color:{BAD}'>No installation found in: "
                                    f"{html.escape(', '.join(radioss_runner.candidate_paths()))}</span>")
            return
        self.path_edit.setText(found.path)

    def test_installation(self):
        self.test_label.setText("Running the starter...")
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            QtWidgets.QApplication.processEvents()
            ok, message = self.installation().test_run(kfile_format.BASIC_K_FILE)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.refresh()  # the Flatpak libraries may have been copied
        self.test_label.setText(f"<span style='color:{OK if ok else BAD}'>{html.escape(message)}</span>")
        return ok

    def download(self):
        parent = QtWidgets.QFileDialog.getExistingDirectory(
            self.form, "Folder to unpack OpenCourant into", os.path.expanduser("~"))
        if not parent:
            return
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            try:
                tag, url, size = radioss_runner.latest_release()
            finally:
                QtWidgets.QApplication.restoreOverrideCursor()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self.form, "Download OpenCourant",
                                          f"Cannot download OpenCourant:\n{e}\n\n"
                                          f"Releases: {radioss_runner.RELEASES_PAGE}")
            return
        target = os.path.join(parent, f"OpenCourant_{tag}")
        answer = QtWidgets.QMessageBox.question(
            self.form, "Download OpenCourant",
            f"Download OpenCourant {tag} ({size / 1e6:.0f} MB, AGPL-3.0) from GitHub and unpack it to\n{target}?")
        if answer != QtWidgets.QMessageBox.Yes:
            return

        progress = QtWidgets.QProgressDialog(f"Downloading OpenCourant {tag}...", "Cancel", 0, 100, self.form)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setMinimumDuration(0)

        def report(done, total):
            if total:
                progress.setValue(int(100 * done / total))
                progress.setLabelText(f"Downloading OpenCourant {tag}: {done / 1e6:.0f} of {total / 1e6:.0f} MB")
            QtWidgets.QApplication.processEvents()
            return not progress.wasCanceled()

        try:
            with tempfile.TemporaryDirectory(prefix="orfe_download_") as tmp:
                archive = radioss_runner.download(url, os.path.join(tmp, os.path.basename(url)), report)
                progress.setLabelText("Unpacking...")
                progress.setRange(0, 0)
                QtWidgets.QApplication.processEvents()
                path = radioss_runner.extract_release(archive, target)
        except Exception as e:
            progress.close()
            QtWidgets.QMessageBox.warning(self.form, "Download OpenCourant", f"Download failed:\n{e}")
            return
        progress.close()
        FreeCAD.Console.PrintMessage(f"OpenRadioss: OpenCourant {tag} unpacked to {path}\n")
        self.path_edit.setText(path)
        self.test_installation()
