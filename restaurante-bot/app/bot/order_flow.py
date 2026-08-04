"""Conversation state machine and order parsing for the Telegram bot.

Pure-ish logic separated from PTB handlers so it can be tested and reused.
Talking to customers is in Spanish (warm/colloquial); identifiers stay English.
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from datetime import datetime
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app import config
from app.kds import ws
from app.menu import canonical
from app.orders.models import DeliveryType, Order, OrderItem
from app.orders import store

logger = logging.getLogger(__name__)

ORDER_KEYWORDS = re.compile(
    r"\b(quiero|quiero pedir|querría|necesito|dame|traeme|pedir|pedido|pido|"
    r"para llevar|para la casa|delivery|retiro|pickup)\b",
    re.IGNORECASE,
)
QUANTITY_PATTERN = re.compile(
    r"\b(\d+|una|un|dos|tres|cuatro|cinco|media|un par)\b",
    re.IGNORECASE,
)
MENU_WORD_RE = re.compile(r"\b(men[uú]|carta)\b", re.IGNORECASE)
MENU_PDF_TRIGGERS = (
    "pdf", "mandame", "mándame", "mandáme", "enviame", "envíame",
    "dame", "pasame", "pásame", "pasámelo", "quiero ver", "ver el",
    "quiero el", "necesito el", "manda el", "envia el", "enviar", "mandar",
)
UPLOAD_MENU_RE = re.compile(
    r"\b(sub[oó] el men[uú]|subo men[uú]|actualiz[aá] el men[uú]|"
    r"actualizar el men[uú]|cambi[aá] el men[uú]|cambiar men[uú]|"
    r"reemplaz[aá] el men[uú]|carg[aá] el men[uú])\b",
    re.IGNORECASE,
)
GREETING_RE = re.compile(
    r"\b(buenos d[ií]as|buen d[ií]a|buenas tardes|buenas noches|buenas|hola|holi|buenass?)\b",
    re.IGNORECASE,
)
MODIFY_KEYWORDS = re.compile(
    r"\b(agreg[aá]|agregame|agr[eé]gale|sac[aá]|s[aá]came|quita|quit[aá]|"
    r"quitame|elimina|elimin[aá]|borra|borr[aá]|cambi[aá]|cambio|cambiar|"
    r"modific[aá]|sin la|sin el|sin)\b",
    re.IGNORECASE,
)
NAME_SKIP = {
    "omitir", "saltar", "skip", "ninguno", "ninguna", "no",
    "no gracias", "n", "n/a", "na", "-", "cliente",
}
MAX_NAME_LEN = 60


# --------------------------------------------------------------------------
# LLM schemas for order parsing / intent classification
# --------------------------------------------------------------------------
class ParsedOrderItem(BaseModel):
    canonical_name: str = Field(description="Exact item name as it appears in the menu")
    quantity: int = Field(default=1, description="How many of this item")
    unit_price: float = Field(default=0.0, description="Unit price from the menu")


class ParsedOrder(BaseModel):
    items: list[ParsedOrderItem] = Field(default_factory=list)
    unmatched: list[str] = Field(default_factory=list, description="Text that could not be matched to a menu item")


class OrderModification(BaseModel):
    items_to_add: list[ParsedOrderItem] = Field(
        default_factory=list,
        description="Items to add, using exact canonical names from the menu",
    )
    items_to_remove: list[str] = Field(
        default_factory=list,
        description="Canonical names of items to remove from the current order",
    )


class IntentResult(BaseModel):
    intent: Literal["order", "menu_question", "other"]


ORDER_PARSE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Sos un extractor de pedidos de restaurante. Te dan el menú canónico y "
            "el texto informal de un cliente. Devolvé el pedido usando SOLO los "
            "nombres canónicos exactos del menú, con su cantidad. Si parte del texto "
            "no coincide con ningún plato, ponelo en `unmatched`. No inventes platos.",
        ),
        (
            "human",
            "Menú canónico:\n{menu_text}\n\nTexto del cliente: {text}",
        ),
    ]
)

INTENT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Clasificá la intención del mensaje de un cliente de restaurante. "
            "`order` = quiere pedir comida o bebida. `menu_question` = pregunta "
            "sobre el menú o el restaurante. `other` = cualquier otra cosa. "
            "Respondé solo con la intención.",
        ),
        ("human", "Mensaje: {text}"),
    ]
)

MODIFY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Sos un modificador de pedidos de restaurante. El cliente quiere "
            "CAMBIAR un pedido existente. Recibís el menú canónico y el pedido "
            "actual. Devolvé qué ítems AGREGAR (nombres canónicos exactos) y "
            "qué ítems QUITAR (nombres canónicos exactos). 'cambia X por Y' => "
            "remove X, add Y. No inventes platos.",
        ),
        (
            "human",
            "Menú:\n{menu_text}\n\nPedido actual:\n{current_text}\n\nMensaje del cliente: {text}",
        ),
    ]
)


# --------------------------------------------------------------------------
# Conversation state
# --------------------------------------------------------------------------
class FlowState(BaseModel):
    step: str = "idle"  # idle | awaiting_order | awaiting_name | awaiting_delivery | awaiting_phone | awaiting_address | awaiting_confirm | awaiting_question
    chat_id: int = 0
    parsed: ParsedOrder | None = None
    delivery_type: DeliveryType | None = None
    customer_name: str = ""
    delivery_phone: str = ""
    delivery_address: str = ""


# user_id -> FlowState (in-memory; fine for a POC)
_flows: dict[int, FlowState] = {}

# order.id -> chat_id, so the bot can notify customers of status changes
_order_owners: dict[int, int] = {}

# user_id -> canonical markdown of the PDF menu awaiting replace confirmation
_pending_menu_replace: dict[int, str] = {}


def reset(user_id: int) -> None:
    _flows.pop(user_id, None)


def _get(user_id: int) -> FlowState:
    flow = _flows.get(user_id)
    if flow is None:
        flow = FlowState(chat_id=0)
        _flows[user_id] = flow
    return flow


def register_order_owner(order: Order, chat_id: int) -> None:
    if order.id is not None:
        _order_owners[order.id] = chat_id


# --------------------------------------------------------------------------
# Intent classification
# --------------------------------------------------------------------------
def _looks_like_order(text: str) -> bool:
    if ORDER_KEYWORDS.search(text):
        return True
    if QUANTITY_PATTERN.search(text):
        return True
    return False


def classify_intent(text: str) -> str:
    """Return 'order', 'menu_question' or 'other'.

    Uses GPT-4o-mini when a key is present, otherwise a regex heuristic.
    """
    if config.has_openai_key():
        try:
            llm = ChatOpenAI(model=config.OPENAI_MODEL, temperature=0)
            result = (INTENT_PROMPT | llm.with_structured_output(IntentResult)).invoke(
                {"text": text}
            )
            intent = result.intent
            logger.info("LLM intent for %.100s -> %s", text, intent)
            return intent
        except Exception:
            logger.exception("LLM intent classification failed, using heuristics")
    intent = "order" if _looks_like_order(text) else "menu_question"
    logger.info("Heuristic intent for %.100s -> %s", text, intent)
    return intent


# --------------------------------------------------------------------------
# Order parsing
# --------------------------------------------------------------------------
def parse_order(text: str, menu: canonical.Menu) -> ParsedOrder:
    """Extract ordered items from colloquial Spanish using GPT-4o-mini."""
    config.require_openai_key()
    logger.info("Parsing order text (truncated): %.200s", text)
    llm = ChatOpenAI(model=config.OPENAI_MODEL, temperature=0)
    parsed = (ORDER_PARSE_PROMPT | llm.with_structured_output(ParsedOrder)).invoke(
        {"menu_text": canonical.menu_context_text(menu), "text": text}
    )
    known = {item.name.lower(): item for item in menu.items}
    validated = [
        item for item in parsed.items if item.canonical_name.lower() in known
    ]
    if not validated and parsed.items:
        # The model invented names: fall back to fuzzy suggestions.
        for item in parsed.items:
            parsed.unmatched.append(item.canonical_name)
        parsed.items = []
    logger.info(
        "Parsed order: %d matched item(s) [%s]; %d unmatched [%s]",
        len(validated),
        ", ".join(f"{i.quantity}x{i.canonical_name}" for i in validated),
        len(parsed.unmatched),
        ", ".join(parsed.unmatched),
    )
    return parsed


# --------------------------------------------------------------------------
# Customer-facing flows (Spanish)
# --------------------------------------------------------------------------
async def _reply(update: Update, text: str) -> None:
    if update.callback_query is not None:
        await update.effective_chat.send_message(text)
    else:
        await update.message.reply_text(text)


def normalize_customer_name(text: str) -> str:
    """Sanitize the customer name, defaulting to 'Cliente' when skipped/empty."""
    cleaned = (text or "").strip()
    if not cleaned or cleaned.lower() in NAME_SKIP:
        return "Cliente"
    return cleaned[:MAX_NAME_LEN]


def wants_upload_menu(text: str) -> bool:
    """True when the customer is offering to replace the menu with a PDF."""
    return bool(UPLOAD_MENU_RE.search(text or ""))


def _delivery_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🛵 Delivery", callback_data="delivery")],
            [InlineKeyboardButton("🏪 Pickup (retiro en local)", callback_data="pickup")],
        ]
    )


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Sí, confirmar", callback_data="confirm")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
        ]
    )


def greeting_reply(text: str) -> str | None:
    """Time-appropriate greeting when `text` contains a greeting, else None."""
    if not GREETING_RE.search(text or ""):
        return None
    hour = datetime.now().hour
    if hour < 12:
        greeting = "¡Buenos días!"
    elif hour < 20:
        greeting = "¡Buenas tardes!"
    else:
        greeting = "¡Buenas noches!"
    return f"{greeting} ¿En qué te ayudo? Podés pedir comida o preguntar por el menú 😊"


def normalize_phone(text: str) -> str | None:
    """Normalize a phone number, returning None when it has no digits at all."""
    if not re.search(r"\d", text or ""):
        return None
    return re.sub(r"\s+", " ", text).strip()[:40]


def _build_order_summary(flow: FlowState) -> tuple[list[str], float]:
    """Render the pending order summary lines and its total."""
    menu = canonical.load_or_empty(config.MENU_PATH)
    parsed = flow.parsed or ParsedOrder()
    lines = ["🧾 Resumen de tu pedido:\n"]
    total = 0.0
    for item in parsed.items:
        known = menu.find_item(item.canonical_name)
        unit_price = known.price if known else item.unit_price
        subtotal = round(unit_price * item.quantity, 2)
        total += subtotal
        lines.append(f"• {item.quantity} × {item.canonical_name} — {canonical.format_price(subtotal)}")
    lines.append("")
    lines.append(f"TOTAL: {canonical.format_price(total)}")
    if flow.delivery_type is not None:
        lines.append(f"Entrega: {flow.delivery_type.label}")
    lines.append(f"A nombre de: {flow.customer_name or 'Cliente'}")
    if flow.delivery_type == DeliveryType.delivery:
        if flow.delivery_phone:
            lines.append(f"📞 Teléfono: {flow.delivery_phone}")
        if flow.delivery_address:
            lines.append(f"📍 Dirección: {flow.delivery_address}")
    return lines, total


def _wants_menu_pdf(text: str) -> bool:
    """True when the customer is explicitly asking for the menu as a document."""
    lowered = text.lower()
    if not MENU_WORD_RE.search(lowered):
        return False
    return any(trigger in lowered for trigger in MENU_PDF_TRIGGERS)


async def send_menu_document_only(update: Update) -> bool:
    """Generate and send the menu PDF as a document. Returns True on success."""
    from app.menu import pdf_export

    try:
        pdf_path = pdf_export.menu_to_pdf(config.MENU_PATH)
    except Exception:
        logger.exception("Menu PDF generation failed")
        return False
    try:
        with open(pdf_path, "rb") as handle:
            await update.effective_chat.send_document(
                document=handle, filename="menu.pdf", caption="📄 Menú"
            )
        logger.info("Menu PDF sent to chat %s", update.effective_chat.id)
        return True
    except Exception:
        logger.exception("Failed to send menu PDF document")
        return False


async def send_menu_pdf(update: Update, user_id: int) -> None:
    """Reply to an explicit 'send me the menu' request with sections + PDF."""
    menu = canonical.load_or_empty(config.MENU_PATH)
    if menu.items:
        sections = " • ".join(section.name for section in menu.sections if section.items)
        await _reply(update, f"📋 {menu.restaurant_name} — Secciones:\n{sections}")
    sent = await send_menu_document_only(update)
    if not sent:
        logger.warning(
            "Menu PDF not sent to user %s; falling back to plain text", user_id
        )
        if menu.items:
            for chunk in canonical.format_menu_text(menu):
                await update.effective_chat.send_message(chunk)
        else:
            await _reply(update, "El menú todavía está vacío 😅 Pedile al staff que lo cargue.")


async def begin_order(user_id: int, chat_id: int, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    flow = _get(user_id)
    flow.step = "awaiting_order"
    flow.chat_id = chat_id
    logger.info("Order flow session started for user %s", user_id)
    await _reply(update, "¡Dale! Contame qué querés pedir 🍽️\nEj.: \"dos milanesas napolitanas y una coca cola\"")


async def begin_question(user_id: int, update: Update) -> None:
    flow = _get(user_id)
    flow.step = "awaiting_question"
    logger.info("Question flow session started for user %s", user_id)
    await _reply(update, "Preguntame lo que quieras sobre nuestro menú 😊")


async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
    text: str,
) -> None:
    flow = _get(user_id)

    if flow.step == "idle" and GREETING_RE.search(text):
        greeting = greeting_reply(text)
        if greeting:
            logger.info("Greeting detected from user %s", user_id)
            await _reply(update, greeting)

    if flow.step in ("idle", "awaiting_question") and _wants_menu_pdf(text):
        logger.info("Explicit menu-PDF request from user %s", user_id)
        reset(user_id)
        await send_menu_pdf(update, user_id)
        return

    if flow.step in ("idle", "awaiting_question") and wants_upload_menu(text):
        logger.info("Menu upload intent from user %s", user_id)
        reset(user_id)
        await _reply(update, "¡Dale! Adjuntame el archivo PDF con el menú y lo reemplazo 📄")
        return

    if flow.step in ("awaiting_name", "awaiting_delivery", "awaiting_confirm") and MODIFY_KEYWORDS.search(text):
        logger.info("Order modification intent from user %s", user_id)
        await modify_order(update, context, user_id, chat_id, text)
        return

    if flow.step == "awaiting_phone":
        phone = normalize_phone(text)
        if phone is None:
            await _reply(update, "No pude leer el número 😅 ¿Me pasás un teléfono de contacto?")
            return
        flow.delivery_phone = phone
        flow.step = "awaiting_address"
        logger.info("Delivery phone set for user %s", user_id)
        await _reply(update, "📍 ¿Y la dirección de entrega?")
        return

    if flow.step == "awaiting_address":
        flow.delivery_address = text.strip()
        flow.step = "awaiting_confirm"
        logger.info("Delivery address set for user %s", user_id)
        lines, _ = _build_order_summary(flow)
        await _reply(update, "\n".join(lines))
        await update.effective_chat.send_message(
            "¿Confirmás el pedido?", reply_markup=_confirm_keyboard()
        )
        return

    if flow.step == "awaiting_name":
        flow.customer_name = normalize_customer_name(text)
        flow.step = "awaiting_delivery"
        logger.info("Customer name set for user %s: %r", user_id, flow.customer_name)
        await update.effective_chat.send_message(
            "¿Cómo lo querés recibir?", reply_markup=_delivery_keyboard()
        )
        return

    if flow.step == "awaiting_delivery":
        lowered = text.lower()
        if any(k in lowered for k in ("delivery", "envío", "envio", "domicilio", "moto", "reparto")):
            await choose_delivery(update, context, user_id, chat_id, "delivery")
        elif any(k in lowered for k in ("pickup", "retiro", "local", "llevar", "take away", "takeaway", "pasar")):
            await choose_delivery(update, context, user_id, chat_id, "pickup")
        else:
            await _reply(update, "¿Cómo lo querés? Elegí Delivery o Pickup 👇")
        return

    if flow.step == "awaiting_confirm":
        lowered = text.lower().strip()
        if lowered in ("sí", "si", "confirmar", "confirmo", "dale", "ok", "s"):
            logger.info("Order confirmation ACCEPTED by user %s", user_id)
            await confirm_order(update, context, user_id, chat_id)
        elif lowered in ("no", "cancelar", "cancela", "n"):
            logger.info("Order confirmation REJECTED by user %s", user_id)
            reset(user_id)
            await _reply(update, "Quedó cancelado 👌 ¿Necesitás algo más?")
        else:
            await _reply(update, "¿Confirmás el pedido? Respondé Sí o Cancelar.")
        return

    if flow.step == "awaiting_question":
        await answer_question(update, user_id, text)
        reset(user_id)
        return

    if flow.step == "awaiting_order":
        await parse_and_continue(update, context, user_id, chat_id, text)
        return

    # Idle: free text routing.
    intent = classify_intent(text)
    if intent == "order":
        await parse_and_continue(update, context, user_id, chat_id, text)
    else:
        await answer_question(update, user_id, text)


async def parse_and_continue(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
    text: str,
) -> None:
    menu = canonical.load_or_empty(config.MENU_PATH)
    if not menu.items:
        await _reply(update, "El menú todavía está vacío 😅 Pedile al staff que lo cargue.")
        reset(user_id)
        return

    try:
        parsed = parse_order(text, menu)
    except RuntimeError as exc:
        await _reply(update, "Todavía no puedo tomar pedidos: falta configurar OPENAI_API_KEY. 😅")
        logger.warning("Order parse skipped: %s", exc)
        reset(user_id)
        return
    except Exception as exc:
        logger.exception("Order parsing failed for user %s", user_id)
        await _reply(update, "No pude interpretar tu pedido 😅 ¿Podés escribirlo de nuevo, más simple?")
        reset(user_id)
        return

    if not parsed.items and parsed.unmatched:
        logger.info(
            "No matching items for user %s; unmatched: %s",
            user_id, ", ".join(parsed.unmatched),
        )
        await _reply(update, f"No encontré \"{', '.join(parsed.unmatched)}\" en el menú 😅")
        suggestions = canonical.suggest_items(menu, " ".join(parsed.unmatched), k=3)
        if suggestions:
            await _reply(
                update,
                "Quizás quisiste decir:\n" + "\n".join(f"• {name}" for name in suggestions),
            )
        await _reply(update, "Escribime tu pedido de nuevo, o usá /start para ver el menú.")
        return
    if not parsed.items:
        logger.info("Could not understand order text from user %s", user_id)
        await _reply(update, "No pude entender el pedido 😅 Probá con algo como \"una milanesa napolitana\".")
        return

    flow = _get(user_id)
    flow.parsed = parsed
    flow.customer_name = ""
    flow.step = "awaiting_name"
    logger.info("Parsed items for user %s; awaiting customer name", user_id)

    if parsed.unmatched:
        await _reply(update, f"Ojo: no encontré \"{', '.join(parsed.unmatched)}\", lo dejo afuera. El resto: 👇")

    await _reply(
        update,
        "¿A nombre de quién hago el pedido? "
        "Podés escribir tu nombre o decir \"omitir\" para usar \"Cliente\".",
    )


async def choose_delivery(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
    delivery_type: str,
) -> None:
    flow = _get(user_id)
    flow.delivery_type = DeliveryType(delivery_type)
    logger.info(
        "Delivery type chosen for user %s: %s", user_id, delivery_type
    )

    if flow.delivery_type == DeliveryType.delivery:
        flow.step = "awaiting_phone"
        await _reply(update, "📞 Para el delivery, ¿me pasás un teléfono de contacto?")
        return

    flow.step = "awaiting_confirm"
    lines, _ = _build_order_summary(flow)
    await _reply(update, "\n".join(lines))
    await update.effective_chat.send_message(
        "¿Confirmás el pedido?", reply_markup=_confirm_keyboard()
    )


def parse_modification(
    text: str, menu: canonical.Menu, current_parsed: ParsedOrder
) -> OrderModification:
    """Extract add/remove changes from colloquial Spanish using GPT-4o-mini."""
    config.require_openai_key()
    logger.info("Parsing order modification text (truncated): %.200s", text)
    llm = ChatOpenAI(model=config.OPENAI_MODEL, temperature=0)
    current_text = "\n".join(
        f"{item.quantity} × {item.canonical_name}" for item in current_parsed.items
    )
    mod = (MODIFY_PROMPT | llm.with_structured_output(OrderModification)).invoke(
        {
            "menu_text": canonical.menu_context_text(menu),
            "current_text": current_text,
            "text": text,
        }
    )
    known = {item.name.lower(): item for item in menu.items}
    validated_adds: list[ParsedOrderItem] = []
    for item in mod.items_to_add:
        match = known.get(item.canonical_name.lower())
        if match is None:
            logger.warning(
                "Modification add dropped (not in menu): %r", item.canonical_name
            )
            continue
        item.unit_price = match.price
        validated_adds.append(item)
    mod.items_to_add = validated_adds
    logger.info(
        "Parsed modification: %d add(s), %d remove(s)",
        len(mod.items_to_add), len(mod.items_to_remove),
    )
    return mod


def apply_modification(flow: FlowState, mod: OrderModification) -> list[str]:
    """Mutate `flow.parsed.items` and return human-readable applied changes."""
    if flow.parsed is None:
        return []
    changes: list[str] = []
    if mod.items_to_remove:
        remove_lower = {name.lower() for name in mod.items_to_remove}
        kept: list[ParsedOrderItem] = []
        removed_names: list[str] = []
        for item in flow.parsed.items:
            if item.canonical_name.lower() in remove_lower:
                removed_names.append(item.canonical_name)
            else:
                kept.append(item)
        flow.parsed.items = kept
        for name in dict.fromkeys(removed_names):
            changes.append(f"Quitado {name}")
    for add in mod.items_to_add:
        flow.parsed.items.append(add)
        changes.append(f"Agregado {add.quantity} × {add.canonical_name}")
    return changes


async def modify_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
    text: str,
) -> None:
    """Apply a colloquial order modification and re-show the pending summary."""
    flow = _get(user_id)
    if flow.parsed is None:
        await _reply(update, "Todavía no hay un pedido para modificar 😊")
        return

    menu = canonical.load_or_empty(config.MENU_PATH)
    try:
        mod = parse_modification(text, menu, flow.parsed)
    except RuntimeError as exc:
        await _reply(update, "Todavía no puedo modificar pedidos: falta configurar OPENAI_API_KEY 😅")
        logger.warning("Modification parse skipped: %s", exc)
        return
    except Exception:
        logger.exception("Modification parsing failed for user %s", user_id)
        await _reply(update, "No pude modificar el pedido 😅 ¿Podés decirlo de otra forma?")
        return

    changes = apply_modification(flow, mod)
    if not changes:
        await _reply(update, "No encontré qué modificar en tu pedido 😅")
        return

    logger.info(
        "Order modified for user %s: %s",
        user_id, ", ".join(changes),
    )
    summary_lines = ["Listo 👇"]
    summary_lines.extend(f"• {change}" for change in changes)
    await _reply(update, "\n".join(summary_lines))

    if not flow.parsed.items:
        await _reply(update, "Tu pedido quedó vacío 😅 Escribime qué querés pedir de nuevo.")
        flow.parsed = None
        flow.step = "awaiting_order"
        return

    lines, _ = _build_order_summary(flow)
    await _reply(update, "\n".join(lines))
    if flow.delivery_type is not None:
        await update.effective_chat.send_message(
            "¿Confirmás el pedido?", reply_markup=_confirm_keyboard()
        )
        flow.step = "awaiting_confirm"
    else:
        await update.effective_chat.send_message(
            "¿Cómo lo querés recibir?", reply_markup=_delivery_keyboard()
        )
        flow.step = "awaiting_delivery"


async def confirm_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
) -> None:
    flow = _get(user_id)
    if flow.parsed is None or flow.delivery_type is None:
        await _reply(update, "No hay un pedido en curso. Escribime qué querés 😊")
        reset(user_id)
        return

    menu = canonical.load_or_empty(config.MENU_PATH)
    items: list[OrderItem] = []
    for parsed_item in flow.parsed.items:
        known = menu.find_item(parsed_item.canonical_name)
        unit_price = known.price if known else parsed_item.unit_price
        items.append(
            OrderItem(name=parsed_item.canonical_name, quantity=parsed_item.quantity, unit_price=unit_price)
        )

    order = store.create_order(
        items,
        flow.delivery_type,
        customer_name=flow.customer_name or "Cliente",
        delivery_phone=flow.delivery_phone,
        delivery_address=flow.delivery_address,
    )
    register_order_owner(order, chat_id)
    reset(user_id)
    logger.info(
        "Order created for user %s: id=%s number=%s total=%.2f",
        user_id, order.id, order.number, order.total,
    )

    await ws.manager.broadcast_order(order, "order.created")

    delivery_label = "Delivery" if order.delivery_type == DeliveryType.delivery else "Pickup"
    lines = [
        f"🎉 ¡Pedido confirmado!\n\n",
        f"🧾 ORDEN N° {order.number}\n",
    ]
    for item in order.items:
        lines.append(f"• {item.quantity} × {item.name} — {canonical.format_price(item.total)}")
    lines.append("")
    lines.append(f"TOTAL: {canonical.format_price(order.total)}")
    lines.append(f"Entrega: {delivery_label}")
    lines.append(f"A nombre de: {order.customer_name or 'Cliente'}")
    if order.delivery_type == DeliveryType.delivery:
        if order.delivery_phone:
            lines.append(f"📞 {order.delivery_phone}")
        if order.delivery_address:
            lines.append(f"📍 {order.delivery_address}")
    lines.append("\nEstado: ⏳ Pendiente. Te avisamos cuando esté en preparación.")
    await _reply(update, "\n".join(lines))


async def answer_question(update: Update, user_id: int, text: str) -> None:
    from app.rag import retriever

    try:
        answer = retriever.answer_question(text)
    except RuntimeError as exc:
        await _reply(update, "Todavía no puedo responder preguntas: falta configurar OPENAI_API_KEY 😅")
        logger.warning("RAG answer skipped: %s", exc)
        return
    except Exception as exc:
        logger.exception("RAG answer failed")
        await _reply(update, "Uy, tuve un problema para responder 😅 Probá de nuevo en un rato.")
        return
    await _reply(update, answer)


# --------------------------------------------------------------------------
# Status notifications to the customer (nice-to-have)
# --------------------------------------------------------------------------
async def notify_order_status(order: Order) -> None:
    chat_id = _order_owners.get(order.id) if order.id is not None else None
    if chat_id is None:
        logger.debug(
            "No owner registered for order %s; skip customer notification",
            order.id,
        )
        return
    from app.bot import telegram_bot

    application = telegram_bot.get_application()
    if application is None:
        logger.debug(
            "Telegram application not available; skip notification for order %s",
            order.id,
        )
        return
    text = (
        f"🔔 Actualización de tu pedido N° {order.number} "
        f"(a nombre de {order.customer_name or 'Cliente'})\n"
        f"Estado: {order.status.label}"
    )
    if order.status.value == "completed":
        text += "\n¡Que lo disfrutes! 😋"
    try:
        await application.bot.send_message(chat_id=chat_id, text=text)
        logger.info(
            "Customer notified for order %s -> status %s (chat %s)",
            order.id, order.status.value, chat_id,
        )
    except Exception as exc:
        logger.warning(
            "Could not notify customer for order %s (chat %s): %s",
            order.id, chat_id, exc,
        )


# --------------------------------------------------------------------------
# PDF menu replacement (upload a PDF that replaces the whole menu)
# --------------------------------------------------------------------------
def _is_pdf_document(document) -> bool:
    """True when the document looks like a PDF (by name or mime type)."""
    file_name = (getattr(document, "file_name", "") or "").lower()
    mime_type = getattr(document, "mime_type", "") or ""
    return file_name.endswith(".pdf") or mime_type == "application/pdf"


async def handle_menu_pdf_document(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Process an uploaded PDF: download, extract, summarize, and offer a replace."""
    from app.menu import pdf_loader

    message = update.message
    if message is None or message.document is None:
        return
    user_id = update.effective_user.id
    document = message.document
    if not _is_pdf_document(document):
        await _reply(update, "Solo acepto el menú en PDF 📄. Adjuntá un archivo .pdf y lo proceso.")
        return

    logger.info(
        "Menu PDF upload started from user %s (file=%r)",
        user_id, document.file_name,
    )
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".pdf", prefix="menu_upload_")
        os.close(fd)
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(custom_path=tmp_path)

        markdown, used_llm = pdf_loader.pdf_to_canonical(tmp_path)
        parsed = canonical.parse_menu(markdown)
        sections = len([s for s in parsed.sections if s.items])
        items = len(parsed.items)
        logger.info(
            "Menu PDF parsed for user %s: %d section(s), %d item(s), used_llm=%s",
            user_id, sections, items, used_llm,
        )
        if items == 0:
            hint = (
                "No pude identificar ítems en el PDF 😅 "
                "Configurá OPENAI_API_KEY para estructurar el menú automáticamente "
                "o revisalo con `python scripts/ingest_pdf.py <archivo>`."
            )
            await _reply(update, hint)
            return

        _pending_menu_replace[user_id] = markdown
        examples = "; ".join(
            f"{item.name} — {canonical.format_price(item.price)}"
            for item in parsed.items[:3]
        )
        summary = (
            f"Encontré {sections} secciones y {items} ítems (ej. {examples}).\n"
            "¿Reemplazo todo el menú actual?"
        )
        if not used_llm:
            summary += (
                "\n\n⚠️ Sin OPENAI_API_KEY el texto se extrajo sin limpiar: "
                "el menú puede necesitar revisión manual."
            )
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Sí, reemplazar", callback_data="menu_replace_confirm")],
                [InlineKeyboardButton("❌ Cancelar", callback_data="menu_replace_cancel")],
            ]
        )
        await _reply(update, summary)
        await update.effective_chat.send_message(
            "¿Reemplazo el menú completo?", reply_markup=keyboard
        )
        logger.info("Menu PDF upload finished for user %s", user_id)
    except Exception:
        logger.exception("Menu PDF upload processing failed for user %s", user_id)
        await _reply(update, "No pude procesar ese PDF 😅 Probá con otro archivo.")
    finally:
        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except OSError:
                logger.debug("Could not remove temp file %s", tmp_path)


