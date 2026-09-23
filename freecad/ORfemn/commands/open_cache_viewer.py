"""
Open LS-DYNA Cache Viewer command for FreeCAD.
"""

from PySide import QtWidgets

from .. import icon_path


class OpenCacheViewer:
    """Command to open the LS-DYNA cache viewer window."""

    def GetResources(self):
        """Return a dictionary with data that will be used by the button or menu item."""
        return {
            'Pixmap': icon_path('import'),
            'MenuText': 'Open Cache Viewer',
            'ToolTip': 'Open the LS-DYNA keyword cache viewer',
            'CmdType': 'ForEdit'
        }

    def Activated(self):
        """Open the cache viewer of an open keyword editor."""
        from ..gui.keyword_editor import KeywordEditorDialog

        editor = next((w for w in QtWidgets.QApplication.topLevelWidgets()
                       if isinstance(w, KeywordEditorDialog) and w.isVisible()), None)

        if editor is None or not editor.keyword_cache:
            QtWidgets.QMessageBox.information(
                None,
                "No Cache Found",
                "No cached keywords found.\n\n"
                "Use the Keyword Editor to generate and cache some keywords first."
            )
            return

        editor.open_cache_viewer()

    def IsActive(self):
        """Define whether the command is active or not (greyed out)."""
        return True
