"""CLI: ingest a restaurant menu PDF into data/menu.md.

Usage:
    python scripts/ingest_pdf.py path/to/menu.pdf
    python scripts/ingest_pdf.py path/to/menu.pdf --output data/menu.md
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.menu.pdf_loader import pdf_to_canonical

config.setup_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a restaurant menu PDF into canonical markdown")
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("--output", default=str(config.MENU_PATH), help="Output markdown path")
    args = parser.parse_args()

    logger.info("PDF ingest started: %s -> %s", args.pdf, args.output)
    try:
        markdown, used_llm = pdf_to_canonical(args.pdf)
    except Exception as exc:
        logger.exception("PDF ingest failed for %s", args.pdf)
        print(f"[error] {exc}")
        raise SystemExit(1)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    logger.info("PDF ingest finished: %s (used_llm=%s)", args.pdf, used_llm)

    if used_llm:
        print(f"PDF parsed and structurized with GPT-4o-mini -> {output}")
    else:
        print(
            f"PDF text extracted WITHOUT LLM cleanup (no OPENAI_API_KEY). "
            f"Raw text written to {output}. "
            f"Review it manually or rerun with OPENAI_API_KEY set for structurization."
        )


if __name__ == "__main__":
    main()
