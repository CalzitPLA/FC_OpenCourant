"""
"Solver OpenRadioss" command, available in the OpenRadioss and the FEM workbench.

The command is registered at FreeCAD start (init_gui.py) and a workbench
manipulator adds it to the FEM workbench's "Solve" toolbar and menu, next to
the built-in solvers.
"""

import FreeCAD
import FreeCADGui as Gui

from .. import icon_path

COMMAND = "FEM_SolverOpenRadioss"


class SolverOpenRadiossCommand:
    """Add an OpenRadioss solver to the active FEM analysis."""

    def GetResources(self):
        return {
            'Pixmap': icon_path('run'),
            'MenuText': 'Solver OpenRadioss',
            'ToolTip': 'Creates a FEM solver OpenRadioss (explicit dynamics) in the active analysis',
        }

    def IsActive(self):
        try:
            import FemGui
        except ImportError:
            return False
        analysis = FemGui.getActiveAnalysis()
        return analysis is not None and analysis.Document is FreeCAD.ActiveDocument

    def Activated(self):
        import FemGui
        from . import solver

        analysis = FemGui.getActiveAnalysis()
        doc = analysis.Document
        doc.openTransaction("Create SolverOpenRadioss")
        obj = solver.create(doc)
        analysis.addObject(obj)
        doc.commitTransaction()
        doc.recompute()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(obj)


class FemWorkbenchManipulator:
    """Adds the OpenRadioss solver next to the built-in FEM solvers.

    The entries are inserted relative to FEM commands, so they only appear in
    workbenches that have those commands (the FEM workbench).
    """

    def modifyToolBars(self):
        return [{"insert": COMMAND, "toolItem": "FEM_SolverCalculiXCcxTools", "after": ""}]

    def modifyMenuBar(self):
        return [{"insert": COMMAND, "menuItem": "FEM_SolverZ88", "after": ""}]


_manipulator = None


def register():
    """Register the command and the FEM workbench manipulator (once)."""
    global _manipulator
    if COMMAND not in Gui.listCommands():
        Gui.addCommand(COMMAND, SolverOpenRadiossCommand())
    if _manipulator is None and hasattr(Gui, "addWorkbenchManipulator"):
        _manipulator = FemWorkbenchManipulator()
        Gui.addWorkbenchManipulator(_manipulator)
