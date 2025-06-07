import json
import logging
from process_doc_page import process_page, load_url_map # Import the function

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

URL_MAP_FILE = "url_to_local_path_map.json"
BASE_STRUCTURIZR_URL = "https://docs.structurizr.com" # Used for resolving external links if needed

def batch_process():
    url_map = load_url_map(URL_MAP_FILE) # Use the loader from process_doc_page

    if not url_map:
        logging.error("URL map is empty or failed to load. Exiting batch process.")
        return

    processed_count = 0
    failed_count = 0

    # Create a list of items to process to avoid issues if map changes during iteration (it shouldn't here)
    # Filter out entries where the key might be a normalized URL that duplicates a raw URL key,
    # if the local path is identical. The crawler script might store both.
    # We only want to process each unique local_path once.

    unique_local_paths_processed = set()
    items_to_process = []

    # Prioritize raw URLs if multiple map entries point to the same local file
    # The crawler stores both raw and normalized URLs as keys.
    # We want the "raw" URL (as seen in hrefs) for fetching.

    # Build a map from local_path to the "best" URL for fetching it
    path_to_url_map = {}
    for url, local_path in url_map.items():
        if local_path not in path_to_url_map:
            path_to_url_map[local_path] = url
        else:
            # Prefer shorter URLs if multiple map to same path (e.g. prefer non-slashed if both exist)
            # This heuristic might need adjustment based on map contents.
            if len(url) < len(path_to_url_map[local_path]):
                 path_to_url_map[local_path] = url


    for local_path, url_to_fetch in path_to_url_map.items():
        logging.info(f"Queueing for processing: {url_to_fetch} -> {local_path}")
        if process_page(url_to_fetch, local_path, URL_MAP_FILE, BASE_STRUCTURIZR_URL):
            processed_count += 1
        else:
            failed_count += 1
            logging.error(f"Failed to process {url_to_fetch}")

    logging.info("--------------------------------------------------")
    logging.info(f"Batch processing complete.")
    logging.info(f"Successfully processed files: {processed_count}")
    logging.info(f"Failed to process files: {failed_count}")
    logging.info("--------------------------------------------------")

if __name__ == "__main__":
    batch_process()
