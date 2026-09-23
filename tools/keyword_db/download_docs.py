#!/usr/bin/env python3
"""
Download the Radioss "LS-DYNA Input" keyword documentation for offline processing.

The current keyword index is fetched from the Altair help site (falling back
to the saved copy in data/Keyword documentation/), and every keyword page it
links to is saved in data/docs/. data/docs/_metadata.json lists the pages
(name, filename, url, description); extract_cards.py uses it to add new
keywords to the keyword database.

Usage:
    python3 tools/keyword_db/download_docs.py [--output DIR] [--workers N] [--delay SECONDS]

Requirements:
    - requests, beautifulsoup4: pip install requests beautifulsoup4
"""

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
INDEX_URL = "https://help.altair.com/hwsolvers/rad/topics/solvers/rad/ls_dyna_keywords_r.htm"
SAVED_INDEX = ROOT / 'data' / 'Keyword documentation' / 'LS-DYNA Input.html'
DEFAULT_OUTPUT = ROOT / 'data' / 'docs'
DESCRIPTION_PREFIX = "LS-DYNA Input Interface Keyword"


class DocumentationDownloader:
    def __init__(self, output_dir=DEFAULT_OUTPUT, workers=2, delay=0.5, retries=3):
        self.output_dir = Path(output_dir)
        self.workers = workers
        self.delay = delay
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'ORfe-FreeCAD-workbench documentation downloader'})
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get(self, url):
        """GET with retries; returns the response text."""
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                # The server sends no charset; requests would then assume ISO-8859-1
                if 'charset' not in response.headers.get('content-type', '').lower():
                    response.encoding = 'utf-8'
                return response.text
            except requests.RequestException:
                if attempt == self.retries:
                    raise
                time.sleep(2 * attempt)

    def load_index(self):
        """Return (index html, base url): the online index, or the saved copy if offline."""
        try:
            html = self.get(INDEX_URL)
            (self.output_dir / '_index.htm').write_text(html, encoding='utf-8')
            return html, INDEX_URL
        except requests.RequestException as e:
            print(f"Could not fetch {INDEX_URL} ({e}); using {SAVED_INDEX}")
            return SAVED_INDEX.read_text(encoding='utf-8'), INDEX_URL

    @staticmethod
    def keyword_links(index_html, base_url):
        """Return the keyword pages linked from the index.

        Keyword links carry a "LS-DYNA Input Interface Keyword..." title; category
        headings (*MAT, *SET, ...) link to overview pages and have no title.
        """
        soup = BeautifulSoup(index_html, 'html.parser')
        links = {}
        for a in soup.find_all('a', href=True):
            name = a.get_text(strip=True)
            if not name.startswith('*') or not (a.get('title') or '').startswith(DESCRIPTION_PREFIX):
                continue
            url = urljoin(base_url, a['href']).split('#')[0]
            description = (a.get('title') or '').replace(DESCRIPTION_PREFIX, '', 1).strip()
            links.setdefault(name, {'name': name, 'url': url, 'description': description})
        return list(links.values())

    def download_page(self, link):
        filename = os.path.basename(urlparse(link['url']).path)
        html = self.get(link['url'])
        (self.output_dir / filename).write_text(html, encoding='utf-8')
        time.sleep(self.delay)
        return dict(link, filename=filename)

    def download_all(self):
        index_html, base_url = self.load_index()
        links = self.keyword_links(index_html, base_url)
        print(f"Found {len(links)} keyword pages; downloading to {self.output_dir} ...")

        pages, failed = [], []
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(self.download_page, link): link for link in links}
            for n, future in enumerate(as_completed(futures), 1):
                link = futures[future]
                try:
                    pages.append(future.result())
                except Exception as e:
                    failed.append(link['name'])
                    print(f"  failed: {link['name']}: {e}")
                if n % 25 == 0:
                    print(f"  {n}/{len(links)}")

        pages.sort(key=lambda page: page['name'])
        metadata = {
            'index_url': base_url,
            'downloaded_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'pages': pages,
        }
        (self.output_dir / '_metadata.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + '\n',
                                                         encoding='utf-8')
        print(f"Downloaded {len(pages)} pages, {len(failed)} failed. Metadata: {self.output_dir / '_metadata.json'}")
        return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help='Output directory')
    parser.add_argument('--workers', type=int, default=2, help='Parallel downloads (be gentle)')
    parser.add_argument('--delay', type=float, default=0.5, help='Pause after each page in seconds')
    args = parser.parse_args()
    DocumentationDownloader(args.output, args.workers, args.delay).download_all()


if __name__ == "__main__":
    main()
