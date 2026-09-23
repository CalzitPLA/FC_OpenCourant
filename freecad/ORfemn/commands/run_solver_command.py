"""
Run OpenRadioss command for FreeCAD.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from .. import icon_path


def k_text_objects(doc):
    """Text documents of ``doc`` that contain keyword text."""
    return [obj for obj in doc.Objects
            if obj.TypeId == 'App::TextDocument' and obj.Text.lstrip().startswith(('*', '$'))]


class RunSolverCommand:
    """Run OpenRadioss on an LS-DYNA keyword text object of the active document."""

    def __init__(self):
        self.dialogs = []

    def GetResources(self):
        return {
            'Pixmap': icon_path('run'),
            'MenuText': 'Run OpenRadioss',
            'ToolTip': 'Run OpenRadioss (starter, engine, VTK conversion) on a LS-DYNA keyword text object',
            'CmdType': 'ForEdit'
        }

    def Activated(self):
        from .export_radioss_input import ExportRadiossInput
        from ..gui.run_dialog import RunDialog

        doc = App.ActiveDocument
        candidates = k_text_objects(doc)
        selected = [obj for obj in Gui.Selection.getSelection() if obj in candidates]
        if selected:
            obj = selected[0]
        elif len(candidates) == 1:
            obj = candidates[0]
        elif candidates:
            obj = ExportRadiossInput()._select_k_file_object(candidates)
        else:
            QtWidgets.QMessageBox.information(
                None, "Run OpenRadioss",
                "No LS-DYNA keyword text object found in the active document.\n\n"
                "Use 'Create Basic .k File' or the Keyword Editor ('Update .k File') first.")
            return
        if obj is None:
            return

        dialog = RunDialog(obj.Text, obj.Label, doc, Gui.getMainWindow())
        self.dialogs.append(dialog)
        dialog.finished.connect(lambda _result: self.dialogs.remove(dialog) if dialog in self.dialogs else None)
        dialog.show()

    def IsActive(self):
        return App.ActiveDocument is not None
