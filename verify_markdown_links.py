import os
import re
from pathlib import Path
import argparse

def verify_links(markdown_root_dir):
    broken_links = []
    markdown_files = list(Path(markdown_root_dir).rglob('*.md'))
    print(f"Found {len(markdown_files)} Markdown files to check in {markdown_root_dir}")

    for md_file_path in markdown_files:
        try:
            content = md_file_path.read_text(encoding='utf-8')
            # Regex to find Markdown links: [text](url)
            # It won't find reference-style links like [text][label]
            for match in re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', content):
                link_text = match.group(1)
                link_url = match.group(2)

                if not link_url or link_url.startswith(('http://', 'https://', 'mailto:', '#')):
                    # Skip absolute URLs, mailto links, and pure anchor links
                    continue

                # Remove anchor from URL if present
                url_no_anchor = link_url.split('#')[0]
                if not url_no_anchor: # If link was only an anchor e.g. [text](#anchor)
                    continue


                current_dir = md_file_path.parent
                target_path = current_dir / url_no_anchor

                try:
                    # Resolve path (handles .., ., etc.) and check existence
                    # Using resolve() can be tricky if symlinks are involved or paths go outside a certain root
                    # A simpler normalization and check:
                    normalized_target_path = target_path.resolve(strict=False) # strict=False to allow resolving non-existent paths for checking
                except Exception as e:
                    # This can happen if path is malformed, e.g. invalid characters after many ../
                    broken_links.append({
                        "source_file": str(md_file_path),
                        "link_text": link_text,
                        "original_url": link_url,
                        "resolved_target": f"Error resolving path: {target_path} ({e})" ,
                        "status": "Error resolving path"
                    })
                    continue


                if not normalized_target_path.is_file():
                    broken_links.append({
                        "source_file": str(md_file_path),
                        "link_text": link_text,
                        "original_url": link_url,
                        "resolved_target": str(normalized_target_path),
                        "status": "File not found"
                    })

        except Exception as e:
            print(f"Error processing file {md_file_path}: {e}")
            broken_links.append({
                "source_file": str(md_file_path),
                "link_text": "N/A",
                "original_url": "N/A",
                "resolved_target": f"Error reading/parsing file: {e}",
                "status": "File processing error"
            })


    if not broken_links:
        print("No broken internal links found.")
    else:
        print(f"Found {len(broken_links)} broken internal links:")
        for link_info in broken_links:
            print(f"  Source: {link_info['source_file']}")
            print(f"    Text: \"{link_info['link_text']}\"")
            print(f"    URL: \"{link_info['original_url']}\"")
            print(f"    Resolved Target: \"{link_info['resolved_target']}\" ({link_info['status']})")
            print("-" * 20)

    return broken_links

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify internal Markdown links.")
    parser.add_argument("markdown_dir", help="Root directory containing Markdown files.")
    args = parser.parse_args()

    verify_links(args.markdown_dir)
