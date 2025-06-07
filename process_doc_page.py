import os
import json
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from urllib.parse import urljoin, urldefrag
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global cache for the URL map to avoid reloading it for each page
_url_map_cache = None
_base_structurizr_url_cache = None

def load_url_map(url_to_local_path_map_file):
    global _url_map_cache
    if _url_map_cache is None:
        try:
            with open(url_to_local_path_map_file, 'r', encoding='utf-8') as f:
                _url_map_cache = json.load(f)
            logging.info(f"Successfully loaded URL map from {url_to_local_path_map_file}")
        except Exception as e:
            logging.error(f"Failed to load URL map from {url_to_local_path_map_file}: {e}")
            _url_map_cache = {} # Ensure it's an empty dict on failure
    return _url_map_cache

def process_page(url_to_fetch, output_md_path, url_to_local_path_map_file, base_structurizr_url_for_links):
    global _base_structurizr_url_cache
    if _base_structurizr_url_cache is None:
        _base_structurizr_url_cache = base_structurizr_url_for_links

    url_map = load_url_map(url_to_local_path_map_file)
    if not url_map:
        logging.warning(f"URL map is empty. Cannot process {url_to_fetch}.")
        return False

    try:
        logging.info(f"Fetching HTML for: {url_to_fetch}")
        response = requests.get(url_to_fetch, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Failed to fetch {url_to_fetch}: {e}")
        return False

    soup = BeautifulSoup(response.text, 'html.parser')

    # Isolate main content
    # Structurizr docs (Just the Docs theme) uses <main role="main"> then <div class="td-content">
    # Or sometimes <article class="td-content">
    main_content_element = soup.find('main', attrs={'role': 'main'})
    if main_content_element:
        content_div = main_content_element.find('div', class_='td-content')
        if content_div:
            main_content_element = content_div
        else: # Fallback if no td-content div, but main role=main exists
             pass # Use the main_content_element as is
    else: # Fallback to article or body
        main_content_element = soup.find('article', class_='td-content')
        if not main_content_element:
            main_content_element = soup.find('article')
            if not main_content_element:
                logging.warning(f"No <main role='main'> or <article class='td-content'> or <article> found for {url_to_fetch}. Falling back to full body.")
                main_content_element = soup.body
                if not main_content_element:
                    logging.error(f"Could not find body for {url_to_fetch}. Skipping.")
                    return False

    # Link Rewriting
    output_md_dir = os.path.dirname(output_md_path)

    for tag in main_content_element.find_all('a', href=True):
        href_value = tag.get('href')
        if not href_value:
            continue

        # Resolve to absolute URL relative to the page being processed
        absolute_link_url_raw = urljoin(url_to_fetch, href_value)

        # Normalize for map lookup (remove fragment, ensure consistent slashes if needed by map keys)
        # The map keys are raw URLs as found and normalized URLs from crawler.
        # Try matching raw first, then a normalized version.

        normalized_lookup_url = urldefrag(absolute_link_url_raw)[0] # Key for map lookup

        # Check variants: raw, raw with slash, normalized, normalized with slash
        # This depends on how keys were stored in url_map. The crawler stored both raw and a normalized form.
        # Let's assume the map keys are consistent with what urljoin + urldefrag produces.

        target_local_path = url_map.get(absolute_link_url_raw) # Try raw as-is from urljoin
        if not target_local_path:
            target_local_path = url_map.get(normalized_lookup_url) # Try just defragged

        # Additional check: if normalized_lookup_url doesn't end with '/' and isn't a file, try with '/'
        if not target_local_path and not normalized_lookup_url.endswith('/') and not '.' in normalized_lookup_url.split('/')[-1]:
            target_local_path = url_map.get(normalized_lookup_url + '/')


        if target_local_path:
            try:
                relative_path_to_target = os.path.relpath(target_local_path, start=output_md_dir)
                tag['href'] = relative_path_to_target
                logging.debug(f"Rewrote link: {href_value} -> {relative_path_to_target} (for {url_to_fetch})")
            except ValueError as e:
                logging.warning(f"Error creating relative path for {target_local_path} from {output_md_dir}: {e}. Keeping original: {href_value}")
        else:
            # If it's an external link not in our map, ensure it's absolute
            if not absolute_link_url_raw.startswith(('http://', 'https://')):
                # This case should be rare if urljoin works correctly from a valid base
                tag['href'] = urljoin(_base_structurizr_url_cache + "/", href_value) # Re-resolve against site base
                logging.debug(f"Made link absolute (external): {href_value} -> {tag['href']}")
            else:
                tag['href'] = absolute_link_url_raw # Ensure it's the fully resolved absolute URL
                logging.debug(f"Kept absolute external link: {absolute_link_url_raw}")

    # Convert to Markdown
    try:
        markdown_content = md(str(main_content_element), heading_style='atx', bullets='*')
    except Exception as e:
        logging.error(f"Error during markdown conversion for {url_to_fetch}: {e}")
        return False

    # Save Output
    try:
        os.makedirs(output_md_dir, exist_ok=True)
        with open(output_md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        logging.info(f"Successfully processed and saved: {url_to_fetch} -> {output_md_path}")
        return True
    except IOError as e:
        logging.error(f"Failed to write markdown to {output_md_path}: {e}")
        return False

if __name__ == '__main__':
    # Example usage (for testing a single page)
    # Ensure url_to_local_path_map.json exists and is populated
    if not os.path.exists('url_to_local_path_map.json'):
        print("Error: url_to_local_path_map.json not found. Run crawler first.")
    else:
        test_map = load_url_map('url_to_local_path_map.json')
        if test_map:
            # Find a sample URL and its path from the map to test
            # Example: first item
            sample_url = list(test_map.keys())[0]
            sample_path = test_map[sample_url]
            print(f"Testing with URL: {sample_url}, Path: {sample_path}")
            process_page(sample_url, sample_path, 'url_to_local_path_map.json', 'https://docs.structurizr.com')
        else:
            print("Test map is empty or failed to load.")
