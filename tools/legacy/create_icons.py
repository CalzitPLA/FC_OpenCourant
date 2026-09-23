#!/usr/bin/env python3
"""
Script to create placeholder icons for the OpenRadioss workbench.
Run this script to generate the required SVG icons.
"""
import os
from pathlib import Path

# Create icons directory if it doesn't exist
icon_dir = Path(__file__).parent / 'icons'
icon_dir.mkdir(exist_ok=True)

# List of required icons
icons = [
    'create_model.svg',
    'keyword_editor.svg',
    'export.svg',
    'import.svg',
    'run.svg',
    'help.svg',
    'ORfemn-icon.svg'
]

# Simple SVG template for placeholder icons
svg_template = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg
   width="64"
   height="64"
   viewBox="0 0 64 64"
   version="1.1"
   id="svg1">
  <rect
     width="60"
     height="60"
     x="2"
     y="2"
     style="fill:#{bg_color};fill-opacity:1;stroke:#000000;stroke-width:2" />
  <text
     x="32"
     y="38"
     text-anchor="middle"
     style="font-size:14px;font-family:Arial;fill:#000000">
    {text}
  </text>
</svg>
"""

# Colors for different icons
icon_colors = {
    'create_model': 'a0e57c',
    'keyword_editor': '7cc4e8',
    'export': 'e8c37c',
    'import': 'e8a87c',
    'run': '7ce8b3',
    'help': 'd47ce8',
    'ORfemn-icon': '7c7ce8'
}

# Create each icon
for icon in icons:
    icon_name = icon.replace('.svg', '')
    bg_color = icon_colors.get(icon_name, 'cccccc')
    text = icon_name.replace('_', ' ').title()
    
    with open(icon_dir / icon, 'w') as f:
        f.write(svg_template.format(bg_color=bg_color, text=text))
    
    print(f"Created icon: {icon}")

print("\nAll icons created successfully!")
