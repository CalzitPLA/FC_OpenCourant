import os
import re
import sys
import time
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# Configuration
BASE_URLS = [
    "https://www.dynaexamples.com/",
    "https://openradioss.atlassian.net/wiki/spaces/OPENRADIOSS/pages/17629185/Example+LS-DYNA+Format+Models"
]
DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "data", "examples", "lsdyna_examples_html")
TIMEOUT = 30
MAX_DEPTH = 3  # Maximum link depth to follow
DELAY = 1  # Delay between requests in seconds

# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Track visited URLs to avoid duplicates
visited_urls = set()

# Valid domains for our target websites
VALID_DOMAINS = ['dynaexamples.com', 'atlassian.net']

def is_valid_url(url):
    """Check if URL is from our target domains and not already visited."""
    parsed = urlparse(url)
    return (any(domain in parsed.netloc for domain in VALID_DOMAINS) and
            not url in visited_urls and
            not url.endswith(('.pdf', '.zip', '.jpg', '.png', '.gif', '.ico', '.css', '.js')))

def sanitize_filename(url):
    """Convert URL to a safe filename."""
    # Remove protocol and domain
    filename = re.sub(r'^https?://[^/]+', '', url)
    # Replace special characters
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    # Ensure it ends with .html if it's not a file
    if not any(filename.endswith(ext) for ext in ['.html', '.htm', '.pdf', '.zip', '.jpg', '.png', '.gif']):
        filename = filename + '.html'
    return os.path.join(DOWNLOAD_DIR, filename.lstrip('/_'))

def get_domain_folder(url):
    """Get the domain name for organizing files."""
    parsed = urlparse(url)
    return parsed.netloc.replace('.', '_')

def download_page(url, depth=0):
    """Download a single page and extract links."""
    if depth > MAX_DEPTH or not is_valid_url(url):
        return []

    visited_urls.add(url)
    print(f"Downloading: {url}")

    try:
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()

        # Save the HTML content
        filename = sanitize_filename(url)
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(response.text)

        # Parse the HTML to find more links
        soup = BeautifulSoup(response.text, 'html.parser')
        links = [a.get('href') for a in soup.find_all('a', href=True)]

        # Convert relative URLs to absolute
        absolute_links = [urljoin(url, link) for link in links]

        # Filter and return valid links
        return [link for link in absolute_links if is_valid_url(link)]

    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return []

def main():
    print("Starting download of LS-DYNA examples from multiple sources:")
    for base_url in BASE_URLS:
        print(f"  • {base_url}")
    print(f"Files will be saved to: {os.path.abspath(DOWNLOAD_DIR)}")

    # Start with all base URLs
    urls_to_visit = BASE_URLS.copy()

    while urls_to_visit:
        current_url = urls_to_visit.pop(0)
        new_links = download_page(current_url)

        # Add new links to the queue
        for link in new_links:
            if link not in visited_urls and link not in urls_to_visit:
                urls_to_visit.append(link)

        # Be nice to the server
        time.sleep(DELAY)

    print("\nDownload complete!")
    print(f"Total pages downloaded: {len(visited_urls)}")
    print(f"Files saved in: {os.path.abspath(DOWNLOAD_DIR)}")

    # Show summary by domain
    domain_counts = {}
    for url in visited_urls:
        domain = urlparse(url).netloc
        if domain not in domain_counts:
            domain_counts[domain] = 0
        domain_counts[domain] += 1

    print("\nDownload summary by domain:")
    for domain, count in sorted(domain_counts.items()):
        print(f"  {domain}: {count} pages")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDownload interrupted by user.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        print("Exiting...")