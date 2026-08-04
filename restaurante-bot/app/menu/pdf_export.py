"""Render the canonical menu as a clean A4 PDF using reportlab.

Cached: if the output file already exists and is newer than the menu source,
the existing PDF is reused instead of regenerating it on every request.
"""
from __future__ import annotations

import logging
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app import config
from app.menu import canonical

logger = logging.getLogger(__name__)

DEFAULT_OUT_PATH = Path(config.DATA_DIR) / "menu.pdf"
DOC_TITLE = "Menú"

# Bump whenever the PDF rendering changes so cached PDFs (guarded by a matching
# `.version` sidecar) are regenerated instead of being reused.
PDF_VERSION = 2

_CURRENCY_CODEPOINT = 0x20A1  # U+20A1 COLON SIGN (₡)
_MENU_FONT_REGULAR = "MenuFont"
_MENU_FONT_BOLD = "MenuFont-Bold"
_FALLBACK_FAMILY = "Helvetica"

# Candidate TrueType fonts that may contain the colón sign, in order of
# preference. Each entry is (regular_file, bold_candidates_in_same_dir). A font
# is only accepted when reportlab's own cmap parser maps U+20A1 to a glyph.
_FONT_CANDIDATES: list[tuple[Path, tuple[str, ...]]] = [
    (Path(r"C:\Windows\Fonts\DejaVuSans.ttf"), ("DejaVuSans-Bold.ttf",)),
    (Path(r"C:\Windows\Fonts\seguisym.ttf"), ()),
    (Path(r"C:\Windows\Fonts\ARIALUNI.TTF"), ()),
    (Path(r"C:\Windows\Fonts\arial.ttf"), ("arialbd.ttf",)),
]

# Set on first successful call; makes font probing/registration a one-time cost.
_cached_font_family: str | None = None


