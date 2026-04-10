"""Aiogram polling application bootstrap."""

import asyncio

from aiogram import Dispatcher
from tortoise import Tortoise

from helios_backend.bot.router import router
from helios_backend.db.config import TORTOISE_CONFIG
from helios_backend.log import configure_logging
from helios_backend.services.notifications.bot_client import (
    close_shared_bot,
    get_shared_bot,
)
from helios_backend.settings import settings


async def run_bot() -> None:
    """Run Telegram bot polling loop with initialized database."""
    if not settings.telegram_bot_token:
        msg = "HELIOS_BACKEND_TELEGRAM_BOT_TOKEN is not configured"
        raise RuntimeError(msg)

    configure_logging()
    await Tortoise.init(config=TORTOISE_CONFIG)

    bot = await get_shared_bot()
    if bot is None:
        msg = "HELIOS_BACKEND_TELEGRAM_BOT_TOKEN is not configured"
        raise RuntimeError(msg)

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    try:
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await close_shared_bot()
        await Tortoise.close_connections()


def run() -> None:
    """Run bot entrypoint in synchronous context."""
    asyncio.run(run_bot())
