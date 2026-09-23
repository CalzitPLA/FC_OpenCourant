# FreeCAD OpenRadioss Workbench
# (c) 2023 Your Name
#

import os
import sys
import json
from pathlib import Path

# Import FreeCAD first to ensure Qt bindings are properly loaded
import FreeCAD as App
import FreeCADGui as Gui

# Import Qt through FreeCAD's wrapper
from PySide import QtCore, QtGui, QtWidgets

# For compatibility, ensure we're using the same Qt version as FreeCAD
if not hasattr(QtCore, 'QItemSelectionModel'):
    # Try to import from PySide2 if PySide doesn't have QItemSelectionModel
    try:
        from PySide2 import QtCore, QtGui, QtWidgets
    except ImportError:
        # Fall back to PySide6 if PySide2 is not available
        try:
            from PySide6 import QtCore, QtGui, QtWidgets
        except ImportError as e:
            App.Console.PrintError(f"Failed to import Qt bindings: {e}\n")
            raise

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import local modules
try:
    from . import utils
    from .gui.keyword_editor import KeywordEditorDialog
except ImportError as e:
    App.Console.PrintError(f"Error importing modules: {str(e)}\n")
    # Create a dummy class to prevent further errors
    class KeywordEditorDialog:
        def __init__(self, *args, **kwargs):
            pass
        def exec_(self):
            App.Console.PrintError("KeywordEditorDialog failed to load\n")

# Translation function
def translate(context, text):
    try:
        return App.Qt.translate(context, text)
    except Exception as e:
        return text

# Create _ function for backward compatibility
_ = lambda text: translate("ORfemn", text)

class CreateRadiossModel:
    """Create a new OpenRadioss model"""
    
    def GetResources(self):
        return {
            'Pixmap': os.path.join(os.path.dirname(__file__), "resources", "icons", "create_model.svg"),
            'MenuText': _("Create New Model"),
            'ToolTip': _("Create a new OpenRadioss model"),
            'Accel': ""
        }
    
    def Activated(self):
        """Execute when the command is clicked"""
        doc = App.ActiveDocument
        if not doc:
            doc = App.newDocument()
        
        # Create a new OpenRadioss model object
        obj = doc.addObject("App::DocumentObjectGroup", "OpenRadioss_Model")
        obj.Label = "OpenRadioss Model"
        
        # Add some default properties
        obj.addProperty("App::PropertyString", "ModelName", "Model", "Name of the model").ModelName = "NewModel"
        obj.addProperty("App::PropertyLength", "LengthUnit", "Units", "Length unit").LengthUnit = 1.0  # meters
        obj.addProperty("App::PropertyLength", "TimeUnit", "Units", "Time unit").TimeUnit = 1.0  # seconds
        obj.addProperty("App::PropertyLength", "MassUnit", "Units", "Mass unit").MassUnit = 1.0  # kg
        
        App.Console.PrintMessage("Created new OpenRadioss model\n")
        doc.recompute()
        
    def IsActive(self):
        """Return True if the command is active"""
        return True

class ExportRadiossInput:
    """Export model to OpenRadioss input files"""
    
    def GetResources(self):
        return {
            'Pixmap': os.path.join(os.path.dirname(__file__), "resources", "icons", "export.svg"),
            'MenuText': _("Export to OpenRadioss"),
            'ToolTip': _("Export model to OpenRadioss input files"),
            'Accel': ""
        }
    
    def Activated(self):
        """Execute when the command is clicked"""
        # Get the active document
        doc = App.ActiveDocument
        if not doc:
            QtGui.QMessageBox.critical(None, "Error", "No active document")
            return
        
        # Ask for output directory
        output_dir = QtGui.QFileDialog.getExistingDirectory(
            None, 
            _("Select output directory for OpenRadioss files"),
            os.path.expanduser("~")
        )
        
        if not output_dir:
            return  # User cancelled
            
        try:
            # TODO: Implement actual export logic
            # This is a placeholder for the export functionality
            with open(os.path.join(output_dir, "model_0001.rad"), 'w') as f:
                f.write("*KEYWORD\n")
                f.write("*TITLE\n")
                f.write("OpenRadioss model exported from FreeCAD\n")
                f.write("*END")
            
            App.Console.PrintMessage(f"Exported OpenRadioss files to {output_dir}\n")
            
        except Exception as e:
            QtGui.QMessageBox.critical(None, "Export Error", f"Failed to export: {str(e)}")
    
    def IsActive(self):
        """Return True if there's a document to export"""
        return App.ActiveDocument is not None