def _escape(text: str) -> str:
    """Escape a string for reportlab Paragraph markup."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _reportlab_bundled_fonts() -> list[tuple[Path, tuple[str, ...]]]:
    """DejaVuSans shipped with the reportlab installation, if present."""
    try:
        import reportlab

        fonts_dir = Path(reportlab.__file__).resolve().parent / "fonts"
    except Exception:
        return []
    bundled = fonts_dir / "DejaVuSans.ttf"
    if bundled.exists():
        return [(bundled, ("DejaVuSans-Bold.ttf",))]
    return []


def _font_candidates() -> list[tuple[Path, tuple[str, ...]]]:
    return [*_FONT_CANDIDATES, *_reportlab_bundled_fonts()]


def _font_has_currency_glyph(font: TTFont) -> bool:
    """True when reportlab can map U+20A1 to an actual glyph in this font."""
    glyph_id = font.face.charToGlyph.get(_CURRENCY_CODEPOINT)
    return bool(glyph_id) and glyph_id < font.face.numGlyphs


def _register_bold_variant(regular: Path, bold_names: tuple[str, ...]) -> str:
    """Register the bold face for the chosen family and return its font name.

    Uses the first bold candidate file that exists in the same directory;
    falls back to the regular file under the bold name otherwise (reportlab
    allows registering the same font under a different name).
    """
    for bold_name in bold_names:
        bold_path = regular.parent / bold_name
        if bold_path.exists():
            pdfmetrics.registerFont(TTFont(_MENU_FONT_BOLD, str(bold_path)))
            return _MENU_FONT_BOLD
    pdfmetrics.registerFont(TTFont(_MENU_FONT_BOLD, str(regular)))
    return _MENU_FONT_BOLD


def _register_currency_font() -> str:
    """Register a TrueType font that renders the colón sign; return its family.

    Searches the candidate fonts in order and registers the first one whose
    cmap (as parsed by reportlab) actually maps U+20A1 to a glyph. The regular
    face is registered as "MenuFont" and the bold variant as "MenuFont-Bold".
    Returns "Helvetica" with a warning when no usable font is found.
    """
    global _cached_font_family
    if _cached_font_family is not None:
        return _cached_font_family

    for regular, bold_names in _font_candidates():
        if not regular.exists():
            logger.debug("Font candidate missing, skipping: %s", regular)
            continue
        font = TTFont(_MENU_FONT_REGULAR, str(regular))
        if not _font_has_currency_glyph(font):
            logger.info(
                "Font candidate has no U+20A1 glyph, skipping: %s", regular
            )
            continue
        bold_face = _register_bold_variant(regular, bold_names)
        pdfmetrics.registerFont(font)
        pdfmetrics.registerFontFamily(
            _MENU_FONT_REGULAR,
            normal=_MENU_FONT_REGULAR,
            bold=bold_face,
            italic=_MENU_FONT_REGULAR,
            boldItalic=bold_face,
        )
        logger.info(
            "Registered %s (bold=%s) for the colón sign (U+20A1)", regular, bold_face
        )
        _cached_font_family = _MENU_FONT_REGULAR
        return _cached_font_family

    logger.warning(
        "No TrueType font with a U+20A1 glyph found; falling back to %s "
        "(the colón sign will render as a black box)",
        _FALLBACK_FAMILY,
    )
    _cached_font_family = _FALLBACK_FAMILY
    return _cached_font_family


def _build_pdf(menu: canonical.Menu, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"{menu.restaurant_name} — {DOC_TITLE}",
        author=menu.restaurant_name,
    )
    family = _register_currency_font()
    title_bold = _MENU_FONT_BOLD if family == _MENU_FONT_REGULAR else "Helvetica-Bold"
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "MenuTitle",
        parent=styles["Title"],
        fontSize=24,
        leading=28,
        textColor=HexColor("#1d1d1f"),
        spaceAfter=4,
        fontName=family,
        boldFontName=title_bold,
    )
    section_style = ParagraphStyle(
        "MenuSection",
        parent=styles["Heading2"],
        fontSize=15,
        leading=18,
        spaceBefore=16,
        spaceAfter=6,
        textColor=HexColor("#b8860b"),
        fontName=family,
    )
    item_style = ParagraphStyle(
        "MenuItem",
        parent=styles["BodyText"],
        fontSize=11,
        leading=14,
        leftIndent=10,
        spaceAfter=2,
        fontName=family,
    )
    desc_style = ParagraphStyle(
        "MenuDesc",
        parent=styles["BodyText"],
        fontSize=10,
        leading=13,
        leftIndent=10,
        spaceAfter=10,
        textColor=HexColor("#555555"),
        fontName=family,
    )

    story = [Paragraph(_escape(menu.restaurant_name), title_style)]
    story.append(Paragraph(DOC_TITLE, section_style))
    if menu.tagline:
        story.append(Paragraph(_escape(menu.tagline), desc_style))
        story.append(Spacer(1, 6))

    for section in menu.sections:
        if not section.items:
            continue
        story.append(Paragraph(_escape(section.name), section_style))
        for item in section.items:
            price = canonical.format_price(item.price)
            story.append(
                Paragraph(
                    f"{_escape(item.name)}&nbsp;&nbsp;&nbsp;&nbsp;{price}",
                    item_style,
                )
            )
            if item.description:
                story.append(Paragraph(_escape(item.description), desc_style))

    doc.build(story)


def _version_path(target: Path) -> Path:
    """Sidecar file recording the PDF version that produced `target`."""
    return target.with_suffix(target.suffix + ".version")


def menu_to_pdf(
    menu_path: str | Path = str(config.MENU_PATH),
    out_path: str | Path | None = None,
) -> Path:
    """Render the canonical menu to a PDF and return its path.

    Raises FileNotFoundError if the menu file does not exist. Reuses a cached
    PDF when the output is up to date with the source menu AND its version
    sidecar matches PDF_VERSION, so rendering changes force a regeneration.
    """
    source = Path(menu_path)
    if not source.exists():
        raise FileNotFoundError(f"Menu file not found: {source}")
    target = Path(out_path) if out_path is not None else DEFAULT_OUT_PATH

    version_file = _version_path(target)
    if (
        target.exists()
        and version_file.exists()
        and version_file.read_text(encoding="utf-8").strip() == str(PDF_VERSION)
        and target.stat().st_mtime >= source.stat().st_mtime
    ):
        logger.info("Reusing cached menu PDF at %s", target)
        return target

    menu = canonical.load_menu(source)
    _build_pdf(menu, target)
    version_file.write_text(str(PDF_VERSION), encoding="utf-8")
    logger.info("Menu PDF generated at %s", target)
    return target
