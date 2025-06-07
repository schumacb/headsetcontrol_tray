import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urldefrag, urlparse
import logging
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
START_URLS = ["https://docs.structurizr.com/"] # Initial URL to start crawling
HTML_SCOPE_URL = "https://docs.structurizr.com/" # Base URL to stay within for discovering HTML pages
ASSET_DOMAIN_SCOPE = urlparse(HTML_SCOPE_URL).netloc # e.g., "docs.structurizr.com" for assets

LOCAL_HTML_BASE_DIR = "docs/structurizr" # For HTML pages converted to MD
LOCAL_ASSETS_BASE_DIR = "docs/structurizr/assets" # For images, DSL files, etc.

HTML_URL_MAP_FILE = "html_url_map.json"
ASSET_URL_MAP_FILE = "asset_url_map.json"

IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']
DSL_EXTENSION = '.dsl'

def normalize_url_for_visit_tracking(url_to_normalize):
    """Removes fragment. Normalizes for HTML page queue/visited set.
    For URLs within HTML_SCOPE_URL, ensures it ends with / if it's directory-like.
    """
    url_str = urldefrag(url_to_normalize)[0]

    if not url_str.startswith(HTML_SCOPE_URL): # External link, return as is
        return url_str

    # Check if it looks like a file (has a common extension)
    path_part = urlparse(url_str).path
    if '.' in path_part.split('/')[-1]: # Simple check for extension in last path segment
        # Check against known non-HTML file types that shouldn't be treated as pages
        known_file_extensions = IMAGE_EXTENSIONS + [DSL_EXTENSION, '.pdf', '.zip', '.css', '.js']
        if any(url_str.lower().endswith(ext) for ext in known_file_extensions):
            return url_str # It's a file asset, don't append slash

    # If it's in scope and doesn't look like a file, assume it's a page/directory, ensure trailing slash
    if not url_str.endswith('/'):
        return url_str + '/'
    return url_str


def get_local_markdown_path(html_url_normalized_slashed):
    """Determines the local .md file path for a given HTML URL (assumed normalized with trailing slash for dirs)."""
    relative_part = html_url_normalized_slashed.replace(HTML_SCOPE_URL, "").strip('/')
    parts = [p for p in relative_part.split('/') if p]

    # Base URL (e.g. https://docs.structurizr.com/) maps to index.md at the root of LOCAL_HTML_BASE_DIR
    if not parts:
        local_file_path = os.path.join(LOCAL_HTML_BASE_DIR, "index.md")
    else:
        # Check if the original URL (before normalization for path generation) pointed to a "file" like /faq (no slash)
        # The input `html_url_normalized_slashed` here is assumed to be directory-like (ends with /)
        # So, all such URLs become an index.md in a directory.
        # e.g. /dsl/ -> dsl/index.md ; /dsl/basics/ -> dsl/basics/index.md
        # If a URL like /faq (no slash, no extension) was passed, it would have been normalized to /faq/
        # and thus maps to /faq/index.md
        dir_path = os.path.join(LOCAL_HTML_BASE_DIR, *parts)
        local_file_path = os.path.join(dir_path, "index.md")

    os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
    return local_file_path


def get_local_asset_path(asset_url):
    """Determines the local file path for a given asset URL."""
    parsed_url = urlparse(asset_url)
    # path_on_server = /path/to/asset.png
    asset_path_on_server = parsed_url.path.strip('/')
    path_parts = [part for part in asset_path_on_server.split('/') if part]

    if not path_parts: # Should not happen if asset_url is valid
        filename = asset_url.split('?')[0].split('/')[-1] # Get filename from URL before query params
        if not filename: filename = "unknown_asset_" + str(hash(asset_url)) # Create a unique name
        path_parts = [filename]

    local_file_path = os.path.join(LOCAL_ASSETS_BASE_DIR, *path_parts)

    # Ensure the directory for the asset exists
    os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
    return local_file_path


