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

# SVG template: coloured tile with a short bold label, readable at toolbar size
svg_template = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="64" height="64" viewBox="0 0 64 64" version="1.1" xmlns="http://www.w3.org/2000/svg">
  <rect width="60" height="60" x="2" y="2" rx="10" ry="10"
        style="fill:#{color};stroke:#222222;stroke-width:3" />
  <text x="32" y="{baseline}" text-anchor="middle"
        style="font-size:{size}px;font-weight:bold;font-family:DejaVu Sans,Arial,sans-serif;fill:#111111">{text}</text>
</svg>
"""

# Short labels (1-3 characters) so the icons stay readable when scaled down
labels = {
    'create_model': 'M',
    'create_k_file': '.k',
    'keyword_editor': '*K',
    'template_editor': 'T',
    'export': 'EX',
    'import': 'C',
    'run': 'R',
    'help': '?',
    'ORfemn-icon': 'OR',
}

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
    text = labels.get(icon, icon[:2].upper())
    size = 38 if len(text) == 1 else 30 if len(text) == 2 else 22
    color = colors.get(icon, 'cccccc')
    svg_content = svg_template.format(color=color, text=text, size=size, baseline=32 + size * 0.36)
    
    with open(icon_dir / f"{icon}.svg", 'w') as f:
        f.write(svg_content)
    
    print(f"Generated icon: {icon}.svg")

print("\nAll icons have been generated in:")
print(icon_dir)