class ImportRadiossResults:
    """Import OpenRadioss results into FreeCAD"""
    
    def GetResources(self):
        return {
            'Pixmap': os.path.join(os.path.dirname(__file__), "resources", "icons", "import.svg"),
            'MenuText': _("Import Results"),
            'ToolTip': _("Import OpenRadioss results into FreeCAD"),
            'Accel': ""
        }
    
    def Activated(self):
        """Execute when the command is clicked"""
        # TODO: Implement results import
        App.Console.PrintMessage("Importing OpenRadioss results...\n")
        
    def IsActive(self):
        return True

class RunRadioss:
    """Run OpenRadioss simulation"""
    
    def GetResources(self):
        return {
            'Pixmap': os.path.join(os.path.dirname(__file__), "resources", "icons", "run.svg"),
            'MenuText': _("Run Simulation"),
            'ToolTip': _("Run OpenRadioss simulation"),
            'Accel': ""
        }
    
    def Activated(self):
        """Execute when the command is clicked"""
        # TODO: Implement running OpenRadioss
        App.Console.PrintMessage("Running OpenRadioss simulation...\n")
        
    def IsActive(self):
        return True

class ShowRadiossHelp:
    """Show OpenRadioss help"""
    
    def GetResources(self):
        return {
            'Pixmap': os.path.join(os.path.dirname(__file__), "resources", "icons", "help.svg"),
            'MenuText': _("Help"),
            'ToolTip': _("Show OpenRadioss help"),
            'Accel': ""
        }
    
    def Activated(self):
        """Execute when the command is clicked"""
        # TODO: Implement help dialog
        QtGui.QMessageBox.information(
            None,
            _("OpenRadioss Workbench Help"),
            _("OpenRadioss Workbench Help\n\n"
              "This workbench provides tools for working with OpenRadioss in FreeCAD.\n\n"
              "1. Create a new model\n"
              "2. Define materials, properties, and boundary conditions\n"
              "3. Export to OpenRadioss input files\n"
              "4. Run the simulation\n"
              "5. Import and visualize results")
        )
    
    def IsActive(self):
        return True

class KeywordEditor:
    """Open the Radioss Keyword Editor"""
    
    def GetResources(self):
        return {
            'Pixmap': os.path.join(os.path.dirname(__file__), "resources", "icons", "keyword_editor.svg"),
            'MenuText': _("Keyword Editor"),
            'ToolTip': _("Open the Radioss Keyword Editor"),
            'Accel': ""
        }
    
    def Activated(self):
        """Execute when the command is clicked"""
        # Create and show the keyword editor dialog
        dialog = KeywordEditorDialog()
        dialog.show()
        
        # Center the dialog on the FreeCAD window
        mw = Gui.getMainWindow()
        if mw:
            dialog.move(
                mw.frameGeometry().center() - dialog.rect().center()
            )
    
    def IsActive(self):
        """Only active when there's a document"""
        return bool(App.ActiveDocument)


