"""User resolution helpers for bot handlers."""

from aiogram.types import CallbackQuery, Message

from helios_backend.bot.services import get_user_service
from helios_backend.db.models.vpn.user import User


async def resolve_user(message: Message) -> User | None:
    """Resolve internal user from Telegram sender."""
    if message.from_user is None:
        await message.answer("❌ Не удалось определить пользователя Telegram.")
        return None

    user_service = get_user_service()
    return await user_service.get_or_create_telegram_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )


async def resolve_user_from_callback(callback: CallbackQuery) -> User | None:
    """Resolve internal user from callback sender."""
    if callback.from_user is None:
        await callback.answer("❌ Пользователь не определен.", show_alert=True)
        return None

    user_service = get_user_service()
    return await user_service.get_or_create_telegram_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
    )
