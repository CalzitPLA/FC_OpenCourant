"""
Keyword Editor command for FreeCAD.
"""

import FreeCADGui as Gui

from .. import icon_path


class KeywordEditorCommand:
    """Command to open the Keyword Editor dialog."""

    def __init__(self):
        self.dialogs = []

    def GetResources(self):
        """Return a dictionary with data that will be used by the button or menu item."""
        return {
            'Pixmap': icon_path('keyword_editor'),
            'MenuText': 'Keyword Editor',
            'ToolTip': 'Open the Radioss Keyword Editor',
            'CmdType': 'ForEdit'
        }
    
    def Activated(self):
        """Run the command."""
        from ..gui.keyword_editor import KeywordEditorDialog
        
        # Create and show the dialog
        dialog = KeywordEditorDialog()
        dialog.show()
        
        # Keep a reference to the dialog to prevent it from being garbage collected
        self.dialogs.append(dialog)

        # Remove the dialog from the list when it's closed
        dialog.finished.connect(lambda _result: self.dialogs.remove(dialog))
    
    def IsActive(self):
        """
        Define whether the command is active or not (greyed out).
        This function is called when the workbench is activated.
        
        Returns:
            bool: True if the command should be active, False otherwise.
        """
        # Only active when there's an active document
        return Gui.ActiveDocument is not None
