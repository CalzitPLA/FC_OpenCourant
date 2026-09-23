#!/usr/bin/env python3
"""
LS-DYNA Keywords Parameter Extractor

This script extracts parameter information from LS-DYNA documentation.
It can work with local HTML files or provide templates for URL processing.

Usage:
    python3 extract_parameters.py [--local-html-dir DIR] [--output FILE]
    (e.g. --local-html-dir data/local_documentation)

Options:
    --local-html-dir DIR    Directory containing local HTML documentation files
    --output FILE          Output JSON file (default: freecad/ORfemn/keywords_with_parameters.json)

Requirements:
    - beautifulsoup4 library: pip install beautifulsoup4
"""

import json
import re
import sys
import argparse
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[2] / 'freecad' / 'ORfemn'

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    print("Warning: BeautifulSoup4 not available.")
    print("Install with: pip install beautifulsoup4")
    HAS_BS4 = False


def extract_parameters_from_html(html_content, keyword_name):
    """
    Extract parameter information from HTML documentation content.

    The documentation uses well-structured tables with class "wh_topic_content body".

    Args:
        html_content (str): HTML content of the documentation page
        keyword_name (str): Name of the keyword for context

    Returns:
        list: List of parameter dictionaries with name, type, default, description
    """
    if not HAS_BS4:
        print(f"Cannot extract parameters for {keyword_name} - BeautifulSoup4 not available")
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    parameters = []

    # Look for the main content table with specific class
    content_div = soup.find('div', class_='wh_topic_content body')

    if not content_div:
        print(f"No main content div found for {keyword_name}")
        return parameters

    # Find all tables within the content
    tables = content_div.find_all('table')

    for table in tables:
        # Check if this looks like a parameter/input table
        headers = table.find_all('th')
        if not headers:
            continue

        header_texts = [h.get_text().lower() for h in headers]

        # Check for parameter-related table headers
        param_headers = ['parameter', 'variable', 'option', 'card', 'input', 'argument']
        is_param_table = any(header in ' '.join(header_texts) for header in param_headers)

        # Also check if headers are just column numbers (common in LS-DYNA docs)
        if not is_param_table and header_texts and all(h.strip().startswith('(') and h.strip().endswith(')') for h in header_texts):
            # Check if first data row looks like parameters
            rows = table.find_all('tr')
            if len(rows) > 1:
                first_data_row = rows[1]
                cells = first_data_row.find_all('td')
                if len(cells) >= 2:
                    first_cell = cells[0].get_text().strip()
                    # Check if first cell looks like a parameter name
                    if (len(first_cell) < 50 and 
                        ('_' in first_cell or first_cell.replace('_', '').replace('-', '').isalnum()) and
                        not first_cell.isdigit()):
                        is_param_table = True

        if is_param_table:
            print(f"Found parameter table for {keyword_name}")

            # Extract table rows
            rows = table.find_all('tr')

            if len(rows) > 1:  # More than just header
                # Get header row to understand column structure
                header_row = rows[0]
                header_cells = header_row.find_all('th')
                num_columns = len(header_cells)

                print(f"Table has {num_columns} columns")

                # Process data rows
                for row in rows[1:]:
                    cells = row.find_all('td')
                    if len(cells) >= num_columns:
                        # Extract parameter information based on expected structure
                        param_info = extract_parameter_from_row(cells, header_cells, keyword_name)
                        if param_info:
                            parameters.append(param_info)

    return parameters


def extract_parameter_from_row(cells, headers, keyword_name):
    """
    Extract parameter information from a table row.

    Args:
        cells (list): List of table cells in the row
        headers (list): List of header cells for column names
        keyword_name (str): Keyword name for context

    Returns:
        dict or None: Parameter dictionary or None if extraction failed
    """
    try:
        # Get header names
        header_names = [h.get_text().strip().lower() for h in headers]

        # Create parameter dictionary
        param = {}

        # Map common column names to parameter fields
        for i, (cell, header_name) in enumerate(zip(cells, header_names)):
            cell_text = cell.get_text().strip()

            if 'parameter' in header_name or 'variable' in header_name or 'name' in header_name:
                param['name'] = cell_text
            elif 'type' in header_name or 'data type' in header_name:
                param['type'] = cell_text
            elif 'default' in header_name or 'value' in header_name:
                param['default_value'] = cell_text
            elif 'description' in header_name or 'definition' in header_name or 'meaning' in header_name:
                param['description'] = cell_text
            else:
                # Generic field
                param[f'field_{i}'] = cell_text

        # Special handling for numeric headers (common in LS-DYNA docs)
        if all(h.strip().startswith('(') and h.strip().endswith(')') for h in header_names):
            # Assume first column is parameter name, second is description
            if len(cells) >= 2:
                param['name'] = cells[0].get_text().strip()
                param['description'] = cells[1].get_text().strip()
                # Additional fields for other columns
                for i in range(2, len(cells)):
                    param[f'field_{i}'] = cells[i].get_text().strip()

        # Only return if we have at least a name
        if 'name' in param and param['name']:
            # Clean up the parameter name (remove extra spaces, etc.)
            param['name'] = re.sub(r'\s+', ' ', param['name']).strip()

            # Ensure description exists
            if 'description' not in param:
                # Try to use other fields as description
                for key in ['field_1', 'field_2', 'field_3']:
                    if key in param and param[key]:
                        param['description'] = param[key]
                        break

            return param

    except Exception as e:
        print(f"Error extracting parameter from row for {keyword_name}: {e}")

    return None


