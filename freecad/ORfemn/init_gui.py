# FreeCAD OpenRadioss Workbench
#
# This file registers the OpenRadioss workbench with the FreeCAD GUI.

import os

import FreeCAD as App
import FreeCADGui as Gui

from . import icon_path

TRANSLATIONSPATH = os.path.join(os.path.dirname(__file__), "resources", "translations")

Gui.addLanguagePath(TRANSLATIONSPATH)
Gui.updateLocale()


class OpenRadiossWorkbench(Gui.Workbench):
    """OpenRadioss workbench class"""

    MenuText = "OpenRadioss"
    ToolTip = "OpenRadioss Workbench"
    Icon = icon_path("ORfemn-icon")

    COMMANDS = [
        "CreateRadiossModel",
        "CreateBasicKFile",
        "KeywordEditor",
        "TemplateEditor",
        "OpenCacheViewer",
        "ExportRadiossInput",
    ]

    def Initialize(self):
        """Initialize the workbench"""
        from .commands.keyword_editor_command import KeywordEditorCommand
        from .commands.create_radioss_model import CreateRadiossModel
        from .commands.export_radioss_input import ExportRadiossInput
        from .commands.create_basic_k_file import CreateBasicKFile
        from .commands.open_cache_viewer import OpenCacheViewer
        from .commands.template_editor_command import TemplateEditorCommand

        Gui.addCommand('KeywordEditor', KeywordEditorCommand())
        Gui.addCommand('CreateRadiossModel', CreateRadiossModel())
        Gui.addCommand('ExportRadiossInput', ExportRadiossInput())
        Gui.addCommand('CreateBasicKFile', CreateBasicKFile())
        Gui.addCommand('OpenCacheViewer', OpenCacheViewer())
        Gui.addCommand('TemplateEditor', TemplateEditorCommand())

        self.appendToolbar("OpenRadioss", self.COMMANDS)
        self.appendMenu("OpenRadioss", self.COMMANDS)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(OpenRadiossWorkbench())
App.Console.PrintLog("Loading OpenRadioss workbench...\n")
