"""Seed data/menu.md with a realistic restaurant demo menu (prices in CRC).

Run: python scripts/seed_menu.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.menu.canonical import Menu, MenuItem, save_menu

config.setup_logging()
logger = logging.getLogger(__name__)


def _item(name: str, price: float, description: str, tags: list[str]) -> MenuItem:
    return MenuItem(name=name, price=price, description=description, tags=tags)


def build_demo_menu() -> Menu:
    menu = Menu(
        restaurant_name="Parrilla La Esquina",
        tagline="Cocina argentina de barrio: asado, empanadas y milanesas como en casa.",
    )

    for item in [
        _item(
            "Empanada de carne",
            1500,
            "Masa casera rellena con carne cortada a cuchillo, huevo y aceitunas. Horneada al momento.",
            ["empanada", "carne", "horneada", "entrada"],
        ),
        _item(
            "Empanada de jamón y queso",
            1500,
            "Jamón cocido y queso derretido, horno de barro.",
            ["empanada", "jamon", "queso", "entrada"],
        ),
        _item(
            "Provoleta a la parrilla",
            4500,
            "Provolone fundido a la parrilla con orégano y pimienta.",
            ["provoleta", "queso", "parrilla", "entrada"],
        ),
        _item(
            "Rabas a la romana",
            5500,
            "Anillos de calamar rebozados, con limón y alioli.",
            ["rabas", "calamar", "fritura", "entrada"],
        ),
        _item(
            "Matambre a la pizza",
            6500,
            "Matambre tierno con tomate, muzzarella y orégano.",
            ["matambre", "pizza", "carne", "entrada"],
        ),
    ]:
        menu.add_item("Entradas", item)

    for item in [
        _item(
            "Milanesa napolitana",
            7500,
            "Milanesa de carne con salsa de tomate, jamón y muzzarella, con papas fritas.",
            ["milanesa", "napolitana", "carne", "plato"],
        ),
        _item(
            "Milanesa a caballo",
            8000,
            "Milanesa de carne con dos huevos fritos encima, acompañada de papas fritas.",
            ["milanesa", "caballo", "huevo", "carne", "plato"],
        ),
        _item(
            "Milanesa de pollo",
            7000,
            "Pechuga empanada y frita, con papas fritas o ensalada.",
            ["milanesa", "pollo", "plato"],
        ),
        _item(
            "Bife de chorizo",
            9500,
            "Corte de carne a la parrilla, punto a elección. Con ensalada o papas.",
            ["bife", "chorizo", "carne", "parrilla", "plato"],
        ),
        _item(
            "Asado de tira",
            12000,
            "Tira de asado a la parrilla, jugosa y tierna. Rinde para dos.",
            ["asado", "tira", "carne", "parrilla", "plato"],
        ),
        _item(
            "Pollo a la parrilla",
            7000,
            "Medio pollo a la parrilla con limón y guarnición a elección.",
            ["pollo", "parrilla", "plato"],
        ),
        _item(
            "Hamburguesa criolla",
            5500,
            "Pan casero, carne de vaca, lechuga, tomate y cheddar.",
            ["hamburguesa", "carne", "cheddar", "plato"],
        ),
        _item(
            "Tallarines con salsa",
            4500,
            "Tallarines frescos con salsa a elección: fileto, bolognesa o mixta.",
            ["tallarines", "pasta", "salsa", "plato"],
        ),
    ]:
        menu.add_item("Platos Fuertes", item)

    for item in [
        _item("Coca-Cola 500ml", 1200, "Gaseosa cola bien fría.", ["coca", "coca cola", "gaseosa"]),
        _item("Coca-Cola Zero 500ml", 1200, "Gaseosa cola sin azúcar.", ["coca", "coca cola", "zero", "gaseosa"]),
        _item("Sprite 500ml", 1200, "Gaseosa sabor lima-limón.", ["sprite", "gaseosa"]),
        _item("Fanta 500ml", 1200, "Gaseosa sabor naranja.", ["fanta", "gaseosa"]),
        _item("Agua mineral 500ml", 1000, "Agua mineral con o sin gas.", ["agua", "mineral"]),
        _item("Cerveza Quilmes 1L", 2500, "Rubia clásica bien tirada.", ["cerveza", "quilmes", "rubia"]),
        _item("Vino tinto de la casa", 3500, "Por copa. Malbec de Mendoza.", ["vino", "tinto", "malbec", "copa"]),
    ]:
        menu.add_item("Bebidas", item)

    for item in [
        _item(
            "Flan casero",
            2000,
            "Con dulce de leche o crema, a elección.",
            ["flan", "postre", "dulce de leche"],
        ),
        _item(
            "Helado artesanal",
            2200,
            "Dos bochas, gustos a elección.",
            ["helado", "bochas", "postre"],
        ),
        _item(
            "Panqueque con dulce de leche",
            2200,
            "Panqueque caliente con dulce de leche.",
            ["panqueque", "dulce de leche", "postre"],
        ),
        _item(
            "Tiramisú",
            2800,
            "Clásico italiano con mascarpone y café.",
            ["tiramisu", "cafe", "postre"],
        ),
    ]:
        menu.add_item("Postres", item)

    return menu


def main() -> None:
    logger.info("Seeding demo menu")
    menu = build_demo_menu()
    save_menu(menu, config.MENU_PATH)
    logger.info("Seeded %d item(s) across %d section(s)", len(menu.items), len(menu.sections))
    print(f"Seeded {len(menu.items)} items across {len(menu.sections)} sections -> {config.MENU_PATH}")
    for section in menu.sections:
        print(f"  - {section.name}: {len(section.items)} items")


if __name__ == "__main__":
    main()