def load_documentation_from_file(file_path, keyword_name):
    """
    Load documentation content from a local HTML file.

    Args:
        file_path (str): Path to the HTML file
        keyword_name (str): Name of the keyword for logging

    Returns:
        str or None: HTML content if successful, None if failed
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"Loaded local documentation for {keyword_name}: {file_path}")
        return content
    except Exception as e:
        print(f"Error loading local file {file_path}: {e}")
        return None


def process_local_html_files(html_dir, output_file):
    """
    Process local HTML files to extract parameters.

    Args:
        html_dir (str): Directory containing HTML documentation files
        output_file (str): Output JSON file path
    """
    html_path = Path(html_dir)

    if not html_path.exists():
        print(f"Error: HTML directory {html_dir} not found")
        return

    # Load the keywords database
    json_path = PACKAGE_DIR / 'keywords_clean.json'
    if not json_path.exists():
        print(f"Error: {json_path} not found")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        keywords_data = json.load(f)

    print(f"Loaded {len(keywords_data)} keywords from database")

    # Process each keyword
    updated_count = 0
    processed_count = 0

    for keyword in keywords_data:
        if 'documentation' in keyword and keyword['documentation'].startswith('https://'):
            url = keyword['documentation']
            keyword_name = keyword['name']

            # Extract keyword from URL
            match = re.search(r'/rad/([^/]+)_lsdyna_r\.htm', url)
            if match:
                keyword_from_url = match.group(1)

                # Try to find corresponding local file
                # Files are directly in the local_documentation directory
                # e.g., "mat_098_simplified_johnson_cook_lsdyna_r.htm"
                expected_filename = f"{keyword_from_url}_lsdyna_r.htm"
                local_file = html_path / expected_filename

                if local_file.exists():
                    html_content = load_documentation_from_file(local_file, keyword_name)
                    if html_content:
                        parameters = extract_parameters_from_html(html_content, keyword_name)
                        if parameters:
                            keyword['parameters'] = parameters
                            updated_count += 1
                            print(f"✓ Extracted {len(parameters)} parameters for {keyword_name}")
                        else:
                            print(f"⚠ No parameters found for {keyword_name}")
                    processed_count += 1
                else:
                    print(f"✗ Local file not found for {keyword_name}: {local_file}")

    print(f"\n📊 Summary:")
    print(f"✓ Updated: {updated_count} keywords")
    print(f"○ Processed: {processed_count} keywords")
    print(f"📄 Total: {len(keywords_data)} keywords")

    # Save updated database
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(keywords_data, f, indent=2, ensure_ascii=False)

    print(f"Updated database saved to: {output_file}")


def create_batch_download_script():
    """Create a script for batch downloading documentation pages."""
    script_content = '''#!/bin/bash
# Batch download script for LS-DYNA documentation
# Run this script to download all documentation pages locally

BASE_URL="https://help.altair.com/hwsolvers/rad/topics/solvers/rad/"
OUTPUT_DIR="local_documentation"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Read URLs from the extracted file
while IFS= read -r url; do
    if [[ $url =~ /rad/([^/]+)_lsdyna_r\\.htm ]]; then
        keyword="${BASH_REMATCH[1]}"
        filename="${keyword}_lsdyna_r.htm"
        output_file="$OUTPUT_DIR/$filename"

        echo "Downloading: $url"
        curl -s -o "$output_file" "$url"

        if [[ $? -eq 0 && -s "$output_file" ]]; then
            echo "✓ Downloaded: $filename"
        else
            echo "✗ Failed: $filename"
        fi

        # Small delay to be respectful
        sleep 0.5
    fi
done < /tmp/extracted_htm_urls.txt

echo "Download complete!"
'''

    with open('/tmp/download_docs.sh', 'w') as f:
        f.write(script_content)

    print("Created batch download script: /tmp/download_docs.sh")
    print("Make it executable with: chmod +x /tmp/download_docs.sh")
    print("Then run: /tmp/download_docs.sh")


def main():
    """Main function with command line argument support."""
    parser = argparse.ArgumentParser(description='Extract LS-DYNA keyword parameters')
    parser.add_argument('--local-html-dir', help='Directory containing local HTML documentation files')
    parser.add_argument('--output', default=str(PACKAGE_DIR / 'keywords_with_parameters.json'), help='Output JSON file')

    args = parser.parse_args()

    if args.local_html_dir:
        print(f"Processing local HTML files from: {args.local_html_dir}")
        process_local_html_files(args.local_html_dir, args.output)
    else:
        print("No local HTML directory specified.")
        print("Available options:")
        print("1. Use --local-html-dir to process local HTML files")
        print("2. Run the batch download script to get local files")
        create_batch_download_script()


if __name__ == '__main__':
    main()
