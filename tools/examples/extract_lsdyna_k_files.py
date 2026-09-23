#!/usr/bin/env python3
"""
LS-DYNA Examples Extractor
Extracts .k files from downloaded HTML pages and creates a JSON database.
"""

import os
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import sys

class LSDYNAExtractor:
    def __init__(self, base_dir=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "examples")):
        self.base_dir = base_dir
        self.html_dir = os.path.join(base_dir, "www.dynaexamples.com")
        self.k_files_dir = os.path.join(base_dir, "extracted_k_files")
        self.database_file = os.path.join(base_dir, "lsdyna_examples_database.json")

        # Create output directory
        os.makedirs(self.k_files_dir, exist_ok=True)

        # Initialize database
        self.database = {
            "examples": [],
            "categories": {},
            "total_files": 0,
            "extraction_date": ""
        }

    def extract_from_html(self, html_file):
        """Extract .k file content from HTML file."""
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')

            # Find the keywords tab (data-tab-target="2")
            keywords_tab = soup.find('div', {'id': 'tab-2'})

            if not keywords_tab:
                return None

            # Extract keyword text
            keyword_text = keywords_tab.get_text(separator='\n', strip=True)

            # Clean up the text
            keyword_text = self.clean_keyword_text(keyword_text)

            if not keyword_text or len(keyword_text.strip()) < 50:
                return None

            # Get metadata from the page
            title_elem = soup.find('h1', class_='documentFirstHeading')
            title = title_elem.get_text().strip() if title_elem else "Unknown"

            desc_elem = soup.find('div', class_='documentDescription')
            description = desc_elem.get_text().strip() if desc_elem else ""

            # Get category from breadcrumbs
            breadcrumbs = soup.find('nav', id='portal-breadcrumbs')
            category = "General"
            if breadcrumbs:
                category_links = breadcrumbs.find_all('a')
                if len(category_links) > 1:
                    category = category_links[-2].get_text().strip()

            # Get download link if available
            download_tab = soup.find('div', {'id': 'tab-5'})
            download_url = None
            if download_tab:
                download_link = download_tab.find('a', href=True)
                if download_link:
                    download_url = download_link.get('href')

            return {
                'title': title,
                'category': category,
                'description': description,
                'html_file': html_file,
                'keyword_text': keyword_text,
                'download_url': download_url,
                'relative_path': os.path.relpath(html_file, self.html_dir)
            }

        except Exception as e:
            print(f"Error processing {html_file}: {e}")
            return None

    def clean_keyword_text(self, text):
        """Clean and format the extracted keyword text."""
        if not text:
            return ""

        # Remove common HTML artifacts
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'^\s*\*\s*', '*', text, flags=re.MULTILINE)
        text = re.sub(r'\s*\*\s*', '\n*', text)

        # Split into lines and clean each line
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line and not line.startswith('$') and not line.startswith('References:'):
                lines.append(line)

        return '\n'.join(lines)

    def download_k_file(self, download_url, output_path):
        """Download actual .k file from URL."""
        if not download_url:
            return False

        try:
            print(f"Downloading .k file from: {download_url}")
            response = requests.get(download_url, timeout=30)

            if response.status_code == 200:
                # Handle zip files
                if download_url.endswith('.zip'):
                    import zipfile
                    import io

                    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                        # Look for .k files in the zip
                        k_files = [name for name in zf.namelist() if name.endswith('.k')]
                        if k_files:
                            with zf.open(k_files[0]) as kf:
                                content = kf.read().decode('utf-8', errors='ignore')
                                with open(output_path, 'w') as f:
                                    f.write(content)
                                return True
                else:
                    # Assume it's a direct .k file
                    content = response.text
                    with open(output_path, 'w') as f:
                        f.write(content)
                    return True

        except Exception as e:
            print(f"Error downloading from {download_url}: {e}")

        return False

    def extract_all_examples(self):
        """Extract all examples from HTML files."""
        html_files = []
        for root, dirs, files in os.walk(self.html_dir):
            for file in files:
                if file.endswith('.html'):
                    html_files.append(os.path.join(root, file))

        print(f"Found {len(html_files)} HTML files to process...")

        extracted_count = 0
        for i, html_file in enumerate(html_files, 1):
            print(f"Processing {i}/{len(html_files)}: {os.path.basename(html_file)}")

            example_data = self.extract_from_html(html_file)
            if example_data:
                # Create .k file
                safe_title = re.sub(r'[^\w\-_]', '_', example_data['title'])
                k_filename = f"{safe_title}.k"
                k_filepath = os.path.join(self.k_files_dir, k_filename)

                # Save keyword text as .k file
                with open(k_filepath, 'w') as f:
                    f.write(example_data['keyword_text'])

                # Try to download actual .k file if download URL exists
                actual_k_path = None
                if example_data['download_url']:
                    actual_k_filename = f"{safe_title}_actual.k"
                    actual_k_path = os.path.join(self.k_files_dir, actual_k_filename)
                    if self.download_k_file(example_data['download_url'], actual_k_path):
                        print(f"  ✓ Downloaded actual .k file: {actual_k_filename}")

                # Update database entry
                example_data['k_file_path'] = k_filepath
                example_data['actual_k_file_path'] = actual_k_path
                self.database['examples'].append(example_data)
                extracted_count += 1

        self.database['total_files'] = extracted_count
        self.database['extraction_date'] = str(os.times())

        # Update category counts
        for example in self.database['examples']:
            category = example['category']
            if category not in self.database['categories']:
                self.database['categories'][category] = 0
            self.database['categories'][category] += 1

        return extracted_count

    def save_database(self):
        """Save the database to JSON file."""
        with open(self.database_file, 'w') as f:
            json.dump(self.database, f, indent=2)
        print(f"Database saved to: {self.database_file}")

    def generate_summary(self):
        """Generate a summary of the extraction."""
        separator = '=' * 60
        print(f"\n{separator}")
        print("EXTRACTION SUMMARY")
        print(f"{separator}")
        print(f"Total examples extracted: {len(self.database['examples'])}")
        print(f"Categories found: {len(self.database['categories'])}")
        print(f".k files created: {self.database['total_files']}")
        print(f"\nCategory breakdown:")
        for category, count in sorted(self.database['categories'].items()):
            print(f"  {category}: {count} examples")
        print(f"\nFiles saved to: {self.k_files_dir}")
        print(f"Database saved to: {self.database_file}")
        print(f"{separator}")

def main():
    extractor = LSDYNAExtractor()
    extracted = extractor.extract_all_examples()
    extractor.save_database()
    extractor.generate_summary()

if __name__ == "__main__":
    main()
