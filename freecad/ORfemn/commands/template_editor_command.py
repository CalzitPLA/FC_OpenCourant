"""
Template Editor command for FreeCAD.
"""

from PySide import QtWidgets

from .. import icon_path


class TemplateEditorCommand:
    """Command to open the keyword template editor."""

    def __init__(self):
        self.dialog = None

    def GetResources(self):
        """Return a dictionary with data that will be used by the button or menu item."""
        return {
            'Pixmap': icon_path('template_editor'),
            'MenuText': 'Template Editor',
            'ToolTip': 'Create, edit and reorder the keyword templates',
            'CmdType': 'ForEdit'
        }

    def Activated(self):
        """Open the template editor (one instance at a time)."""
        from ..gui.keyword_editor import KeywordEditorDialog
        from ..gui.template_editor import TemplateEditorDialog

        if self.dialog is None or not self.dialog.isVisible():
            self.dialog = TemplateEditorDialog()
            # Keep open keyword editors in sync with saved templates
            for widget in QtWidgets.QApplication.topLevelWidgets():
                if isinstance(widget, KeywordEditorDialog):
                    self.dialog.templates_saved.connect(widget.reload_templates)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def IsActive(self):
        """Define whether the command is active or not (greyed out)."""
        return True
