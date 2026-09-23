#!/usr/bin/env python3
"""
Clean the LS-DYNA keywords JSON file by removing copyrighted content and adding documentation links.
"""

import os
import re
import json
import urllib.parse
from pathlib import Path

def clean_keywords(input_path, output_path):
    """Clean the keywords JSON file."""
    print(f"Loading keywords from {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        keywords = json.load(f)
    
    cleaned_keywords = []
    base_url = "https://2021.help.altair.com/2021/hwsolvers/rad/topics/solvers/rad"
    
    for kw in keywords:
        # Clean and validate keyword name
        kw_name = kw.get('name', '').strip()
        if not kw_name:
            continue
            
        # Generate documentation URL
        doc_url = generate_documentation_url(kw_name, base_url)
        
        # Create a clean keyword entry
        cleaned = {
            'id': kw.get('id'),
            'name': kw_name,
            'category': clean_category(kw.get('category', 'UNCATEGORIZED')),
            'description': clean_description(kw.get('description', '')),
            'documentation': doc_url
        }
        
        # Clean and add parameters if they exist
        if 'parameters' in kw and kw['parameters']:
            cleaned['parameters'] = clean_parameters(kw['parameters'])
        
        cleaned_keywords.append(cleaned)
    
    # Sort keywords by ID for consistent output
    cleaned_keywords.sort(key=lambda x: x.get('id', 0))
    
    # Save the cleaned data
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_keywords, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(cleaned_keywords)} cleaned keywords to {output_path}")

def clean_description(desc):
    """Clean up the description text."""
    if not desc or not isinstance(desc, str):
        return "No description available."
    
    # Remove LS-DYNA Input Interface Keyword prefix if present
    if 'LS-DYNA Input Interface Keyword' in desc:
        desc = desc.split('LS-DYNA Input Interface Keyword', 1)[-1].strip()
    
    # Remove any copyright notices and other unwanted text
    unwanted_patterns = [
        r'©.*?All Rights Reserved[^\n]*',
        r'Intellectual Property Rights Notice\|.*',
        r'\[.*?\]',  # Remove anything in square brackets (often units or references)
        r'\s+',      # Normalize whitespace
    ]
    
    for pattern in unwanted_patterns:
        desc = re.sub(pattern, ' ', desc, flags=re.IGNORECASE)
    
    # Clean up any remaining special characters and normalize whitespace
    desc = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', desc)  # Remove control characters
    desc = re.sub(r'\s+', ' ', desc).strip()
    
    # Capitalize first letter and ensure it ends with a period
    if desc:
        desc = desc[0].upper() + desc[1:]
        if not desc.endswith(('.', '!', '?')):
            desc += '.'
    
    # Truncate very long descriptions
    max_length = 500
    if len(desc) > max_length:
        desc = desc[:max_length].rsplit(' ', 1)[0] + '...'
    
    return desc or "No description available."

def clean_category(category):
    """Clean and format the category name."""
    if not category:
        return 'UNCATEGORIZED'
    
    # Remove any version numbers or special markers
    category = re.sub(r'\s*\(.*\)', '', category)  # Remove anything in parentheses
    category = category.strip()
    
    # Convert to title case if it's all uppercase
    if category.isupper():
        category = category.title()
    
    return category or 'UNCATEGORIZED'

def clean_parameters(parameters):
    """Clean and validate parameters list."""
    if not parameters or not isinstance(parameters, list):
        return []
    
    cleaned_params = []
    for param in parameters:
        if not isinstance(param, dict):
            continue
            
        param_name = param.get('name', '').strip()
        if not param_name:
            continue
            
        cleaned_params.append({'name': param_name})
    
    return cleaned_params

