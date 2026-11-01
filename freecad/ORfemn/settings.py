# SPDX-License-Identifier: LGPL-2.1-or-later
"""Workbench settings (Edit > Preferences > OpenRadioss), shared by the Run dialog and the FEM solver."""

import FreeCAD

from . import radioss_runner

PARAMS = "User parameter:BaseApp/Preferences/Mod/ORfemn"


def params():
    return FreeCAD.ParamGet(PARAMS)


def configured_path():
    """The solver folder set in the preferences ('' if none)."""
    return params().GetString("OpenRadiossPath", "")


def installation():
    """The solver installation to use.

    The configured folder if it is usable, otherwise the first usable folder found
    automatically (``radioss_runner.candidate_paths``), otherwise the configured
    or default folder, whose problems are then reported to the user.
    """
    path = configured_path()
    if path:
        configured = radioss_runner.Installation(path)
        if not configured.problems():
            return configured
    found = radioss_runner.detect_installation()
    if found is not None:
        return found
    return radioss_runner.Installation(path or radioss_runner.DEFAULT_INSTALL)


def set_installation_path(path):
    params().SetString("OpenRadiossPath", path)


def threads(default=2):
    return params().GetInt("Threads", default)


def convert_to_vtk():
    return params().GetBool("ConvertToVtk", True)
