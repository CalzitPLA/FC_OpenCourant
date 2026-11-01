# SPDX-License-Identifier: LGPL-2.1-or-later
"""Open Edit > Preferences > OpenRadioss from the workbench menu."""

import FreeCADGui as Gui

from .. import icon_path


class PreferencesCommand:
    def GetResources(self):
        return {
            'Pixmap': icon_path('preferences-openradioss'),
            'MenuText': 'OpenRadioss Preferences...',
            'ToolTip': 'Solver folder, requirements check and OpenCourant download',
        }

    def Activated(self):
        Gui.showPreferences("OpenRadioss")

    def IsActive(self):
        return True
