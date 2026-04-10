"""General bot commands."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from helios_backend.bot.common import build_help_text, send_route_message
from helios_backend.bot.keyboards import build_main_menu_keyboard

router = Router(name="subscription-bot-general")


@router.message(Command("start"))
async def start_command(message: Message) -> None:
    """Show available commands for quick navigation."""
    username = message.from_user.username if message.from_user else None
    await send_route_message(
        bot=message.bot,
        chat_id=message.chat.id,
        text=build_help_text(username),
        route="help",
        reply_markup=build_main_menu_keyboard(),
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    """Show help text and persistent menu."""
    username = message.from_user.username if message.from_user else None
    await send_route_message(
        bot=message.bot,
        chat_id=message.chat.id,
        text=build_help_text(username),
        route="help",
        reply_markup=build_main_menu_keyboard(),
    )