async def confirm_menu_replace(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int
) -> None:
    """Persist the pending menu (REPLACE, not merge) and try to rebuild RAG."""
    markdown = _pending_menu_replace.pop(user_id, None)
    if markdown is None:
        await _reply(update, "No hay ningún menú pendiente por reemplazar 😊")
        return

    menu = canonical.parse_menu(markdown)
    canonical.assign_item_ids(menu)
    canonical.save_menu(menu, config.MENU_PATH)
    logger.info(
        "Menu REPLACED by user %s: %d section(s), %d item(s)",
        user_id, len(menu.sections), len(menu.items),
    )

    try:
        from app.rag import indexer

        docs = indexer.build_index(refresh=True)
        logger.info(
            "RAG index rebuilt after menu replacement: %d document(s)", docs
        )
        await _reply(update, "¡Menú actualizado! Reconstruí el índice RAG ✅")
    except Exception:
        logger.exception("RAG index rebuild failed after menu replacement")
        await _reply(
            update,
            "¡Menú actualizado! Para actualizar el índice RAG, "
            "corré `python scripts/rebuild_index.py`.",
        )


async def cancel_menu_replace(update: Update, user_id: int) -> None:
    """Discard the pending menu replacement without touching the current menu."""
    _pending_menu_replace.pop(user_id, None)
    logger.info("Menu replacement cancelled by user %s", user_id)
    await _reply(update, "Ok, no cambié nada 👌")
