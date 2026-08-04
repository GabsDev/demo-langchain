"""Canonical menu model, parser and writer.

The canonical menu lives in `data/menu.md` using this format:

    # Restaurant name

    Tagline line.

    ## Entradas

    ### Empanada de carne

    - Precio: ₡1,500
    - Descripción: Masa casera rellena con carne, huevo y aceitunas.
    - Tags: empanada, carne, horneada

All ingestion paths (manual, PDF, scraping) normalize into this format.
"""
from __future__ import annotations

import logging
import re
from difflib import get_close_matches
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PRICE_STRIP_RE = re.compile(r"[^\d.,]")
WORD_RE = re.compile(r"\w+")

DEFAULT_SECTION = "General"


class MenuItem(BaseModel):
    id: str = ""
    name: str
    price: float = 0.0
    description: str = ""
    section: str = ""
    tags: list[str] = Field(default_factory=list)


class MenuSection(BaseModel):
    name: str
    items: list[MenuItem] = Field(default_factory=list)


class Menu(BaseModel):
    restaurant_name: str = "Restaurante"
    tagline: str = ""
    sections: list[MenuSection] = Field(default_factory=list)

    @property
    def items(self) -> list[MenuItem]:
        return [item for section in self.sections for item in section.items]

    def find_item(self, name: str) -> MenuItem | None:
        target = name.lower()
        return next((item for item in self.items if item.name.lower() == target), None)

    def find_item_by_id(self, item_id: str) -> MenuItem | None:
        return next((item for item in self.items if item.id == item_id), None)

    def _section_of(self, item: MenuItem) -> MenuSection | None:
        return next(
            (section for section in self.sections
             if any(candidate is item for candidate in section.items)),
            None,
        )

    def move_item(self, item_id: str, section_name: str) -> MenuItem | None:
        """Move an item to another section by id. Returns the item or None."""
        item = self.find_item_by_id(item_id)
        if item is None:
            return None
        current = self._section_of(item)
        if current is not None:
            current.items = [candidate for candidate in current.items
                             if candidate is not item]
        item.section = section_name
        self.ensure_section(section_name).items.append(item)
        logger.debug("Menu item moved: %r -> section %r", item.name, section_name)
        return item

    def remove_item_by_id(self, item_id: str) -> bool:
        """Remove an item by id. Returns True if it was found."""
        item = self.find_item_by_id(item_id)
        if item is None:
            return False
        current = self._section_of(item)
        if current is not None:
            current.items = [candidate for candidate in current.items
                             if candidate is not item]
        logger.debug("Menu item removed by id: %r", item_id)
        return True

    def remove_section(self, name: str) -> bool:
        """Remove a whole section (and its items). Returns True if found."""
        before = len(self.sections)
        self.sections = [
            section for section in self.sections
            if section.name.lower() != name.lower()
        ]
        if len(self.sections) != before:
            logger.debug("Menu section removed: %r", name)
            return True
        return False

    def ensure_section(self, name: str) -> MenuSection:
        section = next(
            (s for s in self.sections if s.name.lower() == name.lower()), None
        )
        if section is None:
            section = MenuSection(name=name)
            self.sections.append(section)
        return section

    def add_item(self, section_name: str, item: MenuItem) -> MenuItem:
        item.section = section_name
        self.ensure_section(section_name).items.append(item)
        logger.debug("Menu item added: %r in section %r", item.name, section_name)
        return item

    def remove_item(self, name: str) -> bool:
        target = name.lower()
        for section in self.sections:
            before = len(section.items)
            section.items = [
                item for item in section.items if item.name.lower() != target
            ]
            if len(section.items) != before:
                logger.debug("Menu item removed: %r", name)
                return True
        return False

    def update_item(self, name: str, **changes) -> MenuItem | None:
        item = self.find_item(name)
        if item is None:
            return None
        for key, value in changes.items():
            if key == "tags" and isinstance(value, str):
                value = [t.strip() for t in value.split(",") if t.strip()]
            setattr(item, key, value)
        return item


