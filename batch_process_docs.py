import json
import logging
from process_doc_page import process_page, load_maps

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s') # Set to INFO for this run

HTML_URL_MAP_FILE = "html_url_map.json"
ASSET_URL_MAP_FILE = "asset_url_map.json"
BASE_STRUCTURIZR_URL = "https://docs.structurizr.com"

# Define a small subset of URLs to process for demonstration purposes
URL_SUBSET_TO_PROCESS = [
    "https://docs.structurizr.com/dsl/example",       # Has /assets/ image
    "https://docs.structurizr.com/dsl/tutorial",       # Has /dsl/tutorial images, ensure non-slashed is fetched
    "https://docs.structurizr.com/ui/diagrams/notation", # Has many images, some /ui/bootstrap-icons/
    "https://docs.structurizr.com/dsl/cookbook/system-context-view/", # Cookbook item (needs slash)
    "https://docs.structurizr.com/quickstart"            # General page
]

def batch_process_subset():
    html_url_map, _ = load_maps(HTML_URL_MAP_FILE, ASSET_URL_MAP_FILE) # asset_map loaded by process_page

    if not html_url_map:
        logging.error("HTML URL map is empty or failed to load. Exiting batch process.")
        return

    processed_count = 0
    failed_count = 0

    logging.info(f"Processing a defined subset of {len(URL_SUBSET_TO_PROCESS)} URLs.")

    for url_to_fetch_key in URL_SUBSET_TO_PROCESS:
        # Find the corresponding local_path from the full html_url_map
        # The keys in URL_SUBSET_TO_PROCESS should reflect how they are best fetched (slashed/non-slashed)
        # and how they exist in html_url_map as primary keys for a given local_path.

        local_path = html_url_map.get(url_to_fetch_key)
        actual_url_to_fetch = url_to_fetch_key

        # If the exact key isn't found, it might be due to crawler storing both (e.g. url and url/)
        # and the subset list using one form. Try the other form.
        if not local_path:
            if url_to_fetch_key.endswith('/'):
                alternative_url = url_to_fetch_key.rstrip('/')
            else:
                alternative_url = url_to_fetch_key + '/'

            local_path = html_url_map.get(alternative_url)
            if local_path:
                logging.info(f"Using alternative URL '{alternative_url}' for key '{url_to_fetch_key}'")
                actual_url_to_fetch = alternative_url

        if not local_path:
            logging.error(f"URL key '{url_to_fetch_key}' (and its alternative) not found in html_url_map.json. Skipping.")
            failed_count +=1
            continue

        logging.info(f"Queueing for processing: {actual_url_to_fetch} (target: {local_path})")
        if process_page(actual_url_to_fetch, local_path, HTML_URL_MAP_FILE, ASSET_URL_MAP_FILE, BASE_STRUCTURIZR_URL):
            processed_count += 1
        else:
            failed_count += 1
            logging.error(f"Failed to process page {actual_url_to_fetch}")

    logging.info("--------------------------------------------------")
    logging.info(f"Subset batch processing complete.")
    logging.info(f"Successfully processed HTML pages: {processed_count}")
    logging.info(f"Failed to process HTML pages: {failed_count}")
    logging.info("--------------------------------------------------")

if __name__ == "__main__":
    # Set logging to DEBUG for process_page for this specific run if more detail is needed
    # current_log_level = logging.getLogger().getEffectiveLevel()
    # logging.getLogger().setLevel(logging.DEBUG)

    batch_process_subset()

    # logging.getLogger().setLevel(current_log_level) # Restore if changed
