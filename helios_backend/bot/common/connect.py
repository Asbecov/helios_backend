"""Connect flow helpers for bot routes."""

from datetime import datetime

from aiogram import Bot

from helios_backend.bot.common.messaging import send_route_message
from helios_backend.bot.keyboards import (
    build_external_link_keyboard,
    build_subscribe_keyboard,
)
from helios_backend.bot.services import (
    get_balance_service,
    get_marzban_service,
    get_user_service,
)
from helios_backend.db.models.vpn.user import User
from helios_backend.services.marzban.service import (
    MarzbanServiceError,
    MarzbanUserAlreadyExistsError,
)


async def send_connect_flow(bot: Bot | None, chat_id: int, user: User) -> None:
    """Send connection flow only for active subscriptions."""
    balance_service = get_balance_service()
    user_service = get_user_service()
    marzban_service = get_marzban_service()

    status = await balance_service.get_status(user)
    if status is None:
        await send_route_message(
            bot=bot,
            chat_id=chat_id,
            text=(
                "🚫 У вас нет активной подписки.\n"
                "Сначала откройте раздел покупки, выберите тариф и оплатите его."
            ),
            route="connect",
            reply_markup=build_subscribe_keyboard(),
        )
        return

    if status.get("is_frozen") is True:
        frozen_days_raw = status.get("remaining_frozen_days")
        frozen_days = frozen_days_raw if isinstance(frozen_days_raw, int) else 0
        if frozen_days > 0:
            status = await balance_service.activate(user)

    if status is None or status.get("is_frozen") is not False:
        await send_route_message(
            bot=bot,
            chat_id=chat_id,
            text=(
                "🚫 У вас нет активной подписки.\n"
                "Сначала откройте раздел покупки, выберите тариф и оплатите его."
            ),
            route="connect",
            reply_markup=build_subscribe_keyboard(),
        )
        return

    active_expires_at = status.get("active_expires_at")
    if not isinstance(active_expires_at, str):
        await send_route_message(
            bot=bot,
            chat_id=chat_id,
            text="Не удалось определить срок действия подписки.",
            route="connect",
        )
        return

    marzban_username = await user_service.get_or_create_marzban_username(user)
    expires_at = datetime.fromisoformat(active_expires_at)

    try:
        try:
            await marzban_service.create_user(
                username=marzban_username,
                expires_at=expires_at,
            )
        except MarzbanUserAlreadyExistsError:
            await marzban_service.extend_user(
                username=marzban_username,
                expires_at=expires_at,
            )

        subscription_url = await marzban_service.get_subscription_url(marzban_username)
    except MarzbanServiceError:
        await send_route_message(
            bot=bot,
            chat_id=chat_id,
            text=("Сервис подключения временно недоступен. Попробуйте немного позже."),
            route="connect",
        )
        return

    if not subscription_url:
        await send_route_message(
            bot=bot,
            chat_id=chat_id,
            text="Не удалось сформировать ссылку подключения.",
            route="connect",
        )
        return

    await send_route_message(
        bot=bot,
        chat_id=chat_id,
        text=(
            "🚀 Подключение готово\n\n"
            "Для подключения нажмите на кнопку ниже и следуйте инструкциям.\n"
        ),
        route="connect",
        reply_markup=build_external_link_keyboard(
            button_text="Открыть ссылку подключения",
            url=subscription_url,
        ),
    )
