"""Telegram bot wiring: handlers for /start, callback buttons and free text.

Delegates all conversation logic to `app.bot.order_flow`.
"""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app import config
from app.bot import order_flow
from app.menu import canonical

logger = logging.getLogger(__name__)

_application: Application | None = None


def get_application() -> Application | None:
    return _application


def build_application() -> Application:
    """Build the PTB Application. Requires TELEGRAM_BOT_TOKEN."""
    global _application
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("ayuda", cmd_help))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(MessageHandler(filters.Document.ALL, on_document))
    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    application.add_error_handler(error_handler)

    _application = application
    return application


def _log_update(update: Update) -> None:
    """Log every incoming update: update_id, user, and payload (truncated)."""
    update_id = update.update_id
    user = update.effective_user
    user_id = user.id if user else None
    who = (user.username or user.first_name) if user is not None else None
    if update.callback_query is not None:
        logger.info(
            "Update %s (user=%s/%s): callback data=%r",
            update_id, user_id, who, update.callback_query.data,
        )
    elif update.message is not None and update.message.text:
        logger.info(
            "Update %s (user=%s/%s): text=%.200s",
            update_id, user_id, who, update.message.text.strip(),
        )
    else:
        logger.info("Update %s (user=%s/%s): received", update_id, user_id, who)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch unhandled handler errors so a bad message never dies silently."""
    logger.error(
        "Telegram handler error while processing update: %s",
        context.error,
        exc_info=context.error,
    )


def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("1) Ver menú", callback_data="menu")],
            [InlineKeyboardButton("2) Hacer un pedido", callback_data="order")],
            [InlineKeyboardButton("3) Preguntar por un plato", callback_data="question")],
        ]
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _log_update(update)
    user_id = update.effective_user.id
    order_flow.reset(user_id)
    await update.message.reply_text(
        "¡Hola! 👋 Soy el asistente de la cocina. Elegí una opción:"
        + order_flow.WELCOME_HINTS,
        reply_markup=_start_keyboard(),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show usage instructions without resetting an order in progress."""
    _log_update(update)
    text = (
        "🤖 ¡Acá va la guía rápida!\n\n"
        "📋 Ver el menú\n"
        "   Tocá el botón \"Ver menú\" o escribime \"mandame el menú\".\n\n"
        "🍽️ Hacer un pedido\n"
        "   Contame qué querés con palabras simples. Ejemplos:\n"
        "   • \"me regala un casado\"\n"
        "   • \"quiero un casado y un fresco\"\n"
        "   • \"2x gallo pinto\" o \"casado x 2\" para cantidades\n\n"
        "✏️ Modificar un pedido en curso\n"
        "   • \"agregame una coca\"\n"
        "   • \"sáqueme el gallo pinto\"\n"
        "   • \"cambie la milanesa por el asado\"\n\n"
        "❌ Cancelar\n"
        "   Escribí \"cancelar\" o tocá el botón Cancelar cuando te pregunten.\n\n"
        "Elegí una opción con el teclado de abajo 👇"
    )
    await update.message.reply_text(text, reply_markup=_start_keyboard())


async def _send_menu(update: Update) -> None:
    menu = canonical.load_or_empty(config.MENU_PATH)
    if not menu.items:
        await update.effective_chat.send_message(
            "El menú todavía está vacío 😅 Pedile al staff que lo cargue."
        )
        return
    for chunk in canonical.format_menu_text(menu):
        await update.effective_chat.send_message(chunk)
    await order_flow.send_menu_document_only(update)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _log_update(update)
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    data = query.data
    logger.info("Dispatch callback %r for user %s", data, user_id)

    if data == "menu":
        await _send_menu(update)
    elif data == "order":
        await order_flow.begin_order(user_id, chat_id, update, context)
    elif data == "question":
        await order_flow.begin_question(user_id, update)
    elif data == "delivery":
        await order_flow.choose_delivery(update, context, user_id, chat_id, "delivery")
    elif data == "pickup":
        await order_flow.choose_delivery(update, context, user_id, chat_id, "pickup")
    elif data == "confirm":
        await order_flow.confirm_order(update, context, user_id, chat_id)
    elif data == "cancel":
        order_flow.reset(user_id)
        await update.effective_chat.send_message("Sin problema, quedó cancelado 👌")
    elif data == "menu_replace_confirm":
        await order_flow.confirm_menu_replace(update, context, user_id)
    elif data == "menu_replace_cancel":
        await order_flow.cancel_menu_replace(update, user_id)
    else:
        await update.effective_chat.send_message("No entendí esa opción 🤔")


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle document uploads (PDF menu replacement) from any chat."""
    _log_update(update)
    if update.message is None or update.message.document is None:
        return
    await order_flow.handle_menu_pdf_document(update, context)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _log_update(update)
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()

    # Numbered quick options typed as plain text.
    if text in ("1", "2", "3"):
        logger.info("Dispatch numbered option %r for user %s", text, user_id)
        if text == "1":
            await _send_menu(update)
        elif text == "2":
            await order_flow.begin_order(user_id, chat_id, update, context)
        else:
            await order_flow.begin_question(user_id, update)
        return

    await order_flow.handle_text(update, context, user_id, chat_id, text)
