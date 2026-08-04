"""PDF -> markdown ingestion for the restaurant menu."""
from __future__ import annotations

import logging
from pathlib import Path

from app.menu import llm_clean

logger = logging.getLogger(__name__)


def pdf_to_markdown(pdf_path: str | Path) -> str:
    """Extract raw text from a PDF using pdfplumber. No API key required."""
    import pdfplumber

    path = Path(pdf_path)
    logger.info("Extracting text from PDF: %s", path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
    raw = "\n".join(pages)
    if not raw.strip():
        raise ValueError(f"No text could be extracted from {path.name}")
    logger.info(
        "PDF extracted: %s -> %d page(s), %d char(s)",
        path.name, len(pages), len(raw),
    )
    return raw


def pdf_to_canonical(pdf_path: str | Path) -> tuple[str, bool]:
    """Extract PDF text and (if a key is present) structurize it with GPT-4o-mini.

    Returns (canonical_markdown, used_llm). Without an API key the raw text is
    returned and the caller should review it manually.
    """
    raw = pdf_to_markdown(pdf_path)
    markdown, used_llm = llm_clean.clean_with_llm(raw)
    logger.info(
        "PDF to canonical: %s (used_llm=%s)", Path(pdf_path).name, used_llm
    )
    return markdown, used_llm
