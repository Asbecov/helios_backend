"""Free proxy command and callbacks."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from helios_backend.bot.common import send_route_message
from helios_backend.bot.keyboards import (
    FREE_PROXY_BUTTON_TEXT,
    build_free_proxy_keyboard,
    build_main_menu_keyboard,
)
from helios_backend.bot.services import get_proxy_service
from helios_backend.db.models.vpn.active_proxies import ActiveProxy

router = Router(name="subscription-bot-proxies")


@router.message(Command("proxy"))
@router.message(F.text == FREE_PROXY_BUTTON_TEXT)
async def free_proxy_command(message: Message) -> None:
    """Show list of free proxies from database."""
    proxy_service = get_proxy_service()
    proxies : list[ActiveProxy] = await proxy_service.get_active_proxies()

    if not proxies:
        await send_route_message(
            bot=message.bot,
            chat_id=message.chat.id,
            text="❌ Сейчас нет доступных бесплатных прокси. \n Пожалуйста, попробуйте позже.",
            route="proxy",
            reply_markup=build_main_menu_keyboard(),
        )
        return

    await send_route_message(
        bot=message.bot,
        chat_id=message.chat.id,
        text="Выберите бесплатный прокси: \n",
        route="proxy",
        reply_markup=build_free_proxy_keyboard(proxies),
    )
