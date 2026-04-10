"""Support command and callbacks."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from helios_backend.bot.callbacks import SHOW_SUPPORT_CALLBACK
from helios_backend.bot.common import (
    build_support_text,
    delete_callback_message,
    send_route_message,
)
from helios_backend.bot.keyboards import (
    SUPPORT_BUTTON_TEXT,
    build_main_menu_keyboard,
    build_support_keyboard,
)

router = Router(name="subscription-bot-support")


@router.message(Command("support"))
@router.message(F.text == SUPPORT_BUTTON_TEXT)
async def support_command(message: Message) -> None:
    """Return support contacts from settings."""
    await send_route_message(
        bot=message.bot,
        chat_id=message.chat.id,
        text=build_support_text(),
        route="support",
        reply_markup=build_main_menu_keyboard(),
    )


@router.callback_query(F.data == SHOW_SUPPORT_CALLBACK)
async def show_support_callback(callback: CallbackQuery) -> None:
    """Return support contacts and replace current inline message."""
    if callback.message is None or not hasattr(callback.message, "chat"):
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return

    await delete_callback_message(callback)
    await send_route_message(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=build_support_text(),
        route="support",
        reply_markup=build_support_keyboard(),
    )
    await callback.answer("Контакты поддержки")
