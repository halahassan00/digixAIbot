import requests
from bs4 import BeautifulSoup
import os
import time
from pages import STATIC_PAGES, DYNAMIC_SECTIONS

# Where raw text files will be saved
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "raw")


def fetch_page(url):
    """Fetch the HTML content of a URL."""
    headers = {
        # Pretend to be a browser — some sites block Python requests without this
        "User-Agent": "Mozilla/5.0 (compatible; research-scraper/1.0)"
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()  # Raises an error if the request failed
    return response.text


def extract_text(html):
    """Parse HTML and extract clean readable text."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove tags that never contain useful content
    for tag in soup(["script", "style", "nav", "footer", "head", "noscript"]):
        tag.decompose()

    # Get all remaining text
    text = soup.get_text(separator="\n")

    # Clean up excessive whitespace and blank lines
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]  # Remove empty lines
    clean_text = "\n".join(lines)

    return clean_text


def save_text(text, filename):
    """Save extracted text to a file in the raw directory."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  Saved: {filepath}")


def discover_child_pages(section):
    """
    Visit a section page and find all child page links within a given path.
    Returns a list of page dicts ready to scrape — empty list if none found.
    """
    print(f"  Checking for child pages under: {section['base_url']}")
    try:
        html = fetch_page(section["base_url"])
        soup = BeautifulSoup(html, "html.parser")

        child_pages = []
        seen = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]

            # Normalize relative URLs to absolute
            if href.startswith("/"):
                href = "https://digix-ai.com" + href

            # Only follow links within the defined child path
            if section["child_path"] in href and href not in seen:
                seen.add(href)

                # Generate a filename from the URL slug
                slug = href.rstrip("/").split("/")[-1]
                filename = f"{section['category']}_{slug}.txt"

                child_pages.append({
                    "url": href,
                    "category": section["category"],
                    "filename": filename
                })
                print(f"    Found: {href}")

        if not child_pages:
            print(f"    No child pages found yet — skipping.")

        return child_pages

    except Exception as e:
        print(f"    ERROR discovering child pages: {e}")
        return []

def scrape_all():
    """Scrape all pages defined in pages.py."""

    pages_to_scrape = list(STATIC_PAGES)

    for section in DYNAMIC_SECTIONS:
        children = discover_child_pages(section)
        pages_to_scrape.extend(children)

    print(f"Starting scrape of {len(pages_to_scrape)} pages...\n")


    for page in pages_to_scrape:
        print(f"Scraping: {page['url']}")
        try:
            html = fetch_page(page["url"])
            text = extract_text(html)
            save_text(text, page["filename"])
            print(f"  Words extracted: {len(text.split())}")
        except Exception as e:
            print(f"  ERROR: {e}")

        # Be polite — wait 1 second between requests
        time.sleep(1)

    print("\nDone.")


if __name__ == "__main__":
    scrape_all()
