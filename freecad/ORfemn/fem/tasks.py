"""Check / Prepare / Solve / Results tasks of the OpenRadioss FEM solver."""

import os
import subprocess

import FreeCAD

from femsolver import run
from femtools import femutils

from .. import radioss_runner
from . import deck_writer, model

JOB_NAME = "radioss"
RESULT_PREFIX = "OpenRadiossResult"


def installation():
    path = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/ORfemn").GetString(
        "OpenRadiossPath", radioss_runner.DEFAULT_INSTALL)
    return radioss_runner.Installation(path)


class Check(run.Check):
    def run(self):
        self.pushStatus("Checking analysis members...\n")
        self.check_mesh_exists()
        self.check_material_exists()
        self.checkSupported([(t,) for t in model.SUPPORTED_CONSTRAINTS])
        problems = installation().problems()
        if problems:
            self.report.error("; ".join(problems) + ". Set the OpenRadioss folder in the 'Run OpenRadioss' dialog "
                              "of the OpenRadioss workbench (default ~/OpenRadioss).")
            self.fail()


class Prepare(run.Prepare):
    def run(self):
        self.pushStatus("Writing OpenRadioss deck...\n")
        try:
            deck_model, warnings = model.build_model(self.analysis, self.solver)
        except model.ModelError as e:
            self.report.error(str(e))
            self.fail()
            return
        for warning in warnings:
            self.report.warning(warning)
            self.pushStatus(f"Warning: {warning}\n")
        # Results of an earlier run in this directory would be mixed into the new ones
        for f in os.listdir(self.directory):
            if radioss_runner.is_result_file(f, JOB_NAME):
                os.remove(os.path.join(self.directory, f))
        path = os.path.join(self.directory, JOB_NAME + ".k")
        with open(path, "w") as f:
            f.write(deck_writer.write_deck(deck_model))
        n_elements = sum(len(p["elements"]) for p in deck_model["parts"])
        self.pushStatus(f"Deck written: {path} ({n_elements} elements, {len(deck_model['parts'])} parts)\n")


class Solve(run.Solve):
    def run(self):
        inst = installation()
        copied = inst.prepare_flatpak()
        if copied:
            self.pushStatus(f"Copied host libraries for the Flatpak sandbox: {', '.join(copied)}\n")
        threads = int(self.solver.Threads)
        env = inst.environment(threads)
        deck = os.path.join(self.directory, JOB_NAME + ".k")

        self.pushStatus("Running OpenRadioss starter...\n")
        if not self._execute(inst.starter_command(deck, threads), env) and not self.aborted:
            listing = os.path.join(self.directory, f"{JOB_NAME}_0000.out")
            for message in radioss_runner.listing_messages(listing):
                self.report.error(message)
            self.report.error(f"The starter failed, see {listing}")
            self.fail()
            return
        errors, warnings = radioss_runner.listing_summary(os.path.join(self.directory, f"{JOB_NAME}_0000.out"))
        self.pushStatus(f"\nStarter: {errors} errors, {warnings} warnings\n")
        if errors:
            self.report.error(f"The starter found {errors} error(s) in the deck.")
            self.fail()
            return

        for engine_input in radioss_runner.engine_inputs(self.directory, JOB_NAME):
            if self.aborted:
                return
            self.pushStatus(f"Running OpenRadioss engine ({os.path.basename(engine_input)})...\n")
            ok = self._execute(inst.engine_command(engine_input, threads), env)
            out = os.path.splitext(engine_input)[0] + ".out"
            if self.aborted:
                return
            if not ok or not radioss_runner.normal_termination(out):
                self.report.error(f"The engine did not terminate normally, see {out}")
                self.fail()
                return

        animations = radioss_runner.animation_files(self.directory, JOB_NAME)
        self.pushStatus(f"\nConverting {len(animations)} result frames to VTK...\n")
        frames = []
        for animation in animations:
            if self.aborted:
                return
            frames.append(radioss_runner.convert_animation(inst, animation, env, self.directory))
        if frames:
            radioss_runner.write_pvd(frames, os.path.join(self.directory, JOB_NAME + ".pvd"))
        self.pushStatus(f"Done: {len(frames)} frames, series {JOB_NAME}.pvd\n")

    def _execute(self, argv, env):
        """Run a solver step, stream its output to the status; returns True on exit code 0."""
        process = subprocess.Popen(argv, cwd=self.directory, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.signalAbort.add(process.terminate)
        try:
            self._observeSolver(process)
            process.wait()
        finally:
            self.signalAbort.remove(process.terminate)
        return process.returncode == 0


class Results(run.Results):
    def run(self):
        frames = sorted(f for f in os.listdir(self.directory)
                        if f.startswith(JOB_NAME + "A") and f.endswith(".vtu"))
        if not frames:
            self.report.error("No result frames found.")
            self.fail()
            return
        prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Fem/General")
        doc = self.analysis.Document
        if not prefs.GetBool("KeepResultsOnReRun", False):
            for obj in list(self.analysis.Group):
                if femutils.is_of_type(obj, "Fem::FemPostPipeline") and obj.Name.startswith(RESULT_PREFIX):
                    doc.removeObject(obj.Name)
        last = os.path.join(self.directory, frames[-1])
        pipeline = doc.addObject("Fem::FemPostPipeline", RESULT_PREFIX)
        pipeline.read(last)
        end_time = self.solver.EndTime.getValueAs("s").Value  # UserString rounds to 2 decimals
        pipeline.Label = f"{RESULT_PREFIX} (t = {end_time:g} s)"
        self.analysis.addObject(pipeline)
        doc.recompute()
        self.pushStatus(f"Loaded {frames[-1]} into '{pipeline.Label}'. "
                        f"All {len(frames)} frames: {os.path.join(self.directory, JOB_NAME + '.pvd')}\n")
