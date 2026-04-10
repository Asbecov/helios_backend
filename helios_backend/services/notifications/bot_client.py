"""Shared Telegram bot client for notification senders."""

import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from helios_backend.settings import settings

_shared_bot_lock = asyncio.Lock()


class _SharedBotState:
    """Mutable state holder for shared bot instance."""

    def __init__(self) -> None:
        self.bot: Bot | None = None


_state = _SharedBotState()


async def get_shared_bot() -> Bot | None:
    """Return one shared Bot instance for current process."""
    if not settings.telegram_bot_token:
        return None

    if _state.bot is not None:
        return _state.bot

    async with _shared_bot_lock:
        if _state.bot is None:
            _state.bot = Bot(
                token=settings.telegram_bot_token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
    return _state.bot


async def close_shared_bot() -> None:
    """Close shared Bot session if it was initialized."""
    if _state.bot is None:
        return

    await _state.bot.session.close()
    _state.bot = None
