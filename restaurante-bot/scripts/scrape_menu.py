"""CLI: scrape a restaurant site URL into data/menu.md.

Usage:
    python scripts/scrape_menu.py https://example.com/menu
    python scripts/scrape_menu.py https://example.com/menu --output data/menu.md
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.menu.scraper import scrape_to_canonical

config.setup_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape a restaurant URL into canonical markdown")
    parser.add_argument("url", help="URL of the restaurant site")
    parser.add_argument("--output", default=str(config.MENU_PATH), help="Output markdown path")
    args = parser.parse_args()

    logger.info("Scrape ingest started: %s -> %s", args.url, args.output)
    try:
        markdown, used_llm = scrape_to_canonical(args.url)
    except Exception as exc:
        logger.exception("Scrape ingest failed for %s", args.url)
        print(f"[error] {exc}")
        raise SystemExit(1)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    logger.info("Scrape ingest finished: %s (used_llm=%s)", args.url, used_llm)

    if used_llm:
        print(f"URL scraped and structurized with GPT-4o-mini -> {output}")
    else:
        print(
            f"URL scraped WITHOUT LLM cleanup (no OPENAI_API_KEY). "
            f"Raw text written to {output}. "
            f"Review it manually or rerun with OPENAI_API_KEY set for structurization."
        )


if __name__ == "__main__":
    main()
