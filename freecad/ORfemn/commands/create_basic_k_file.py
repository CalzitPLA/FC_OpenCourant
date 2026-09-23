"""
Create Basic LS-DYNA .k File command for FreeCAD.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from .. import icon_path
from ..kfile_format import BASIC_K_FILE

class CreateBasicKFile:
    """Command to create a new basic LS-DYNA .k file object in FreeCAD."""

    def GetResources(self):
        """Return a dictionary with data that will be used by the button or menu item."""
        return {
            'Pixmap': icon_path('create_k_file'),
            'MenuText': 'Create Basic .k File',
            'ToolTip': 'Create a new basic LS-DYNA .k file object',
            'CmdType': 'ForEdit'
        }

    def Activated(self):
        """Run the command to create a new basic LS-DYNA .k file object."""
        try:
            # Create a new document if none exists
            if not App.ActiveDocument:
                doc = App.newDocument("LSDyna_Model")
                doc.Label = "LS-DYNA Model"
            else:
                doc = App.ActiveDocument

            # Create the LS-DYNA keyword text object
            k_file_obj = doc.addObject("App::TextDocument", "LSDynaKeywords")
            k_file_obj.Label = "LS-DYNA Keywords"

            # Set the text content
            k_file_obj.Text = BASIC_K_FILE

            # Refresh the view
            doc.recompute()

            # Set the active workbench to OpenRadioss
            Gui.activateWorkbench("OpenRadiossWorkbench")

            # Show success message
            QtWidgets.QMessageBox.information(
                None,
                "LS-DYNA Keywords Created",
                "LS-DYNA keywords text document created successfully in the active document.\n\n"
                "You can now:\n"
                "• View the content in the Property panel (Text property)\n"
                "• Edit the content by modifying the Text property\n"
                "• Export to .k file using the Export command\n"
                "• The content is stored in the .FCStd file"
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                None,
                "Error creating LS-DYNA keywords",
                f"An error occurred while creating the LS-DYNA keywords:\n{str(e)}"
            )

    def IsActive(self):
        """Define whether the command is active or not (greyed out)."""
        # Always active as we can create a new .k file object anytime
        return True
