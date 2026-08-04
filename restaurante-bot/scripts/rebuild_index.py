"""CLI: rebuild the ChromaDB index from data/menu.md.

Requires OPENAI_API_KEY. Gracefully errors with a clear message otherwise.

Usage:
    python scripts/rebuild_index.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.rag import indexer

config.setup_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Index rebuild started")
    try:
        count = indexer.build_index(refresh=True)
    except RuntimeError as exc:
        logger.exception("Index rebuild failed")
        print(f"[error] {exc}")
        print("Hint: copy `.env.example` to `.env` and add your OPENAI_API_KEY.")
        raise SystemExit(1)
    logger.info("Index rebuild finished: %d document(s)", count)
    print(f"Index rebuilt: {count} documents in {config.CHROMA_DIR}")


if __name__ == "__main__":
    main()