def crawl():
    start_time = time.time()
    urls_to_visit = list(START_URLS)
    visited_html_urls = set()

    html_url_map = {}
    asset_url_map = {}
    discovered_asset_urls = set()

    os.makedirs(LOCAL_HTML_BASE_DIR, exist_ok=True)
    os.makedirs(LOCAL_ASSETS_BASE_DIR, exist_ok=True)

    queue_idx = 0
    while queue_idx < len(urls_to_visit): # Process as a FIFO queue
        current_url_raw = urls_to_visit[queue_idx]
        queue_idx += 1

        current_html_url_normalized = normalize_url_for_visit_tracking(current_url_raw)

        if current_html_url_normalized in visited_html_urls:
            logging.debug(f"HTML URL already visited: {current_html_url_normalized}")
            continue

        if not current_html_url_normalized.startswith(HTML_SCOPE_URL):
            logging.debug(f"Skipping out-of-scope HTML URL: {current_html_url_normalized}")
            continue

        visited_html_urls.add(current_html_url_normalized)
        logging.info(f"Visiting HTML page ({queue_idx}/{len(urls_to_visit)}): {current_url_raw} (Normalized: {current_html_url_normalized})")

        # Map both raw and normalized URL to the same local path for flexibility in link rewriting
        local_markdown_path = get_local_markdown_path(current_html_url_normalized)
        html_url_map[current_url_raw] = local_markdown_path
        if current_url_raw != current_html_url_normalized:
             html_url_map[current_html_url_normalized] = local_markdown_path

        try:
            response = requests.get(current_url_raw, timeout=10) # Fetch the raw URL
            response.raise_for_status()
            # Ensure we only parse HTML content type
            if not response.headers.get('content-type','').lower().startswith('text/html'):
                logging.warning(f"Skipping non-HTML content at {current_url_raw} (Content-Type: {response.headers.get('content-type')})")
                continue
        except requests.RequestException as e:
            logging.error(f"Failed to fetch HTML {current_url_raw}: {e}")
            continue

        soup = BeautifulSoup(response.text, 'html.parser')

        # Discover new HTML pages (<a> tags)
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            abs_next_html_url_raw = urljoin(current_url_raw, href) # Resolve against the raw current URL

            # Only consider for crawling if it's HTTP/HTTPS
            if not abs_next_html_url_raw.lower().startswith(('http://', 'https://')):
                continue

            abs_next_html_url_normalized = normalize_url_for_visit_tracking(abs_next_html_url_raw)

            if abs_next_html_url_normalized.startswith(HTML_SCOPE_URL) and \
               abs_next_html_url_normalized not in visited_html_urls and \
               not any(u == abs_next_html_url_raw for u in urls_to_visit): # Check raw form in queue

                is_file_asset = any(abs_next_html_url_raw.lower().endswith(ext) for ext in IMAGE_EXTENSIONS + [DSL_EXTENSION, '.pdf', '.zip'])
                if not is_file_asset: # Don't add asset links to HTML crawl queue
                    urls_to_visit.append(abs_next_html_url_raw)
                    logging.debug(f"Added HTML to queue: {abs_next_html_url_raw}")

        # Discover assets (<img>, <link rel="stylesheet">, <script src="">, and .dsl links in <a> tags)
        asset_tags_selectors = [
            ('img', 'src'),
            ('link', 'href'), # For CSS, favicons etc.
            ('script', 'src') # For JS
        ]

        for tag_name, attr_name in asset_tags_selectors:
            for tag in soup.find_all(tag_name, **{attr_name: True}):
                asset_src_val = tag.get(attr_name)
                abs_asset_url = urldefrag(urljoin(current_url_raw, asset_src_val))[0]

                if urlparse(abs_asset_url).netloc == ASSET_DOMAIN_SCOPE: # Check if asset is from the same domain
                    if abs_asset_url not in discovered_asset_urls:
                        # Filter specific rel types for <link> if needed, e.g. only stylesheets
                        if tag_name == 'link' and not tag.get('rel', [''])[0].lower() in ['stylesheet', 'icon', 'shortcut icon', 'apple-touch-icon']:
                            logging.debug(f"Skipping non-stylesheet/icon <link> asset: {abs_asset_url}")
                            continue

                        discovered_asset_urls.add(abs_asset_url)
                        local_asset_path = get_local_asset_path(abs_asset_url)
                        asset_url_map[abs_asset_url] = local_asset_path
                        logging.info(f"Discovered {tag_name} asset: {abs_asset_url} -> {local_asset_path}")
                else:
                    logging.debug(f"Skipping external domain {tag_name} asset: {abs_asset_url}")

        # DSL files from <a> tags specifically
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            if href.lower().endswith(DSL_EXTENSION):
                abs_dsl_url = urldefrag(urljoin(current_url_raw, href))[0]
                if urlparse(abs_dsl_url).netloc == ASSET_DOMAIN_SCOPE:
                    if abs_dsl_url not in discovered_asset_urls:
                        discovered_asset_urls.add(abs_dsl_url)
                        local_dsl_path = get_local_asset_path(abs_dsl_url)
                        asset_url_map[abs_dsl_url] = local_dsl_path
                        logging.info(f"Discovered DSL file asset (<a> tag): {abs_dsl_url} -> {local_dsl_path}")
                else:
                    logging.debug(f"Skipping external domain DSL file asset (<a> tag): {abs_dsl_url}")


    with open(HTML_URL_MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(html_url_map, f, indent=4, sort_keys=True)
    logging.info(f"HTML URL map saved to {HTML_URL_MAP_FILE}. Mapped {len(html_url_map)} unique raw/normalized URLs.")

    with open(ASSET_URL_MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(asset_url_map, f, indent=4, sort_keys=True)
    logging.info(f"Asset URL map saved to {ASSET_URL_MAP_FILE}. Mapped {len(asset_url_map)} unique asset URLs.")

    end_time = time.time()
    logging.info(f"Crawling complete in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    crawl()
