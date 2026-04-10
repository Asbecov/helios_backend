"""Legal command handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from helios_backend.bot.common import send_route_message
from helios_backend.settings import settings

router = Router(name="subscription-bot-legal")


@router.message(Command("terms"))
async def terms_command(message: Message) -> None:
    """Return terms text with external link."""
    if not settings.telegram_terms_url:
        await message.answer("Публичная оферта пока не настроена.")
        return

    await send_route_message(
        bot=message.bot,
        chat_id=message.chat.id,
        text=f"Публичная оферта: {settings.telegram_terms_url}",
        route="terms",
    )


@router.message(Command("privacy"))
async def privacy_command(message: Message) -> None:
    """Return privacy text with external link."""
    if not settings.telegram_privacy_url:
        await message.answer("Политика конфиденциальности пока не настроена.")
        return

    await send_route_message(
        bot=message.bot,
        chat_id=message.chat.id,
        text=f"Политика конфиденциальности: {settings.telegram_privacy_url}",
        route="privacy",
    )
