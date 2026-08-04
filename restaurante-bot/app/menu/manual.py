"""Programmatic, manual menu editing against the canonical data/menu.md."""
from __future__ import annotations

import logging

from app import config
from app.menu.canonical import Menu, MenuItem, load_or_empty, save_menu

logger = logging.getLogger(__name__)


def _load() -> Menu:
    return load_or_empty(config.MENU_PATH)


def add_item(
    section: str,
    name: str,
    price: float,
    description: str = "",
    tags: list[str] | None = None,
) -> MenuItem:
    """Add an item to a section and persist."""
    menu = _load()
    item = menu.add_item(section, MenuItem(
        name=name, price=price, description=description, tags=tags or []
    ))
    save_menu(menu, config.MENU_PATH)
    logger.info("Manually added menu item %r in section %r", name, section)
    return item


def update_item(name: str, **changes) -> MenuItem | None:
    """Update fields of an existing item (price, description, tags, section)."""
    menu = _load()
    item = menu.update_item(name, **changes)
    if item is not None:
        save_menu(menu, config.MENU_PATH)
        logger.info("Manually updated menu item %r (%s)", name, ", ".join(changes))
    else:
        logger.warning("Manual update skipped: item %r not found", name)
    return item


def remove_item(name: str) -> bool:
    """Remove an item by name. Returns True if it was found."""
    menu = _load()
    removed = menu.remove_item(name)
    if removed:
        save_menu(menu, config.MENU_PATH)
        logger.info("Manually removed menu item %r", name)
    else:
        logger.warning("Manual removal skipped: item %r not found", name)
    return removed


def list_items() -> list[MenuItem]:
    """Return every item currently in the canonical menu."""
    return _load().items