def parse_price(raw: str) -> float:
    """Parse a price string like '₡12,500', '$1,200', '1.200' or '12,50' into a float."""
    cleaned = PRICE_STRIP_RE.sub("", raw)
    if not cleaned:
        return 0.0
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) > 1 and len(parts[-1]) == 3:
            cleaned = cleaned.replace(".", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def format_price(price: float) -> str:
    """Render a price in Costa Rican colones, e.g. '₡12,500' or '₡12,500.75'.

    One helper used everywhere prices are displayed (menu, PDF, orders, RAG).
    """
    if float(price) == int(price):
        return f"₡{int(price):,}"
    return f"₡{price:,.2f}"


def parse_menu(text: str) -> Menu:
    """Parse canonical markdown text into a Menu model."""
    menu = Menu()
    section: MenuSection | None = None
    item: MenuItem | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            section = menu.ensure_section(line[3:].strip())
            item = None
        elif line.startswith("### "):
            if section is None:
                section = menu.ensure_section(DEFAULT_SECTION)
            item = MenuItem(name=line[4:].strip(), section=section.name)
            section.items.append(item)
        elif line.startswith("# "):
            menu.restaurant_name = line[2:].strip()
        elif item is not None:
            if line.startswith("- Precio:"):
                item.price = parse_price(line[len("- Precio:"):])
            elif line.startswith("- Descripción:"):
                item.description = line[len("- Descripción:"):].strip()
            elif line.startswith("- Tags:"):
                item.tags = [
                    tag.strip()
                    for tag in line[len("- Tags:"):].split(",")
                    if tag.strip()
                ]
        elif section is None:
            menu.tagline = (menu.tagline + " " + line).strip()
    return menu


def serialize_menu(menu: Menu) -> str:
    """Render a Menu model as canonical markdown."""
    lines = [f"# {menu.restaurant_name}", ""]
    if menu.tagline:
        lines.append(menu.tagline)
        lines.append("")
    for section in menu.sections:
        lines.append(f"## {section.name}")
        lines.append("")
        for item in section.items:
            lines.append(f"### {item.name}")
            lines.append("")
            lines.append(f"- Precio: {format_price(item.price)}")
            if item.description:
                lines.append(f"- Descripción: {item.description}")
            if item.tags:
                lines.append(f"- Tags: {', '.join(item.tags)}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def assign_item_ids(menu: Menu) -> None:
    """Assign stable runtime ids (`item-<n>` by order in the file) to items.

    Ids are a runtime concern: they are never persisted to menu.md, so they are
    recomputed deterministically on every load and stay stable as long as the
    item order in the file does not change.
    """
    for index, item in enumerate(menu.items, start=1):
        item.id = f"item-{index}"


def load_menu(path: str | Path) -> Menu:
    """Load a Menu from a canonical markdown file."""
    text = Path(path).read_text(encoding="utf-8")
    menu = parse_menu(text)
    assign_item_ids(menu)
    logger.info(
        "Menu loaded from %s: %d section(s), %d item(s)",
        path, len(menu.sections), len(menu.items),
    )
    return menu


def load_or_empty(path: str | Path) -> Menu:
    """Load a Menu, returning an empty one if the file does not exist yet."""
    if not Path(path).exists():
        logger.warning("Menu file not found at %s; returning empty menu", path)
        return Menu()
    return load_menu(path)


def save_menu(menu: Menu, path: str | Path) -> None:
    """Persist a Menu to a canonical markdown file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(serialize_menu(menu), encoding="utf-8")
    logger.info(
        "Menu saved to %s: %d section(s), %d item(s)",
        target, len(menu.sections), len(menu.items),
    )


def suggest_items(menu: Menu, query: str, k: int = 3) -> list[str]:
    """Suggest menu item names closest to `query` (fuzzy, token-based).

    Used when the LLM cannot match an item so the bot can offer the closest
    options to the customer.
    """
    if not menu.items:
        return []
    query_tokens = set(WORD_RE.findall(query.lower()))
    scored: list[tuple[int, str]] = []
    for item in menu.items:
        hay = " ".join([item.name] + item.tags).lower()
        hay_tokens = set(WORD_RE.findall(hay))
        overlap = len(query_tokens & hay_tokens)
        if overlap:
            scored.append((overlap, item.name))
    if scored:
        return [name for _, name in sorted(scored, reverse=True)[:k]]
    names = [item.name for item in menu.items]
    return get_close_matches(query, names, n=k, cutoff=0.4)


def format_menu_text(menu: Menu, max_chars: int = 3800) -> list[str]:
    """Render the menu as one or more Telegram-friendly chunks."""
    blocks: list[str] = []
    for section in menu.sections:
        if not section.items:
            continue
        text = f"🍽️ {section.name}"
        for item in section.items:
            text += f"\n▪️ {item.name} — {format_price(item.price)}"
            if item.description:
                text += f"\n   {item.description}"
        blocks.append(text)

    chunks: list[str] = []
    current = f"📋 {menu.restaurant_name}"
    for block in blocks:
        candidate = current + "\n\n" + block
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def menu_context_text(menu: Menu) -> str:
    """Plain-text rendering of the menu used as LLM context for order parsing."""
    lines = [f"# {menu.restaurant_name}"]
    for section in menu.sections:
        if not section.items:
            continue
        lines.append(f"## {section.name}")
        for item in section.items:
            tags = f" (tags: {', '.join(item.tags)})" if item.tags else ""
            desc = f" - {item.description}" if item.description else ""
            lines.append(f"- {item.name}: {format_price(item.price)}{desc}{tags}")
    return "\n".join(lines)
