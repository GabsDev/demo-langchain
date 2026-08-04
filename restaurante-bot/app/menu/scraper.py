"""Web scraping of a restaurant site URL into markdown for the menu."""
from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup

from app.menu import llm_clean

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
MAX_CHARS = 30000


def scrape_menu(url: str, timeout: int = 15) -> str:
    """Fetch a restaurant URL and return its main visible text as plain text.

    No API key required; this is pure requests + BeautifulSoup extraction.
    """
    logger.info("Scraping menu from URL: %s", url)
    response = requests.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=timeout
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(
        ["script", "style", "noscript", "header", "footer", "nav", "form", "aside", "iframe"]
    ):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    lines = [line for line in text.splitlines() if line.strip()]
    cleaned = "\n".join(lines)[:MAX_CHARS]
    if not cleaned.strip():
        raise ValueError(f"No readable content found at {url}")
    logger.info(
        "Scraped %s -> %d char(s) (truncated at %d)", url, len(cleaned), MAX_CHARS
    )
    return cleaned


def scrape_to_canonical(url: str, timeout: int = 15) -> tuple[str, bool]:
    """Scrape a URL and (if a key is present) structurize it with GPT-4o-mini.

    Returns (canonical_markdown, used_llm).
    """
    raw = scrape_menu(url, timeout=timeout)
    markdown, used_llm = llm_clean.clean_with_llm(raw)
    logger.info("Scraped URL to canonical: %s (used_llm=%s)", url, used_llm)
    return markdown, used_llm
