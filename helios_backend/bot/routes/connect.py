"""Connect command handlers."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from helios_backend.bot.common import resolve_user, send_connect_flow
from helios_backend.bot.keyboards import CONNECT_BUTTON_TEXT

router = Router(name="subscription-bot-connect")


@router.message(Command("connect"))
@router.message(F.text == CONNECT_BUTTON_TEXT)
async def connect_command(message: Message, state: FSMContext) -> None:
    """Show connection details for active subscriptions only."""
    user = await resolve_user(message)
    if user is None:
        return

    await state.set_state(None)
    await send_connect_flow(bot=message.bot, chat_id=message.chat.id, user=user)
