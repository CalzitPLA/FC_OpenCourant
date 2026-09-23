"""The OpenRadioss solver object of the FreeCAD FEM workbench."""

import glob
import os

import FreeCAD

from femsolver import run, solverbase
from femtools import femutils

from .. import icon_path
from . import tasks

ANALYSIS_TYPES = ["explicit"]
LOAD_CURVES = ["Ramp", "Constant"]


def create(doc, name="SolverOpenRadioss"):
    return femutils.createObject(doc, name, Proxy, ViewProxy)


class Proxy(solverbase.Proxy):
    """Explicit dynamic analysis with OpenRadioss."""

    Type = "Fem::SolverOpenRadioss"

    def __init__(self, obj):
        super().__init__(obj)
        obj.Proxy = self
        self.add_properties(obj)

    def onDocumentRestored(self, obj):
        self.add_properties(obj)  # documents saved by older versions get new/converted properties

    @staticmethod
    def add_properties(obj):
        def add(prop_type, name, group, doc, value):
            if not hasattr(obj, name):
                obj.addProperty(prop_type, name, group, doc)
                setattr(obj, name, value)

        if not hasattr(obj, "AnalysisType"):
            obj.addProperty("App::PropertyEnumeration", "AnalysisType", "Fem", "Type of the analysis")
            obj.AnalysisType = ANALYSIS_TYPES
            obj.AnalysisType = ANALYSIS_TYPES[0]
        add("App::PropertyTime", "EndTime", "OpenRadioss",
            "Simulated time. Explicit solvers need small time steps: keep it short or use mass scaling", "0.01 s")
        add("App::PropertyIntegerConstraint", "OutputFrames", "OpenRadioss",
            "Number of result frames written over the simulated time", (20, 1, 10000, 1))
        if not hasattr(obj, "LoadCurve"):
            obj.addProperty("App::PropertyEnumeration", "LoadCurve", "OpenRadioss",
                            "Ramp: loads grow linearly from 0 to full over the end time (quasi-static); "
                            "Constant: loads act fully from the start (impact-like)")
            obj.LoadCurve = LOAD_CURVES
            obj.LoadCurve = LOAD_CURVES[0]
        old_mass_scaling = None
        if hasattr(obj, "MassScalingTimeStep"):
            # earlier versions stored a time quantity, which the property view rounds to "0,00 s"
            old_mass_scaling = obj.MassScalingTimeStep.getValueAs("s").Value
            obj.removeProperty("MassScalingTimeStep")
        add("App::PropertyFloat", "MassScalingMicroseconds", "OpenRadioss",
            "Mass scaling time step in microseconds (0 = off). Mass is added where needed so the time step "
            "stays at least this value: much faster runs, check the added mass in the listing", 0.0)
        if old_mass_scaling is not None:
            obj.MassScalingMicroseconds = old_mass_scaling * 1e6
        add("App::PropertyIntegerConstraint", "Threads", "OpenRadioss", "Threads used by starter and engine",
            (min(4, os.cpu_count() or 1), 1, max(1, os.cpu_count() or 1), 1))
        add("App::PropertyLink", "AdditionalKeywords", "OpenRadioss",
            "Text document with extra LS-DYNA keywords appended to the deck (e.g. from the Keyword Editor)", None)

    def createMachine(self, obj, directory, testmode=False):
        return run.Machine(
            solver=obj,
            directory=directory,
            check=tasks.Check(),
            prepare=tasks.Prepare(),
            solve=tasks.Solve(),
            results=tasks.Results(),
            testmode=testmode,
        )

    def editSupported(self):
        return True

    def edit(self, directory):
        decks = glob.glob(os.path.join(directory, "*.k"))
        if not decks:
            FreeCAD.Console.PrintError(f"No deck written yet in {directory}\n")
            return
        import FemGui
        FemGui.open(decks[0])

    def execute(self, obj):
        return


class ViewProxy(solverbase.ViewProxy):
    def getIcon(self):
        return icon_path("run")
