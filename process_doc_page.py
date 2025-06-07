import os
import json
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from urllib.parse import urljoin, urldefrag, urlparse
import logging
import shutil
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s') # Changed to DEBUG for more verbose logging

_html_url_map_cache = None
_asset_url_map_cache = None
_base_site_url_for_logic = None

def load_maps(html_map_file, asset_map_file):
    global _html_url_map_cache, _asset_url_map_cache
    if _html_url_map_cache is None:
        try:
            with open(html_map_file, 'r', encoding='utf-8') as f:
                _html_url_map_cache = json.load(f)
            logging.info(f"Successfully loaded HTML map from {html_map_file}")
        except Exception as e:
            logging.error(f"Failed to load HTML map from {html_map_file}: {e}")
            _html_url_map_cache = {}

    if _asset_url_map_cache is None:
        try:
            with open(asset_map_file, 'r', encoding='utf-8') as f:
                _asset_url_map_cache = json.load(f)
            logging.info(f"Successfully loaded Asset map from {asset_map_file}")
        except Exception as e:
            logging.error(f"Failed to load Asset map from {asset_map_file}: {e}")
            _asset_url_map_cache = {}

    return _html_url_map_cache, _asset_url_map_cache

def download_asset(asset_url, local_asset_path_str):
    local_asset_path = Path(local_asset_path_str)
    try:
        if local_asset_path.is_file() and local_asset_path.stat().st_size > 0:
            logging.debug(f"Asset already exists, skipping download: {local_asset_path}")
            return True

        logging.info(f"Downloading asset: {asset_url} -> {local_asset_path}")
        local_asset_path.parent.mkdir(parents=True, exist_ok=True)

        response = requests.get(asset_url, stream=True, timeout=10)
        response.raise_for_status()
        with open(local_asset_path, 'wb') as f:
            shutil.copyfileobj(response.raw, f)
        logging.info(f"Successfully downloaded asset: {local_asset_path}")
        return True
    except requests.RequestException as e:
        logging.error(f"Failed to download asset {asset_url}: {e}")
        return False
    except IOError as e:
        logging.error(f"Failed to save asset {local_asset_path}: {e}")
        return False

