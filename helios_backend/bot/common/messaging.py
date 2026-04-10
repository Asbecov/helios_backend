"""Messaging helpers shared across bot routes."""

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, ReplyKeyboardMarkup

from helios_backend.settings import settings

ReplyMarkupType = InlineKeyboardMarkup | ReplyKeyboardMarkup


def route_image_url(route: str) -> str:
    """Resolve optional route image URL from settings."""
    mapping = {
        "help": settings.telegram_help_image_url,
        "my": settings.telegram_my_image_url,
        "buy": settings.telegram_buy_image_url,
        "connect": settings.telegram_connect_image_url,
        "support": settings.telegram_support_image_url,
        "terms": settings.telegram_terms_image_url,
        "privacy": settings.telegram_privacy_image_url,
    }
    return mapping.get(route, "").strip()


async def send_route_message(
    bot: Bot | None,
    chat_id: int,
    text: str,
    route: str,
    reply_markup: ReplyMarkupType | None = None,
) -> None:
    """Send message with optional route image if configured."""
    if bot is None:
        return

    image_url = route_image_url(route)
    if image_url and len(text) <= 1024:
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=image_url,
                caption=text,
                reply_markup=reply_markup,
            )
            return
        except TelegramAPIError:
            # Fall back to text when image URL is invalid/unavailable.
            pass

    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
    )


async def delete_callback_message(callback: CallbackQuery) -> None:
    """Delete callback source message when possible."""
    if callback.message is None or not hasattr(callback.message, "delete"):
        return

    try:
        await callback.message.delete()
    except TelegramAPIError:
        # Old or already deleted messages are safe to ignore.
        return
