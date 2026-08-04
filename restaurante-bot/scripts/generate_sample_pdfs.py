"""Generate three sample restaurant menu PDFs (Argentine, Mexican, Costa Rican) for testing.

Run: python scripts/generate_sample_pdfs.py

Writes:
    sample_menus/menu_argentino.pdf
    sample_menus/menu_mexicano.pdf
    sample_menus/menu_costarricense.pdf

Upload any PDF to the Telegram bot (or ingest it with scripts/ingest_pdf.py)
to test the "replace the whole menu" feature.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app import config
from app.menu import canonical
from app.menu.pdf_export import (
    _FALLBACK_FAMILY,
    _MENU_FONT_BOLD,
    _register_currency_font,
)

config.setup_logging()
logger = logging.getLogger(__name__)

OUTPUT_DIR = config.BASE_DIR / "sample_menus"

# Section -> list of (item name, price in CRC, short description)
ARGENTINE_MENU = {
    "restaurant_name": "El Gauchito",
    "tagline": "Sabores argentinos: asado, empanadas y milanesas como en casa.",
    "sections": [
        (
            "Entradas",
            [
                ("Empanadas de carne", 1800, "Masa casera rellena de carne cortada a cuchillo, huevo y aceitunas."),
                ("Provoleta", 4200, "Provolone fundido a la parrilla con orégano y pimienta."),
            ],
        ),
        (
            "Platos Fuertes",
            [
                ("Milanesa napolitana", 7500, "Milanesa de carne con salsa de tomate, jamón y muzzarella, con papas fritas."),
                ("Asado de tira", 12000, "Tira de asado a la parrilla, jugosa y tierna."),
                ("Bondiola", 9000, "Bondiola de cerdo a la parrilla, glaseada con cerveza rubia."),
            ],
        ),
        (
            "Bebidas",
            [
                ("Gaseosa", 1200, "Refresco bien frío, 500 ml."),
                ("Cerveza", 2500, "Rubia clásica bien tirada."),
                ("Agua", 900, "Agua mineral con o sin gas."),
            ],
        ),
        (
            "Postres",
            [
                ("Flan con dulce de leche", 2000, "Flan casero bañado con dulce de leche."),
                ("Helado", 2500, "Dos bochas de helado artesanal, gustos a elección."),
            ],
        ),
    ],
}

MEXICAN_MENU = {
    "restaurant_name": "La Taquería",
    "tagline": "Cocina mexicana auténtica: tacos, enchiladas y pozole.",
    "sections": [
        (
            "Entradas",
            [
                ("Guacamole con totopos", 3500, "Aguacate fresco machacado con totopos crujientes."),
                ("Nachos", 3000, "Totopos con queso fundido, jalapeños y frijoles."),
            ],
        ),
        (
            "Platos Fuertes",
            [
                ("Tacos al pastor", 2200, "Tortillas de maíz con cerdo al pastor, cebolla y cilantro."),
                ("Burrito de pollo", 4500, "Tortilla de harina rellena de pollo, arroz y frijoles."),
                ("Enchiladas verdes", 5000, "Tortillas rellenas de pollo bañadas en salsa verde."),
                ("Pozole", 6500, "Sopa tradicional de maíz con cerdo y guarniciones."),
            ],
        ),
        (
            "Bebidas",
            [
                ("Horchata", 1500, "Bebida de arroz y canela, bien fría."),
                ("Jamaica", 1500, "Agua de flor de jamaica."),
                ("Cerveza", 2200, "Cerveza bien fría, 355 ml."),
            ],
        ),
        (
            "Postres",
            [
                ("Churros con chocolate", 2800, "Churros espolvoreados con azúcar y chocolate caliente."),
                ("Flan mexicano", 2200, "Flan de huevo con caramelo."),
            ],
        ),
    ],
}


COSTA_RICAN_MENU = {
    "restaurant_name": "Soda La Tica",
    "tagline": "Comida casera costarricense: casados, gallos y fresco natural.",
    "sections": [
        (
            "Desayunos",
            [
                ("Gallo pinto", 2800, "Arroz y frijoles con natilla, queso y café chorreado."),
                ("Gallo pinto con huevo", 3500, "Gallo pinto acompañado de huevo revuelto o frito."),
                ("Chorreada", 2000, "Tortilla dulce de maíz tierno con natilla."),
            ],
        ),
        (
            "Casados",
            [
                ("Casado de pollo", 4500, "Arroz, frijoles, ensalada de repollo, plátano maduro y pollo."),
                ("Casado de carne", 5000, "Arroz, frijoles, ensalada, plátano maduro y carne picada."),
                ("Casado de pescado", 5500, "Arroz, frijoles, ensalada, plátano maduro y pescado al ajillo."),
                ("Casado de cerdo", 5000, "Arroz, frijoles, ensalada, plátano maduro y cerdo en salsa."),
            ],
        ),
        (
            "Platos Típicos",
            [
                ("Chifrijo", 4800, "Chicharrones, frijoles molidos, pico de gallo y arroz con tortillas."),
                ("Olla de carne", 6500, "Sopa de res con yuca, papa, elote, ayote y repollo."),
                ("Sopa negra", 3800, "Sopa de frijol negro con huevo duro y culantro."),
                ("Tamal de cerdo", 2200, "Masa de maíz rellena de cerdo, arroz y verduras, envuelto en hoja de plátano."),
                ("Arreglado de queso", 1800, "Gallo de queso derretido con cebolla y culantro."),
                ("Arreglado de carne", 2500, "Gallo de carne mechada con ensalada fresca."),
                ("Empanada de papa", 1500, "Empanada de maíz rellena de papa con picadillo."),
            ],
        ),
        (
            "Bebidas",
            [
                ("Fresco de mora", 1200, "Fresco natural de mora, con leche o al agua."),
                ("Fresco de tamarindo", 1200, "Fresco natural de tamarindo bien frío."),
                ("Fresco de cas", 1200, "Fresco natural de cas, con leche o al agua."),
                ("Horchata", 1500, "Bebida de arroz y canela."),
                ("Café chorreado", 800, "Café de la zona, colado en bolsita."),
                ("Gaseosa", 1200, "Refresco bien frío, 500 ml."),
                ("Agua", 900, "Agua mineral con o sin gas."),
            ],
        ),
        (
            "Postres",
            [
                ("Arroz con leche", 1500, "Arroz con leche casero con canela."),
                ("Tres leches", 2000, "Queque suave bañado en tres leches."),
                ("Queque seco", 1200, "Queque seco de la casa, perfecto con café."),
            ],
        ),
    ],
}


def _escape(text: str) -> str:
    """Escape a string for reportlab Paragraph markup."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _build_pdf(
    restaurant_name: str,
    tagline: str,
    sections: list[tuple[str, list[tuple[str, float, str]]]],
    out_path: Path,
) -> None:
    """Render a clean A4 menu PDF: title, sections, items with price + description."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"{restaurant_name} — Menú",
        author=restaurant_name,
    )
    styles = getSampleStyleSheet()
    family = _register_currency_font()
    title_bold = _MENU_FONT_BOLD if family != _FALLBACK_FAMILY else "Helvetica-Bold"
    title_style = ParagraphStyle(
        "SampleTitle",
        parent=styles["Title"],
        fontSize=24,
        leading=28,
        textColor=HexColor("#1d1d1f"),
        spaceAfter=4,
        fontName=family,
        boldFontName=title_bold,
    )
    tagline_style = ParagraphStyle(
        "SampleTagline",
        parent=styles["BodyText"],
        fontSize=11,
        leading=15,
        spaceAfter=12,
        textColor=HexColor("#555555"),
        fontName=family,
    )
    section_style = ParagraphStyle(
        "SampleSection",
        parent=styles["Heading2"],
        fontSize=15,
        leading=18,
        spaceBefore=16,
        spaceAfter=6,
        textColor=HexColor("#b8860b"),
        fontName=family,
    )
    item_style = ParagraphStyle(
        "SampleItem",
        parent=styles["BodyText"],
        fontSize=11,
        leading=14,
        leftIndent=10,
        spaceAfter=2,
        fontName=family,
    )
    desc_style = ParagraphStyle(
        "SampleDesc",
        parent=styles["BodyText"],
        fontSize=10,
        leading=13,
        leftIndent=10,
        spaceAfter=10,
        textColor=HexColor("#777777"),
        fontName=family,
    )

    story = [Paragraph(_escape(restaurant_name), title_style)]
    story.append(Paragraph(_escape(tagline), tagline_style))

    for section_name, items in sections:
        story.append(Paragraph(_escape(section_name), section_style))
        for name, price, description in items:
            story.append(
                Paragraph(
                    f"{_escape(name)} — {canonical.format_price(price)}",
                    item_style,
                )
            )
            if description:
                story.append(Paragraph(_escape(description), desc_style))
        story.append(Spacer(1, 4))

    doc.build(story)
    logger.info("Sample menu PDF generated at %s", out_path)


def main() -> None:
    output_argentine = OUTPUT_DIR / "menu_argentino.pdf"
    output_mexican = OUTPUT_DIR / "menu_mexicano.pdf"
    output_costarricense = OUTPUT_DIR / "menu_costarricense.pdf"

    _build_pdf(
        ARGENTINE_MENU["restaurant_name"],
        ARGENTINE_MENU["tagline"],
        ARGENTINE_MENU["sections"],
        output_argentine,
    )
    _build_pdf(
        MEXICAN_MENU["restaurant_name"],
        MEXICAN_MENU["tagline"],
        MEXICAN_MENU["sections"],
        output_mexican,
    )
    _build_pdf(
        COSTA_RICAN_MENU["restaurant_name"],
        COSTA_RICAN_MENU["tagline"],
        COSTA_RICAN_MENU["sections"],
        output_costarricense,
    )

    for path in (output_argentine, output_mexican, output_costarricense):
        size = path.stat().st_size
        print(f"Generated {path} ({size} bytes)")
    print(f"\nUpload one of these PDFs to the Telegram bot to test the menu replace feature.")


if __name__ == "__main__":
    main()
