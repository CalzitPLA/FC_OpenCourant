"""
Download Radioss documentation pages for offline processing.
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[2]

class DocumentationDownloader:
    def __init__(self, base_url=None, output_dir=None):
        """Initialize the downloader with base URL and output directory."""
        self.base_url = base_url or "https://help.altair.com"
        self.output_dir = output_dir or str(ROOT / 'data' / 'docs')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    def get_links_from_html(self, html_file):
        """Extract all documentation links from the main HTML file."""
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        links = []
        
        # Find all keyword links
        for link in soup.find_all('a', class_='- topic/xref xref'):
            if link.get('href') and link.get('title'):
                keyword_name = link.get_text(strip=True)
                if keyword_name.startswith('*'):
                    url = link['href']
                    full_url = urljoin(self.base_url, url) if not url.startswith('http') else url
                    links.append({
                        'name': keyword_name,
                        'url': full_url,
                        'description': link['title']
                    })
        
        return links
    
    def download_page(self, link):
        """Download a single documentation page."""
        try:
            response = self.session.get(link['url'], timeout=10)
            response.raise_for_status()
            
            # Create a safe filename from the URL
            parsed_url = urlparse(link['url'])
            filename = os.path.basename(parsed_url.path)
            if not filename:
                filename = f"{link['name'].replace('*', '').replace('/', '_')}.html"
            
            filepath = os.path.join(self.output_dir, filename)
            
            # Save the content
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            print(f"Downloaded: {link['name']} -> {filename}")
            return {
                'name': link['name'],
                'filename': filename,
                'url': link['url'],
                'description': link['description']
            }
            
        except Exception as e:
            print(f"Error downloading {link['url']}: {e}")
            return None
    
    def download_all(self, html_file, max_workers=5):
        """Download all documentation pages."""
        print(f"Extracting links from {html_file}...")
        links = self.get_links_from_html(html_file)
        print(f"Found {len(links)} documentation pages to download.")
        
        # Create a metadata file to store information about all pages
        metadata = {
            'base_url': self.base_url,
            'downloaded_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'pages': []
        }
        
        # Download pages with thread pool for better performance
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_link = {
                executor.submit(self.download_page, link): link 
                for link in links
            }
            
            for future in as_completed(future_to_link):
                result = future.result()
                if result:
                    metadata['pages'].append(result)
        
        # Save metadata
        metadata_file = os.path.join(self.output_dir, '_metadata.json')
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\nDownload complete. Metadata saved to {metadata_file}")
        return metadata


def main():
    # Path to the main HTML file containing all the links
    html_file = str(ROOT / 'data' / 'Keyword documentation' / 'LS-DYNA Input.html')
    
    # Initialize downloader
    downloader = DocumentationDownloader()
    
    # Start downloading
    downloader.download_all(html_file)


if __name__ == "__main__":
    import json
    main()
