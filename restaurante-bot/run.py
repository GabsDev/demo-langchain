"""Entry point: starts the FastAPI server (KDS dashboard) AND the Telegram bot
(polling) together in one process.

Run:
    python run.py

Both components share one asyncio event loop. If TELEGRAM_BOT_TOKEN is missing
the server still boots (only the bot is skipped). If OPENAI_API_KEY is missing
the RAG/LLM paths fail gracefully at call time.
"""
from __future__ import annotations

import asyncio
import logging

import uvicorn

from app import config

config.setup_logging()
logger = logging.getLogger("run")


async def run_server() -> None:
    from app.server import app

    server = uvicorn.Server(
        uvicorn.Config(app, host=config.HOST, port=config.PORT, log_level="info")
    )
    await server.serve()


async def start_bot():
    logger.info("Telegram bot start attempt")
    from telegram import Update

    from app.bot.telegram_bot import build_application
    from app.server import app

    application = build_application()
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    app.state.order_update_callback = order_update_handler
    logger.info("Telegram bot started and polling")
    return application


def order_update_handler(order) -> None:
    """Spawn a task (server loop is running) to notify the customer on Telegram."""
    from app.bot import order_flow

    asyncio.create_task(order_flow.notify_order_status(order))


async def main() -> None:
    logger.info("Starting KDS server on http://%s:%s", config.HOST, config.PORT)
    server_task = asyncio.create_task(run_server())
    logger.info("KDS server task started")

    bot_application = None
    if config.has_telegram_token():
        try:
            bot_application = await start_bot()
        except Exception:
            logger.exception("Telegram bot failed to start; continuing with server only")
    else:
        logger.warning(
            "TELEGRAM_BOT_TOKEN not set: Telegram bot will NOT start. "
            "Only the KDS server is running. Add the token to .env to enable it."
        )

    try:
        await asyncio.Event().wait()
    finally:
        logger.info("Shutting down: stopping bot and server")
        if bot_application is not None:
            await bot_application.updater.stop()
            await bot_application.stop()
            await bot_application.shutdown()
        server_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down")
