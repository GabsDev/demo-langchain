"""Build and refresh the persistent ChromaDB collection from data/menu.md."""
from __future__ import annotations

import inspect
import logging

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from app import config
from app.menu.canonical import format_price, load_menu

logger = logging.getLogger(__name__)

COLLECTION_NAME = "menu"

# langchain_chroma >= 1.x computes the embeddings inside `add_texts` and only
# receives an explicit `embeddings` kwarg through **kwargs, where it is ignored.
# When the kwarg is not an explicit parameter we fall back to
# `Chroma.from_documents` (which re-embeds) after the delete.
_ADD_TEXTS_ACCEPTS_EMBEDDINGS = "embeddings" in inspect.signature(
    Chroma.add_texts
).parameters


def _embeddings() -> OpenAIEmbeddings:
    config.require_openai_key()
    return OpenAIEmbeddings(model=config.EMBEDDING_MODEL)


def _vectorstore() -> Chroma:
    config.require_openai_key()
    return Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(config.CHROMA_DIR),
        embedding_function=_embeddings(),
    )


def _build_documents(menu) -> list[Document]:
    """Chunk the menu into per-item docs plus section and catalog summaries.

    Every item gets its own document (precise lookups). Each non-empty section
    also gets a summary listing all its items, and the whole menu is summarized
    in one catalog document, so broad questions ("what drinks do you sell?")
    can be answered from a single retrieved document.
    """
    docs: list[Document] = []

    def _item_summary(item) -> str:
        summary = f"{item.name} ({format_price(item.price)})"
        if item.description:
            summary += f" — {item.description}"
        return summary

    catalog_lines = [f"MENU of {menu.restaurant_name}"]
    for section in menu.sections:
        if not section.items:
            continue
        item_lines = [_item_summary(item) for item in section.items]
        docs.append(
            Document(
                page_content="\n".join(
                    [f"SECTION: {section.name}", "ITEMS:"] + item_lines
                ),
                metadata={"section": section.name, "type": "section"},
            )
        )
        catalog_lines.append(
            f"Sección {section.name}: "
            + ", ".join(
                f"{item.name} ({format_price(item.price)})" for item in section.items
            )
        )
        for item in section.items:
            content = "\n".join(
                [
                    f"SECTION: {section.name}",
                    f"ITEM: {item.name}",
                    f"PRICE: {format_price(item.price)}",
                    f"DESCRIPTION: {item.description}" if item.description else "",
                    f"TAGS: {', '.join(item.tags)}" if item.tags else "",
                ]
            )
            docs.append(
                Document(
                    page_content=content,
                    metadata={
                        "section": section.name,
                        "item": item.name,
                        "price": item.price,
                        "type": "item",
                    },
                )
            )

    docs.append(
        Document(
            page_content="\n".join(catalog_lines),
            metadata={"type": "catalog"},
        )
    )
    return docs


def _replace_collection(docs: list[Document]) -> None:
    """Swap the collection contents through the Chroma API, without touching disk.

    Embeddings are computed BEFORE anything is deleted, so a failure (missing
    API key, network error) leaves the existing index intact. The stale
    documents are then removed via `collection.delete()` and the new ones are
    added, which works while the collection files are open on Windows because
    it rewrites the index instead of unlinking in-use files.
    """
    embeddings = _embeddings().embed_documents([d.page_content for d in docs])
    vectorstore = _vectorstore()
    stale_ids = vectorstore.get(include=[])["ids"]
    if stale_ids:
        logger.info(
            "Removing %d stale document(s) from collection '%s'",
            len(stale_ids), COLLECTION_NAME,
        )
        vectorstore.delete(ids=stale_ids)
    else:
        logger.info("Collection '%s' has no documents to remove", COLLECTION_NAME)
    if _ADD_TEXTS_ACCEPTS_EMBEDDINGS:
        vectorstore.add_texts(
            texts=[d.page_content for d in docs],
            metadatas=[d.metadata for d in docs],
            embeddings=embeddings,
        )
    else:
        # The installed langchain_chroma re-embeds internally on add_texts, so
        # use from_documents after the delete as the sanctioned fallback.
        Chroma.from_documents(
            docs,
            _embeddings(),
            collection_name=COLLECTION_NAME,
            persist_directory=str(config.CHROMA_DIR),
        )
    logger.info(
        "Indexed %d document(s) into collection '%s'", len(docs), COLLECTION_NAME
    )


def build_index(menu_path: str = str(config.MENU_PATH), refresh: bool = True) -> int:
    """Build (or refresh) the ChromaDB index from the canonical menu.

    Requires OPENAI_API_KEY. Returns the number of documents indexed.

    The refresh is always a clean swap: stale documents are removed through the
    Chroma API and the new ones are added afterwards, so it works while the
    running server keeps `data/chroma` open on Windows (no files are deleted).
    `refresh` is kept for signature compatibility; the swap is clean either way.
    """
    config.require_openai_key()
    logger.info(
        "Building index from %s into collection '%s'", menu_path, COLLECTION_NAME
    )
    menu = load_menu(menu_path)
    if not menu.items:
        logger.warning("Menu is empty at %s; nothing to index", menu_path)
        raise ValueError(
            "The menu is empty. Run `python scripts/seed_menu.py` first or add "
            "items via `app.menu.manual`."
        )
    docs = _build_documents(menu)
    try:
        _replace_collection(docs)
    except Exception:
        logger.exception("Chroma indexing failed for %s", menu_path)
        raise
    logger.info(
        "Index finished: %d documents for %d menu items in '%s'",
        len(docs), len(menu.items), COLLECTION_NAME,
    )
    return len(docs)


def count() -> int:
    """Return the number of documents in the collection (0 if not built)."""
    config.require_openai_key()
    if not config.CHROMA_DIR.exists():
        logger.debug("Chroma collection '%s' not built yet", COLLECTION_NAME)
        return 0
    vectorstore = _vectorstore()
    docs = len(vectorstore.get(include=[])["ids"])
    logger.debug("Collection '%s' contains %d document(s)", COLLECTION_NAME, docs)
    return docs


def collection_exists() -> bool:
    """Best-effort check for an existing, non-empty collection."""
    try:
        return count() > 0
    except Exception:
        logger.warning("Could not verify collection '%s' existence", COLLECTION_NAME)
        return False
