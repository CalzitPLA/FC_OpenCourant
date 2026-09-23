#!/usr/bin/env python3
"""
Generate placeholder icons for the OpenRadioss workbench.
"""
import os
from pathlib import Path

# Create icons directory
icon_dir = Path(__file__).resolve().parent.parent / "freecad" / "ORfemn" / "resources" / "icons"
icon_dir.mkdir(parents=True, exist_ok=True)

# List of required icons
icons = [
    'create_model',
    'create_k_file',
    'keyword_editor',
    'template_editor',
    'export',
    'import',
    'run',
    'help',
    'ORfemn-icon'
]

# SVG template for placeholder icons
svg_template = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="64" height="64" viewBox="0 0 64 64" version="1.1">
  <rect width="60" height="60" x="2" y="2" 
        style="fill:#{color};stroke:#000000;stroke-width:2;fill-opacity:0.7" />
  <text x="32" y="38" text-anchor="middle" 
        style="font-size:10px;font-family:Arial;fill:#000000">
    {text}
  </text>
</svg>
"""

# Colors for different icons
colors = {
    'create_model': 'a0e57c',
    'create_k_file': 'c8e87c',
    'keyword_editor': '7cc4e8',
    'template_editor': 'e87cb0',
    'export': 'e8c37c',
    'import': 'e8a87c',
    'run': '7ce8b3',
    'help': 'd47ce8',
    'ORfemn-icon': '7c7ce8'
}

# Generate icons
for icon in icons:
    text = icon.replace('_', ' ').title()
    color = colors.get(icon, 'cccccc')
    svg_content = svg_template.format(color=color, text=text)
    
    with open(icon_dir / f"{icon}.svg", 'w') as f:
        f.write(svg_content)
    
    print(f"Generated icon: {icon}.svg")

print("\nAll icons have been generated in:")
print(icon_dir)
