"""
Radioss Documentation Parser

This script downloads and parses Radioss documentation to extract keywords and their parameters.
"""

import os
import re
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse

DATA_DIR = Path(__file__).resolve().parents[2] / 'data'

# Base URL for Altair documentation (update this with the actual URL if different)
DOCS_BASE_URL = "https://2021.help.altair.com/2021/rad/"

class RadiossDocParser:
    def __init__(self, cache_dir: str = None):
        """Initialize the parser with an optional cache directory."""
        if cache_dir is None:
            self.cache_dir = str(DATA_DIR / '.doc_cache')
        else:
            self.cache_dir = cache_dir
        
        os.makedirs(self.cache_dir, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def _get_cached_content(self, url: str) -> Optional[str]:
        """Get content from cache if available."""
        cache_file = os.path.join(self.cache_dir, self._url_to_filename(url))
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                return f.read()
        return None
    
    def _cache_content(self, url: str, content: str):
        """Cache the content of a URL."""
        cache_file = os.path.join(self.cache_dir, self._url_to_filename(url))
        with open(cache_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    @staticmethod
    def _url_to_filename(url: str) -> str:
        """Convert a URL to a safe filename."""
        return re.sub(r'[^a-zA-Z0-9_.-]', '_', url) + '.html'
    
    def fetch_url(self, url: str) -> str:
        """Fetch URL content with caching."""
        # Try to get from cache first
        cached = self._get_cached_content(url)
        if cached is not None:
            return cached
        
        # Fetch from web
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            content = response.text
            
            # Cache the response
            self._cache_content(url, content)
            return content
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return ""
    
    def extract_keywords_from_docs(self) -> List[Dict]:
        """Extract Radioss keywords from the local documentation files."""
        # Path to the metadata file
        metadata_file = str(DATA_DIR / 'docs' / '_metadata.json')
        
        if not os.path.exists(metadata_file):
            print(f"Error: Metadata file not found at {metadata_file}")
            return []
        
        # Load metadata
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Process each keyword
        keywords = []
        for page in metadata.get('pages', []):
            print(f"Processing {page['name']}...")
            keyword_data = self._process_local_page(page)
            if keyword_data:
                keywords.append(keyword_data)
        
        return keywords
    
    def _process_local_page(self, page_info: Dict) -> Dict:
        """Process a single local documentation page."""
        # Get the local file path
        docs_dir = str(DATA_DIR / 'docs')
        filepath = os.path.join(docs_dir, page_info['filename'])
        
        if not os.path.exists(filepath):
            print(f"Warning: File not found: {filepath}")
            return None
        
        # Read the file
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the page
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract sections
        sections = {}
        current_section = None
        
        # Find all section headers and content
        for element in soup.find_all(['h1', 'h2', 'h3', 'p', 'pre', 'table']):
            if element.name in ['h1', 'h2', 'h3']:
                current_section = element.get_text(strip=True)
                sections[current_section] = []
            elif current_section and element.get_text(strip=True):
                sections[current_section].append(element.get_text(strip=True))
        
        # Extract parameter table if it exists
        parameters = []
        param_table = soup.find('table', class_='table')
        if param_table:
            # Get headers
            headers = []
            for th in param_table.find_all('th'):
                header_text = th.get_text(strip=True)
                if header_text:  # Only add non-empty headers
                    headers.append(header_text)
            
            # Get rows
            for row in param_table.find_all('tr')[1:]:  # Skip header row
                cols = row.find_all('td')
                if cols and len(cols) >= len(headers):
                    param = {}
                    for i, col in enumerate(cols):
                        if i < len(headers):
                            param[headers[i]] = col.get_text(strip=True)
                    if param:  # Only add if we got some data
                        parameters.append(param)
        
        # Build the keyword data
        keyword_data = {
            'name': page_info['name'],
            'category': self._get_keyword_category(page_info['name']),
            'description': page_info.get('description', ''),
            'filename': page_info['filename'],
            'sections': sections,
            'parameters': parameters
        }
        
        return keyword_data
    
    def _process_keyword_page(self, keyword_name: str, url: str, description: str) -> Dict:
        """Process a single keyword documentation page (kept for backward compatibility)."""
        return None  # This method is no longer used
    
    def _get_keyword_category(self, keyword: str) -> str:
        """Extract the category from a keyword."""
        if not keyword.startswith('*'):
            return 'GENERAL'
            
        # Remove leading '*' and split by '_' to get the main category
        parts = keyword[1:].split('_')
        
        # Special handling for MATERIAL keywords
        if keyword.startswith('*MAT_'):
            mat_type = parts[1] if len(parts) > 1 else 'GENERAL'
            return f'MATERIAL_{mat_type}'
            
        # Return the first part as category if available
        return parts[0] if parts else 'GENERAL'


def main():
    # Initialize the parser
    parser = RadiossDocParser()
    
    # Extract keywords from documentation
    print("Extracting keywords from local documentation...")
    keywords = parser.extract_keywords_from_docs()
    print(f"\nExtracted {len(keywords)} keywords")
    
    # Initialize database
    from keyword_database import create_database_from_parser
    
    print("\nStoring data in database...")
    db = create_database_from_parser(keywords)
    
    # Print database summary
    print("\nDatabase Summary:")
    print("=" * 50)
    
    # Get all categories
    categories = db.get_all_categories()
    print(f"\nFound {len(categories)} categories:")
    for category in categories[:10]:  # Show first 10 categories
        count = len(db.get_keywords_by_category(category))
        print(f"- {category}: {count} keywords")
    
    if len(categories) > 10:
        print(f"- ... and {len(categories) - 10} more categories")
    
    # Show example queries
    print("\nExample Queries:")
    print("1. Search for 'node' related keywords:")
    for kw in db.search_keywords('node', limit=3):
        print(f"   - {kw['name']}: {kw['description']}")
    
    print("\n2. Get all keywords in 'MATERIAL' category:")
    material_keywords = [c for c in categories if 'MATERIAL' in c]
    for category in material_keywords[:3]:
        kws = db.get_keywords_by_category(category)[:2]
        print(f"\n   {category} (showing {len(kws)} of {len(db.get_keywords_by_category(category))}):")
        for kw in kws:
            print(f"   - {kw['name']}")
    
    # Export to JSON
    json_file = db.export_to_json()
    print(f"\nExported all data to: {json_file}")
    
    # Close database connection
    db.close()


if __name__ == "__main__":
    main()
