#!/usr/bin/env python3
"""
Fetch and process LS-DYNA documentation to create a clean keywords database.
"""

import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://2021.help.altair.com/2021/hwsolvers/rad/topics/solvers/rad/ls_dyna_keywords_r.htm"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_FILE = os.path.join(ROOT, 'data', 'archiv', 'lsdyna_keywords.json')

def fetch_keywords():
    """Fetch the main keywords page and extract keyword links."""
    print(f"Fetching main documentation page: {BASE_URL}")
    response = requests.get(BASE_URL)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    keywords = []
    
    # Find all links in the content area
    content = soup.find('div', {'class': 'content'})
    if not content:
        raise ValueError("Could not find content area in the documentation page")
    
    for link in content.find_all('a', href=True):
        href = link.get('href')
        name = link.text.strip()
        
        # Only process keyword links
        if not name.startswith('*'):
            continue
            
        # Get the full URL
        url = urljoin(BASE_URL, href)
        
        # Get the category from the parent element if possible
        category = 'UNCATEGORIZED'
        parent = link.find_parent(['h2', 'h3', 'h4', 'div'])
        if parent and hasattr(parent, 'text'):
            category = parent.text.strip().split('\n')[0].strip()
        
        keywords.append({
            'name': name,
            'url': url,
            'category': category
        })
    
    return keywords

def save_keywords(keywords):
    """Save keywords to a JSON file."""
    # Sort keywords by name
    keywords.sort(key=lambda x: x['name'].lower())
    
    # Add IDs
    for i, kw in enumerate(keywords, 1):
        kw['id'] = i
    
    # Save to file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(keywords, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(keywords)} keywords to {OUTPUT_FILE}")

def main():
    try:
        print("Starting documentation fetch...")
        keywords = fetch_keywords()
        save_keywords(keywords)
        print("Done!")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
