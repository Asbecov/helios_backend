"""Account commands."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from helios_backend.bot.common import (
    format_user_profile,
    resolve_user,
    send_route_message,
)
from helios_backend.bot.keyboards import ACCOUNT_BUTTON_TEXT, build_account_keyboard
from helios_backend.bot.services import get_balance_service, get_code_service

router = Router(name="subscription-bot-account")


@router.message(Command("my"))
@router.message(F.text == ACCOUNT_BUTTON_TEXT)
async def my_command(message: Message) -> None:
    """Show account profile, subscription state and referral details."""
    user = await resolve_user(message)
    if user is None:
        return

    balance_service = get_balance_service()
    code_service = get_code_service()
    status = await balance_service.get_status(user)
    referral_code = await code_service.get_or_create_user_referral_code(user)

    has_active_subscription = status is not None and status.get("is_frozen") is False
    await send_route_message(
        bot=message.bot,
        chat_id=message.chat.id,
        text=format_user_profile(user, status, referral_code),
        route="my",
        reply_markup=build_account_keyboard(
            referral_code=referral_code.code,
            show_buy_button=not has_active_subscription,
        ),
    )
