"""Buy flow helpers for bot routes."""

from decimal import Decimal
from uuid import UUID

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from helios_backend.bot.common.messaging import (
    delete_callback_message,
    send_route_message,
)
from helios_backend.bot.common.text import build_offer_text, format_tags
from helios_backend.bot.common.users import resolve_user_from_callback
from helios_backend.bot.keyboards import (
    build_checkout_keyboard,
    build_plans_keyboard,
    build_support_keyboard,
)
from helios_backend.bot.services import (
    get_balance_service,
    get_code_service,
    get_payment_service,
    get_plan_service,
    get_runtime_setting_service,
)
from helios_backend.db.models.vpn.code import Code
from helios_backend.db.models.vpn.user import User
from helios_backend.settings import settings


def extract_promo_code_from_state(data: dict[str, object]) -> str | None:
    """Extract promo code string from FSM data payload."""
    promo_code_raw = data.get("promo_code")
    if not isinstance(promo_code_raw, str):
        return None
    promo_code = promo_code_raw.strip()
    return promo_code or None


async def resolve_applied_promo_code(
    user: User,
    state: FSMContext,
) -> tuple[Code | None, str | None]:
    """Resolve promo code from state to validated code entity."""
    data = await state.get_data()
    promo_code = extract_promo_code_from_state(data)
    if promo_code is None:
        return None, None

    code_service = get_code_service()
    resolved_code = await code_service.resolve_valid_code(promo_code, user_id=user.id)
    if resolved_code is not None:
        return resolved_code, None

    await state.update_data(promo_code=None)
    return None, "❌ Промокод больше недействителен"


async def send_buy_flow(
    bot: Bot | None,
    chat_id: int,
    user: User,
    state: FSMContext,
    notice: str | None = None,
) -> None:
    """Send subscription purchase flow with optional promo discounts."""
    balance_service = get_balance_service()
    plan_service = get_plan_service()

    status = await balance_service.get_status(user)
    resolved_code, promo_notice = await resolve_applied_promo_code(user, state)
    plans = await plan_service.get_plans_with_discount(code=resolved_code)

    if not plans:
        await send_route_message(
            bot=bot,
            chat_id=chat_id,
            text="❌ Сейчас нет доступных платных планов.",
            route="buy",
        )
        return

    text = build_offer_text()

    frozen_days = 0
    if status is not None and status.get("is_frozen") is True:
        frozen_days_raw = status.get("remaining_frozen_days")
        if isinstance(frozen_days_raw, int):
            frozen_days = frozen_days_raw
    if frozen_days > 0:
        text += f"\n\n⏸ У вас уже есть замороженные дни: {frozen_days}"

    if resolved_code is not None:
        discount_percent = resolved_code.discount_percent or 0
        text += f"\n\n🎁 Промокод: {resolved_code.code}"
        if discount_percent:
            text += f" (-{discount_percent}%)"

    notices = [msg for msg in [notice, promo_notice] if msg]
    if notices:
        text += "\n\n" + "\n".join(f"ℹ️ {item}" for item in notices)

    await send_route_message(
        bot=bot,
        chat_id=chat_id,
        text=f"{text}\n\nВыберите подписку:",
        route="buy",
        reply_markup=build_plans_keyboard(
            plans,
            promo_applied=resolved_code is not None,
        ),
    )


async def process_buy_plan_selection(
    callback: CallbackQuery,
    callback_plan_id: str,
    state: FSMContext,
) -> tuple[bool, str | None]:
    """Create payment for selected plan and return checkout URL payload."""
    user = await resolve_user_from_callback(callback)
    if user is None:
        return False, None

    try:
        plan_id = UUID(callback_plan_id)
    except ValueError:
        await callback.answer("❌ Некорректный план.", show_alert=True)
        return False, None

    if callback.message is None or not hasattr(callback.message, "chat"):
        await callback.answer("❌ Сообщение для ответа не найдено.", show_alert=True)
        return False, None

    payment_service = get_payment_service()
    runtime_setting_service = get_runtime_setting_service()
    if not await runtime_setting_service.payments_enabled():
        await callback.answer("❌ Оплата временно отключена.", show_alert=True)
        return False, None

    promo_data = await state.get_data()
    promo_code = extract_promo_code_from_state(promo_data)

    try:
        payment, provider_payload = await payment_service.create_payment(
            user=user,
            plan_id=plan_id,
            provider_name=settings.telegram_default_payment_provider,
            code_raw=promo_code,
        )
    except ValueError:
        if promo_code is not None:
            await state.update_data(promo_code=None)
            await delete_callback_message(callback)
            await send_buy_flow(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                user=user,
                state=state,
                notice="❌ Промокод недействителен. Выберите подписку заново.",
            )
            await callback.answer("Промокод сброшен", show_alert=True)
            return False, None
        await callback.answer("❌ Не удалось создать платеж.", show_alert=True)
        return False, None

    plan_label = "💠 Подписка"
    if payment.plan is not None:
        plan_tags = payment.plan.tags if isinstance(payment.plan.tags, dict) else {}
        tags_label = format_tags(plan_tags)
        amount = Decimal(payment.amount).quantize(Decimal("0.01"))
        plan_label = (
            f"💠 {payment.plan.name}{tags_label} - "
            f"{amount} ₽ / {payment.plan.duration_days} дн."
        )

    await delete_callback_message(callback)

    checkout_url = provider_payload.get("checkout_url")
    if not isinstance(checkout_url, str) or not checkout_url:
        await send_route_message(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            text=(
                f"{plan_label}\n\n"
                "Платеж создан и обработан без внешнего перехода.\n"
                f"Статус: {payment.status}"
            ),
            route="buy",
            reply_markup=build_support_keyboard(),
        )
        await callback.answer("Готово")
        return True, None

    await send_route_message(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=(f"{plan_label}\n\n💳 Перейти к оплате (Банковская карта RUB)"),
        route="buy",
        reply_markup=build_checkout_keyboard(checkout_url),
    )
    await callback.answer("Ссылка на оплату отправлена")
    return True, checkout_url
