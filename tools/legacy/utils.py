"""
Utility functions for the OpenRadioss workbench.
"""
import os
import sys
from pathlib import Path

def get_module_path():
    """Return the path to the current module."""
    return os.path.dirname(os.path.abspath(__file__))

def get_resources_path():
    """Return the path to the resources directory."""
    return os.path.join(get_module_path(), 'resources')

def get_icon_path(icon_name):
    """Return the full path to an icon file.
    
    Args:
        icon_name (str): Name of the icon without extension
        
    Returns:
        str: Full path to the icon file
    """
    # Try multiple possible locations
    possible_paths = [
        # Development layout
        os.path.join(get_resources_path(), 'icons', f"{icon_name}.svg"),
        # Installed layout
        os.path.join('/app/freecad/Mod/ORfe/freecad/ORfemn/resources/icons', f"{icon_name}.svg"),
        # Flatpak layout
        os.path.join(os.path.expanduser('~'), '.var/app/org.freecad.FreeCAD/data/FreeCAD/Mod/ORfe/freecad/ORfemn/resources/icons', f"{icon_name}.svg"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # If no icon is found, return None
    print(f"Warning: Could not find icon: {icon_name}.svg")
    return None
