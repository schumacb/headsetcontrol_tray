import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urldefrag
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
BASE_URL_FOR_SCOPING = "https://docs.structurizr.com/dsl"
LOCAL_BASE_DIR = "docs/structurizr/dsl"
URL_MAP_FILE = "url_to_local_path_map.json"

def normalize_url(url_to_normalize):
    """Removes fragment. Ensures URL ends with / if it's directory-like and not a file."""
    url_str = urldefrag(url_to_normalize)[0]
    # If it's the base URL, or already ends with a slash, or looks like a file, return as is (or with / for base)
    if url_str == BASE_URL_FOR_SCOPING: # Keep base URL as is, or ensure it has a slash if that's how site works
         return url_str # Initial fetch should be as-is

    # Check if it looks like a path that could have a file extension
    # Common file extensions, not exhaustive. Add more if needed.
    file_extensions = ['.html', '.md', '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.css', '.js']
    if any(url_str.lower().endswith(ext) for ext in file_extensions):
        return url_str

    if url_str.endswith('/'):
        return url_str

    return url_str + '/' # Assume it's a directory if no extension and not ending with /

def get_local_path(url_to_map):
    """Determines the local file path for a given URL."""
    # Use the original, non-normalized URL for path generation logic if needed,
    # but generally, path logic should stem from a consistent URL form.
    # For this function, let's use a consistently slashed version for directory determination.

    temp_url_for_path = url_to_map
    if not temp_url_for_path.endswith('/') and not any(temp_url_for_path.lower().endswith(ext) for ext in ['.html', '.md', '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.css', '.js']):
        temp_url_for_path += '/'

    relative_part = temp_url_for_path.replace(BASE_URL_FOR_SCOPING, "").strip('/')

    parts = [p for p in relative_part.split('/') if p] # Filter out empty parts

    if not parts: # Base URL itself
        local_file_path = os.path.join(LOCAL_BASE_DIR, "index.md")
    else:
        # If the original URL did not end with a slash and didn't have a common file extension,
        # it's something like /dsl/basics -> basics.md
        # If it was /dsl/basics/ -> basics/index.md

        # Check if the last part looks like a filename (has an extension)
        if '.' in parts[-1]:
            # e.g. foo.html -> foo.md or image.png -> image.png
            if not parts[-1].endswith(".md"):
                 parts[-1] = parts[-1].split('.')[0] + ".md" # Convert non-md extensions to .md
        elif url_to_map.endswith('/'): # It's a directory index
            parts.append("index.md")
        else: # It's a path segment like 'basics' -> 'basics.md'
            parts[-1] = parts[-1] + ".md"

        local_file_path = os.path.join(LOCAL_BASE_DIR, *parts)

    os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
    return local_file_path

def crawl():
    urls_to_visit = [BASE_URL_FOR_SCOPING] # Start with base URL, no trailing slash
    visited_urls = set()
    url_map = {} # Store original URL from site -> local_path

    if not os.path.exists(LOCAL_BASE_DIR):
        os.makedirs(LOCAL_BASE_DIR)
        logging.info(f"Created base directory: {LOCAL_BASE_DIR}")

    while urls_to_visit:
        current_url_raw = urls_to_visit.pop(0) # This is the URL as found on the site

        # Normalize for internal processing (visiting, checking scope)
        # The first URL (BASE_URL_FOR_SCOPING) will be fetched as is.
        # Subsequent URLs found in hrefs will be normalized.
        if current_url_raw == BASE_URL_FOR_SCOPING:
            current_url_for_processing = current_url_raw
        else:
            current_url_for_processing = normalize_url(current_url_raw)


        if current_url_for_processing in visited_urls:
            logging.debug(f"Already visited (normalized form): {current_url_for_processing} (raw: {current_url_raw})")
            continue

        if not current_url_for_processing.startswith(BASE_URL_FOR_SCOPING):
            logging.debug(f"Skipping out-of-scope URL: {current_url_for_processing}")
            continue

        visited_urls.add(current_url_for_processing)
        logging.info(f"Visiting: {current_url_raw} (Processing as: {current_url_for_processing})")

        # Use current_url_raw for mapping, as it's the key we want for the map.
        # get_local_path should use a URL form that helps it decide if it's dir/file
        local_path = get_local_path(current_url_raw) # Pass raw URL to get_local_path
        url_map[current_url_raw] = local_path

        try:
            # Fetch the raw URL, as that's what a browser/user would request
            response = requests.get(current_url_raw, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            logging.error(f"Failed to fetch {current_url_raw}: {e}")
            # Add to map with error or skip? For now, it's in map, but no content/further links.
            continue


        soup = BeautifulSoup(response.text, 'html.parser')

        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            # Resolve against the URL that was actually fetched (current_url_raw)
            absolute_next_url_raw = urljoin(current_url_raw, href)

            # Normalize this newly found URL for visited checks and queue
            normalized_next_url = normalize_url(absolute_next_url_raw)


            if normalized_next_url.startswith(BASE_URL_FOR_SCOPING):
                # Check if the *normalized* form has been visited or is already in queue (via its raw form)
                # We add raw URLs to queue, so check against those.
                # And we add normalized URLs to visited_urls.
                is_in_queue = any(u == absolute_next_url_raw for u in urls_to_visit)

                if normalized_next_url not in visited_urls and not is_in_queue:
                    # Filter out links that are just anchors on the *same logical page*
                    # current_url_for_processing is the normalized version of current_url_raw
                    if urldefrag(current_url_for_processing)[0] == urldefrag(normalized_next_url)[0] and urldefrag(absolute_next_url_raw)[1]:
                        logging.debug(f"Skipping same-page anchor: {absolute_next_url_raw} from {current_url_raw}")
                        continue

                    urls_to_visit.append(absolute_next_url_raw)
                    logging.debug(f"Added to queue: {absolute_next_url_raw} (Normalized: {normalized_next_url})")
            else:
                logging.debug(f"Skipping out-of-scope or non-HTTP link: {absolute_next_url_raw}")

    with open(URL_MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(url_map, f, indent=4, sort_keys=True)

    logging.info(f"Crawling complete. Map saved to {URL_MAP_FILE}")
    logging.info(f"Mapped {len(url_map)} distinct raw URLs.")

if __name__ == "__main__":
    crawl()