def process_page(url_to_fetch, output_md_path_str, html_map_file, asset_map_file, base_site_url):
    global _base_site_url_for_logic
    if _base_site_url_for_logic is None:
        parsed_base = urlparse(base_site_url)
        _base_site_url_for_logic = f"{parsed_base.scheme}://{parsed_base.netloc}"

    html_url_map, asset_url_map = load_maps(html_map_file, asset_map_file)
    output_md_path = Path(output_md_path_str)

    logging.info(f"Processing page: {url_to_fetch} -> {output_md_path_str}")

    try:
        response = requests.get(url_to_fetch, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Failed to fetch page {url_to_fetch}: {e}")
        return False

    soup = BeautifulSoup(response.text, 'html.parser')
    main_content_element = soup.find('main', attrs={'role': 'main'})
    if main_content_element:
        content_div = main_content_element.find('div', class_='td-content')
        if content_div: main_content_element = content_div
    else:
        main_content_element = soup.find('article', class_='td-content')
        if not main_content_element:
            main_content_element = soup.find('article')
            if not main_content_element:
                logging.warning(f"No <main role='main'> or <article> found for {url_to_fetch}. Falling back to full body.")
                main_content_element = soup.body
                if not main_content_element:
                    logging.error(f"Could not find body for {url_to_fetch}. Skipping.")
                    return False

    output_md_dir = output_md_path.parent

    # Handle <a> tags
    for tag in main_content_element.find_all('a', href=True):
        href_value = tag.get('href')
        logging.debug(f"Processing <a> tag in {url_to_fetch}: original href='{href_value}'")
        if not href_value or href_value.startswith("mailto:") or href_value.startswith("#"):
            logging.debug(f"Skipping mailto, empty, or pure anchor link: '{href_value}'")
            continue

        if href_value.startswith('/') and not href_value.startswith('//'):
            abs_url = urljoin(_base_site_url_for_logic, href_value)
        else:
            abs_url = urljoin(url_to_fetch, href_value)
        abs_url = urldefrag(abs_url)[0]
        logging.debug(f"Resolved <a> href to absolute: '{abs_url}'")

        target_local_md_path_str = html_url_map.get(abs_url)
        if not target_local_md_path_str: # Try with/without trailing slash
            if abs_url.endswith('/'): target_local_md_path_str = html_url_map.get(abs_url.rstrip('/'))
            else: target_local_md_path_str = html_url_map.get(abs_url + '/')

        if target_local_md_path_str:
            try:
                relative_path = Path(os.path.relpath(Path(target_local_md_path_str).resolve(), output_md_dir.resolve()))
                tag['href'] = str(relative_path).replace(os.sep, '/')
                logging.debug(f"Rewrote <a> HTML link: '{href_value}' -> '{tag['href']}'")
            except ValueError as e:
                logging.warning(f"Error creating relpath for MD link '{target_local_md_path_str}' from '{output_md_dir}': {e}. Keeping: '{abs_url}'")
                tag['href'] = abs_url
        elif asset_url_map.get(abs_url): # Check if it's an asset link
            local_asset_path_str = asset_url_map[abs_url]
            logging.debug(f"Found <a> asset link: '{abs_url}' maps to local '{local_asset_path_str}'")
            if download_asset(abs_url, local_asset_path_str):
                try:
                    relative_path = Path(os.path.relpath(Path(local_asset_path_str).resolve(), output_md_dir.resolve()))
                    tag['href'] = str(relative_path).replace(os.sep, '/')
                    logging.debug(f"Rewrote <a> asset link: '{href_value}' -> '{tag['href']}'")
                except ValueError as e:
                    logging.warning(f"Error creating relpath for asset link '{local_asset_path_str}' from '{output_md_dir}': {e}. Keeping: '{abs_url}'")
                    tag['href'] = abs_url
            else: # Download failed
                tag['href'] = abs_url
                logging.warning(f"Download failed for asset link '{abs_url}'. Kept original href.")
        else: # External link
            if not urlparse(abs_url).scheme in ['http', 'https']:
                 logging.warning(f"Correcting malformed external link '{href_value}' to '{abs_url}'")
            tag['href'] = abs_url
            logging.debug(f"Kept/Made <a> external link absolute: '{abs_url}'")

    # Handle <img> tags
    for tag in main_content_element.find_all('img', src=True):
        src_value = tag.get('src')
        logging.debug(f"Processing <img> tag in {url_to_fetch}: original src='{src_value}'")
        if not src_value or src_value.startswith('data:'):
            logging.debug(f"Skipping data URI or empty src: '{src_value}'")
            continue

        if src_value.startswith('/') and not src_value.startswith('//'):
            abs_image_url = urljoin(_base_site_url_for_logic, src_value)
        else:
            abs_image_url = urljoin(url_to_fetch, src_value)
        abs_image_url = urldefrag(abs_image_url)[0]
        logging.debug(f"Resolved <img> src to absolute: '{abs_image_url}'")

        local_image_path_str = asset_url_map.get(abs_image_url)
        # Robust lookup for asset_url_map (though less likely needed for assets than HTML pages)
        if not local_image_path_str:
            if abs_image_url.endswith('/'): local_image_path_str = asset_url_map.get(abs_image_url.rstrip('/'))
            elif not '.' in abs_image_url.split('/')[-1]: local_image_path_str = asset_url_map.get(abs_image_url + '/')


        if local_image_path_str:
            logging.debug(f"Found <img> asset in map: '{abs_image_url}' -> '{local_image_path_str}'")
            if download_asset(abs_image_url, local_image_path_str):
                try:
                    relative_path = Path(os.path.relpath(Path(local_image_path_str).resolve(), output_md_dir.resolve()))
                    tag['src'] = str(relative_path).replace(os.sep, '/')
                    logging.info(f"Successfully rewrote <img> src: '{src_value}' -> '{tag['src']}' (in {output_md_path_str})")
                except ValueError as e:
                     logging.warning(f"Error creating relpath for image src '{local_image_path_str}' from '{output_md_dir}': {e}. Setting src to absolute: '{abs_image_url}'")
                     tag['src'] = abs_image_url
            else: # Download failed
                tag['src'] = abs_image_url
                logging.warning(f"Download failed for image '{abs_image_url}'. Setting src to absolute.")
        else:
            logging.warning(f"Image not in asset_url_map: '{abs_image_url}'. Original src: '{src_value}'. Setting src to absolute.")
            if not urlparse(abs_image_url).scheme in ['http', 'https']:
                 logging.warning(f"Correcting potentially malformed external image src '{src_value}' to '{abs_image_url}'")
            tag['src'] = abs_image_url

    try:
        markdown_content = md(str(main_content_element), heading_style='atx', bullets='*')
    except Exception as e:
        logging.error(f"Error during markdown conversion for {url_to_fetch}: {e}")
        return False

    try:
        output_md_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        logging.info(f"Successfully processed and saved Markdown: {output_md_path} (from {url_to_fetch})")
        return True
    except IOError as e:
        logging.error(f"Failed to write markdown to {output_md_path}: {e}")
        return False

if __name__ == '__main__':
    if not os.path.exists('html_url_map.json') or not os.path.exists('asset_url_map.json'):
        print("DEMO Error: Map files (html_url_map.json or asset_url_map.json) not found. Run crawler first.")
    else:
        test_html_map, _ = load_maps('html_url_map.json', 'asset_url_map.json')
        if test_html_map:
            # Test with a page that has domain-absolute image paths
            # Example: https://docs.structurizr.com/dsl/example (contains /assets/images/dsl/example.png)
            # Example: https://docs.structurizr.com/dsl/tutorial (contains /dsl/tutorial/1.png etc.)

            # Let's use the dsl/tutorial page as it has several such images
            sample_url_key_raw = "https://docs.structurizr.com/dsl/tutorial"
            sample_url_key_slashed = "https://docs.structurizr.com/dsl/tutorial/"

            sample_md_path_str = test_html_map.get(sample_url_key_raw)
            url_to_use = sample_url_key_raw
            if not sample_md_path_str:
                sample_md_path_str = test_html_map.get(sample_url_key_slashed)
                url_to_use = sample_url_key_slashed

            if not sample_md_path_str: # Fallback if specific keys not found
                 logging.warning(f"Specific test URLs not found, picking first from map for demo.")
                 url_to_use = list(test_html_map.keys())[0]
                 sample_md_path_str = test_html_map[url_to_use]

            print(f"DEMO: Testing with URL: {url_to_use}, Path: {sample_md_path_str}")
            # Change logging to DEBUG for this single test run if needed, then revert for batch.
            # current_log_level = logging.getLogger().getEffectiveLevel()
            # logging.getLogger().setLevel(logging.DEBUG)
            process_page(url_to_use, sample_md_path_str,
                         'html_url_map.json', 'asset_url_map.json',
                         'https://docs.structurizr.com')
            # logging.getLogger().setLevel(current_log_level)
        else:
            print("DEMO Error: Test HTML map is empty or failed to load.")
