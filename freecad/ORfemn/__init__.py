# SPDX-License-Identifier: LGPL-2.1-or-later
# FreeCAD OpenRadioss Workbench
#
# This file is part of the OpenRadioss Workbench for FreeCAD
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see <https://www.gnu.org/licenses/>.

"""
OpenRadioss Workbench for FreeCAD.

This workbench provides tools for working with OpenRadioss within FreeCAD.
The workbench itself is registered in init_gui.py; this module must stay
importable without the FreeCAD GUI.
"""

import os

from .version import __version__

__title__ = "OpenRadioss Workbench"
__author__ = "Nicholas Herrmann"
__url__ = "https://github.com/CalzitPLA/ORfe"
__license__ = "LGPL-2.1-or-later"

ICONPATH = os.path.join(os.path.dirname(__file__), "resources", "icons")


def icon_path(name):
    """Return the absolute path of an SVG icon in resources/icons."""
    return os.path.join(ICONPATH, f"{name}.svg")
