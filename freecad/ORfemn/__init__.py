# FreeCAD OpenRadioss Workbench
#
# This file is part of the OpenRadioss Workbench for FreeCAD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
__url__ = "https://hexascan.de"
__license__ = "GPL-3.0-or-later"

ICONPATH = os.path.join(os.path.dirname(__file__), "resources", "icons")


def icon_path(name):
    """Return the absolute path of an SVG icon in resources/icons."""
    return os.path.join(ICONPATH, f"{name}.svg")
