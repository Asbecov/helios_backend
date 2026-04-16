"""Buy command and callbacks."""

from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from helios_backend.bot.callbacks import (
    APPLY_PROMO_CALLBACK,
    CLEAR_PROMO_CALLBACK,
    OPEN_BUY_CALLBACK,
    OPEN_CONNECT_CALLBACK,
    BuyPlanCallback,
    CheckPaymentCallback,
)
from helios_backend.bot.common import (
    delete_callback_message,
    process_buy_plan_selection,
    resolve_user,
    resolve_user_from_callback,
    send_buy_flow,
    send_route_message,
)
from helios_backend.bot.common.text import format_date_label
from helios_backend.bot.keyboards import BUY_BUTTON_TEXT, build_promo_input_keyboard
from helios_backend.bot.services import (
    get_balance_service,
    get_code_service,
    get_payment_service,
)
from helios_backend.bot.states import BuyPromoState
from helios_backend.db.models.vpn.payment import PaymentStatus

router = Router(name="subscription-bot-buy")


def _build_paid_payment_status_text(
    status: dict[str, int | bool | str | None] | None,
) -> str:
    """Build payment success summary with current subscription term."""
    if status is None:
        return "✅ Оплата прошла успешно."

    active_expires_at = status.get("active_expires_at")
    if status.get("is_frozen") is False and isinstance(active_expires_at, str):
        return (
            "✅ Оплата прошла успешно.\n\n"
            f"📅 Подписка активна до {format_date_label(active_expires_at)}"
        )

    remaining_frozen_days = status.get("remaining_frozen_days")
    if isinstance(remaining_frozen_days, int) and remaining_frozen_days > 0:
        return f"✅ Оплата прошла успешно.\n\n⏸ Доступно дней: {remaining_frozen_days}"

    return "✅ Оплата прошла успешно."


@router.message(Command("buy"))
@router.message(F.text == BUY_BUTTON_TEXT)
async def buy_command(message: Message, state: FSMContext) -> None:
    """Show plans and purchase actions."""
    user = await resolve_user(message)
    if user is None:
        return

    await state.set_state(None)
    await send_buy_flow(
        bot=message.bot,
        chat_id=message.chat.id,
        user=user,
        state=state,
    )


@router.callback_query(F.data.in_({OPEN_BUY_CALLBACK, OPEN_CONNECT_CALLBACK}))
async def open_buy_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Open buy flow from inline buttons, including legacy open_connect callback."""
    user = await resolve_user_from_callback(callback)
    if user is None:
        return
    if callback.message is None or not hasattr(callback.message, "chat"):
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return

    await state.set_state(None)
    await delete_callback_message(callback)
    await send_buy_flow(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        user=user,
        state=state,
    )
    await callback.answer("Показываю тарифы")


@router.callback_query(F.data == APPLY_PROMO_CALLBACK)
async def apply_promo_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Ask user for promo code input and replace current inline message."""
    user = await resolve_user_from_callback(callback)
    if user is None:
        return
    if callback.message is None or not hasattr(callback.message, "chat"):
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return

    await state.set_state(BuyPromoState.waiting_code)
    await delete_callback_message(callback)
    await send_route_message(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text="🎁 Введите промокод одним сообщением.\n\nПример: HELIOS10",
        route="buy",
        reply_markup=build_promo_input_keyboard(),
    )
    await callback.answer("Ожидаю промокод")


@router.callback_query(F.data == CLEAR_PROMO_CALLBACK)
async def clear_promo_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Clear promo code from state and refresh buy flow."""
    user = await resolve_user_from_callback(callback)
    if user is None:
        return
    if callback.message is None or not hasattr(callback.message, "chat"):
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return

    await state.update_data(promo_code=None)
    await state.set_state(None)
    await delete_callback_message(callback)
    await send_buy_flow(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        user=user,
        state=state,
        notice="Промокод удален.",
    )
    await callback.answer("Промокод сброшен")


@router.message(BuyPromoState.waiting_code)
async def promo_code_input(message: Message, state: FSMContext) -> None:
    """Apply promo code entered by user and refresh buy route message."""
    user = await resolve_user(message)
    if user is None:
        return

    raw_text = (message.text or "").strip()
    if not raw_text:
        await send_route_message(
            bot=message.bot,
            chat_id=message.chat.id,
            text="❌ Промокод пустой. Отправьте код текстом.",
            route="buy",
            reply_markup=build_promo_input_keyboard(),
        )
        return

    if raw_text.startswith("/"):
        await send_route_message(
            bot=message.bot,
            chat_id=message.chat.id,
            text="❌ Отправьте промокод текстом без символа '/'.",
            route="buy",
            reply_markup=build_promo_input_keyboard(),
        )
        return

    code_service = get_code_service()
    resolved_code = await code_service.resolve_valid_code(raw_text, user_id=user.id)
    if resolved_code is None:
        await send_route_message(
            bot=message.bot,
            chat_id=message.chat.id,
            text="❌ Промокод недействителен. Попробуйте снова.",
            route="buy",
            reply_markup=build_promo_input_keyboard(),
        )
        return

    await state.update_data(promo_code=resolved_code.code)
    await state.set_state(None)
    await send_buy_flow(
        bot=message.bot,
        chat_id=message.chat.id,
        user=user,
        state=state,
        notice=f"✅ Промокод {resolved_code.code} применен.",
    )


@router.callback_query(BuyPlanCallback.filter())
async def buy_plan_callback(
    callback: CallbackQuery,
    callback_data: BuyPlanCallback,
    state: FSMContext,
) -> None:
    """Create payment for selected plan and show checkout link."""
    await process_buy_plan_selection(
        callback=callback,
        callback_plan_id=callback_data.plan_id,
        state=state,
    )


@router.callback_query(CheckPaymentCallback.filter())
async def check_payment_callback(
    callback: CallbackQuery,
    callback_data: CheckPaymentCallback,
) -> None:
    """Check payment status from checkout message and notify only when paid."""
    user = await resolve_user_from_callback(callback)
    if user is None:
        return

    try:
        payment_id = UUID(callback_data.payment_id)
    except ValueError:
        await callback.answer("❌ Некорректный идентификатор платежа.", show_alert=True)
        return

    payment_service = get_payment_service()
    payment = await payment_service.get_user_payment(
        payment_id=payment_id,
        user_id=user.id,
    )
    if payment is None:
        await callback.answer("❌ Платеж не найден.", show_alert=True)
        return

    if payment.status is not PaymentStatus.PAID:
        await callback.answer()
        return

    if callback.message is not None and hasattr(callback.message, "chat"):
        balance_service = get_balance_service()
        status_payload = await balance_service.get_status(user)
        await send_route_message(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            text=_build_paid_payment_status_text(status_payload),
            route="buy",
        )

    await callback.answer("Оплата подтверждена")