class KeywordEditorDialog(QtWidgets.QDialog):
    """Dialog for editing Radioss keywords"""
    
    def __init__(self, parent=None):
        super(KeywordEditorDialog, self).__init__(parent)
        self.keywords = []
        self.setup_ui()
        self.load_keywords()
    
    def setup_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Radioss Keyword Editor")
        self.setMinimumSize(800, 600)
        
        # Create main layout
        layout = QtWidgets.QVBoxLayout(self)
        
        # Create splitter
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        # Left panel - Keyword list
        self.keyword_list = QtWidgets.QListWidget()
        self.keyword_list.itemSelectionChanged.connect(self.on_keyword_selected)
        
        # Right panel - Keyword details
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        
        # Keyword name
        self.keyword_name = QtWidgets.QLabel("Select a keyword")
        right_layout.addWidget(self.keyword_name)
        
        # Parameter table
        self.param_table = QtWidgets.QTableWidget(0, 2)
        self.param_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.param_table.horizontalHeader().setStretchLastSection(True)
        right_layout.addWidget(self.param_table)
        
        # Add panels to splitter
        splitter.addWidget(self.keyword_list)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        # Add buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        # Add everything to main layout
        layout.addWidget(splitter)
        layout.addWidget(button_box)
    
    def load_keywords(self):
        """Load keywords from the JSON file"""
        try:
            json_path = os.path.join(
                os.path.dirname(__file__), 
                "lsdyna_keywords_cleaned.json"
            )
            with open(json_path, 'r') as f:
                self.keywords = json.load(f)
            
            # Populate the keyword list
            self.keyword_list.clear()
            for keyword in self.keywords:
                self.keyword_list.addItem(keyword.get('name', 'Unnamed'))
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, 
                "Error", 
                f"Failed to load keywords: {str(e)}"
            )
            self.keywords = []
    
    def on_keyword_selected(self):
        """Update the parameter table when a keyword is selected"""
        current_item = self.keyword_list.currentItem()
        if not current_item:
            return
        
        keyword_name = current_item.text()
        keyword = next((k for k in self.keywords if k.get('name') == keyword_name), None)
        if not keyword:
            return
        
        self.keyword_name.setText(keyword_name)
        
        # Clear and set up the table
        self.param_table.setRowCount(0)
        
        # Add parameters to the table
        for param in keyword.get('parameters', []):
            row = self.param_table.rowCount()
            self.param_table.insertRow(row)
            
            # Parameter name
            name_item = QtWidgets.QTableWidgetItem(param.get('name', ''))
            name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.param_table.setItem(row, 0, name_item)
            
            # Parameter value
            value_item = QtWidgets.QTableWidgetItem(param.get('default', ''))
            self.param_table.setItem(row, 1, value_item)
    
    def update_keyword_list(self, search_text=""):
        """Update the list of keywords based on filters"""
        self.keyword_list.clear()
        
        for kw in self.keywords:
            kw_category = kw.get('category', '')
            kw_name = kw.get('name', '')
            kw_desc = kw.get('description', '')
            
            # Apply search filter
            if search_text and (search_text not in kw_name.lower() and 
                              search_text not in kw_desc.lower() and
                              search_text not in kw_category.lower()):
                continue
            
            # Add matching keyword to the list
            self.keyword_list.addItem(kw_name)
    
    def load_keyword_details(self, item):
        """Load details of the selected keyword"""
        if not item:
            return
            
        keyword_name = item.text()
        keyword = next((k for k in self.keywords if k.get('name') == keyword_name), None)
        if not keyword:
            return
            
        # Format the keyword details
        text = f"<h2>{keyword.get('name', '')}</h2>"
        text += f"<p><b>Category:</b> {keyword.get('category', '')}</p>"
        text += f"<p><b>Description:</b> {keyword.get('description', '')}</p>"
        
        # Add parameters
        params = keyword.get('parameters', [])
        if params:
            text += "<p><b>Parameters:</b></p><ul>"
            for param in params:
                text += f"<li><b>{param.get('name', '')}</b>: {param.get('description', '')} "
                if 'default' in param:
                    text += f"(default: {param['default']})"
                text += "</li>"
            text += "</ul>"
        
        # Set the formatted text to the details widget
        if hasattr(self, 'keyword_details'):
            self.keyword_details.setHtml(text)
    
    def edit_keyword(self):
        """Edit the currently selected keyword"""
        current_item = self.keyword_list.currentItem()
        if not current_item:
            return
            
        keyword_name = current_item.text()
        keyword = next((k for k in self.keywords if k.get('name') == keyword_name), None)
        if not keyword:
            return
        if not kw:
            return
        
        # Here you would implement the actual editing functionality
        # For now, just show a message
        QtGui.QMessageBox.information(
            self,
            "Edit Keyword",
            f"Editing keyword: {kw.get('name', '')}\n\n"
            "This would open an editor for the selected keyword."
        )


# Add commands to FreeCAD
Gui.addCommand('CreateRadiossModel', CreateRadiossModel())
Gui.addCommand('ExportRadiossInput', ExportRadiossInput())
Gui.addCommand('ImportRadiossResults', ImportRadiossResults())
Gui.addCommand('RunRadioss', RunRadioss())
Gui.addCommand('ShowRadiossHelp', ShowRadiossHelp())
Gui.addCommand('KeywordEditor', KeywordEditor())