# List of valid keywords for documentation links
VALID_KEYWORDS = {
    '*AIRBAG_SIMPLE_AIRBAG_MODEL', '*AIRBAG_SIMPLE_PRESSURE_VOLUME',
    '*BOUNDARY_PRESCRIBED_MOTION', '*BOUNDARY_SPC',
    '*CONSTRAINED_EXTRA_NODES', '*CONSTRAINED_JOINT',
    '*CONSTRAINED_NODAL_RIGID_BODY', '*CONSTRAINED_RIGID_BODIES',
    '*CONSTRAINED_SPOTWELD', '*CONTACT_AUTOMATIC_GENERAL',
    '*CONTACT_AUTOMATIC_NODES_TO_SURFACE', '*CONTACT_AUTOMATIC_SINGLE_SURFACE',
    '*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE', '*CONTACT_INTERIOR',
    '*CONTACT_SPOTWELD', '*CONTACT_TIED', '*CONTROL_TERMINATION',
    '*CONTROL_TIMESTEP', '*CONTROL_UNIT', '*DATABASE',
    '*DATABASE_BINARY_D3PLOT', '*DATABASE_BINARY_RUNRSF',
    '*DATABASE_CROSS_SECTION_PLANE', '*DATABASE_CROSS_SECTION_SET',
    '*DATABASE_EXTENT_BINARY', '*DATABASE_HISTORY',
    '*DATABASE_HISTORY_NODE', '*DEFINE_BOX',
    '*DEFINE_COORDINATE_NODES', '*DEFINE_COORDINATE_SYSTEM',
    '*DEFINE_COORDINATE_VECTOR', '*DEFINE_CURVE',
    '*DEFINE_SD_ORIENTATION', '*DEFINE_TABLE',
    '*DEFINE_VECTOR', '*ELEMENT_BEAM',
    '*ELEMENT_DISCRETE', '*ELEMENT_MASS',
    '*ELEMENT_MASS_PART', '*ELEMENT_SEATBELT_ACCELEROMETER',
    '*ELEMENT_SHELL', '*ELEMENT_SOLID',
    '*INITIAL_VELOCITY', '*INITIAL_VELOCITY_GENERATION',
    '*INITIAL_VELOCITY_NODE', '*KEYWORD',
    '*LOAD_BODY', '*LOAD_NODE',
    '*MAT_001 (ELASTIC)', '*MAT_002 (ORTHOTROPIC_ELASTIC)',
    '*MAT_003 (PLASTIC_KINEMATIC)', '*MAT_006 (VISCOELASTIC)',
    '*MAT_007 (BLATZ_KO_RUBBER)', '*MAT_009 (NULL)',
    '*MAT_015 (JOHNSON_COOK)', '*MAT_018 (POWER_LAW_PLASTICITY)',
    '*MAT_020 (RIGID)', '*MAT_024 (PIECEWISE_LINEAR_PLASTICITY)',
    '*MAT_026 (HONEYCOMB)', '*MAT_027 (MOONEY-RIVLIN_RUBBER)',
    '*MAT_032 (LAMINATED_GLASS)', '*MAT_034 (FABRIC)',
    '*MAT_057 (LOW_DENSITY_FOAM)', '*MAT_061 (KELVIN_MAXWELL_VISCOELASTIC)',
    '*MAT_066 (LINEAR_ELASTIC_DISCRETE_BEAM)', '*MAT_067 (NONLINEAR_ELASTIC_DISCRETE_BEAM)',
    '*MAT_068 (NONLINEAR_PLASTIC_DISCRETE_BEAM)', '*MAT_071 (CABLE_DISCRETE_BEAM)',
    '*MAT_074 (ELASTIC_SPRING_DISCRETE_BEAM)', '*MAT_077_O (OGDEN_RUBBER)',
    '*MAT_081 (PLASTICITY_WITH_DAMAGE)', '*MAT_083 (FU_CHANG_FOAM)',
    '*MAT_098 (SIMPLIFIED_JOHNSON_COOK)', '*MAT_099 (SIMPLIFIED_JOHNSON_COOK_ORTHOTROPIC_DAMAGE)',
    '*MAT_100 (SPOTWELD)', '*MAT_119 (GENERAL_NONLINEAR_6DOF_DISCRETE_BEAM)',
    '*MAT_121 (GENERAL_NONLINEAR_1DOF_DISCRETE_BEAM)', '*MAT_123 (MODIFIED_PIECEWISE_LINEAR_PLASTICITY)',
    '*MAT_126 (MODIFIED_HONEYCOMB)', '*MAT_169 (ARUP_ADHESIVE)',
    '*MAT_181 (SIMPLIFIED_RUBBER/FOAM)', '*MAT_196 (GENERAL_SPRING_DISCRETE_BEAM)',
    '*MAT_240 (COHESIVE_MIXED_MODE_ELASTOPLASTIC_RATE)', '*MAT_ADD_EROSION',
    '*MAT_S01 (SPRING_ELASTIC)', '*MAT_S02 (DAMPER_VISCOUS)',
    '*MAT_S03 (SPRING_ELASTOPLASTIC)', '*MAT_S04 (SPRING_NONLINEAR_ELASTIC)',
    '*MAT_S05 (DAMPER_NONLINEAR_VISCOUS)', '*MAT_S06 (SPRING_GENERAL_NONLINEAR)',
    '*MAT_S08 (SPRING_INELASTIC)', '*NODE',
    '*PART', '*RIGIDWALL_GEOMETRIC',
    '*RIGIDWALL_PLANAR', '*SECTION_BEAM',
    '*SECTION_DISCRETE', '*SECTION_SHELL',
    '*SECTION_SOLID', '*SET_BEAM',
    '*SET_NODE', '*SET_NODE_ADD',
    '*SET_PART', '*SET_PART_ADD',
    '*SET_SHELL', '*SET_SOLID'
}

def generate_documentation_url(keyword_name, base_url):
    """Generate a documentation URL for the given keyword if it's in the allowed list."""
    if not keyword_name or not keyword_name.startswith('*'):
        return ""
    
    # Check if the exact keyword is in our valid list
    if keyword_name in VALID_KEYWORDS:
        # Remove the leading * and convert to lowercase
        name_part = keyword_name[1:].lower()
        
        # Replace special characters with underscores and clean up
        name_part = re.sub(r'[^a-z0-9]+', '_', name_part)
        name_part = name_part.strip('_')
        
        # Special handling for material models with parentheses
        if '(' in keyword_name and ')' in keyword_name:
            # For material models, use the base name without the material number
            base_name = re.sub(r'\s*\([^)]*\)', '', keyword_name[1:].lower())
            return f"{base_url}/{base_name}_lsdyna_r.htm"
        
        # Standard URL format
        return f"{base_url}/{name_part}_lsdyna_r.htm"
    
    return ""

def main():
    # Define paths
    root = Path(__file__).resolve().parents[2]
    input_path = root / 'data' / 'archiv' / 'lsdyna_keywords_cleaned.json'
    output_path = root / 'freecad' / 'ORfemn' / 'keywords_clean.json'
    
    if not input_path.exists():
        print(f"Error: Input file not found at {input_path}")
        return 1
    
    try:
        clean_keywords(input_path, output_path)
        print("Cleaning completed successfully!")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
