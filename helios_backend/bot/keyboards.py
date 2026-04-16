"""Inline keyboard builders for bot commands."""

from collections.abc import Sequence
from decimal import Decimal
from typing import Protocol, cast

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from helios_backend.bot.callbacks import (
    APPLY_PROMO_CALLBACK,
    CLEAR_PROMO_CALLBACK,
    OPEN_BUY_CALLBACK,
    SHOW_SUPPORT_CALLBACK,
    BuyPlanCallback,
    CheckPaymentCallback,
)

ACCOUNT_BUTTON_TEXT = "💳 Мой аккаунт, подписка"
BUY_BUTTON_TEXT = "💠 Купить подписку"
CONNECT_BUTTON_TEXT = "🚀 Подключиться"
SUPPORT_BUTTON_TEXT = "🆘 Поддержка"


class PlanKeyboardView(Protocol):
    """Structural view required to render a plan button."""

    id: object
    name: str
    duration_days: int
    tags: object


def _format_price(value: Decimal) -> str:
    """Return decimal with two fraction digits for UI labels."""
    return str(value.quantize(Decimal("0.01")))


def _format_plan_tags(tags: dict[str, str]) -> str:
    """Format plan tags for user-facing labels."""
    if not tags:
        return ""

    tag_chunks: list[str] = []
    for key, value in sorted(tags.items()):
        tag_chunks.append(f"{key}: {value}")
    return f" ({', '.join(tag_chunks)})"


def build_plans_keyboard(
    plans: Sequence[tuple[object, Decimal]],
    promo_applied: bool,
) -> InlineKeyboardMarkup:
    """Build buttons for available paid plans."""
    rows: list[list[InlineKeyboardButton]] = []
    for plan_raw, final_price in plans:
        plan = cast(PlanKeyboardView, plan_raw)
        callback_data = BuyPlanCallback(plan_id=str(plan.id)).pack()
        raw_tags = plan.tags
        tags = cast(dict[str, str], raw_tags) if isinstance(raw_tags, dict) else {}
        tags_part = _format_plan_tags(tags)
        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"💠 {plan.name}{tags_part} - "
                        f"{_format_price(final_price)} ₽ / {plan.duration_days} дн."
                    ),
                    callback_data=callback_data,
                )
            ]
        )

    promo_button_text = "🎁 Применить промокод"
    if promo_applied:
        promo_button_text = "🎁 Изменить промокод"
    rows.append(
        [
            InlineKeyboardButton(
                text=promo_button_text,
                callback_data=APPLY_PROMO_CALLBACK,
            )
        ]
    )
    if promo_applied:
        rows.append(
            [
                InlineKeyboardButton(
                    text="❌ Убрать промокод",
                    callback_data=CLEAR_PROMO_CALLBACK,
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=SUPPORT_BUTTON_TEXT,
                callback_data=SHOW_SUPPORT_CALLBACK,
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_checkout_keyboard(url: str, payment_id: str) -> InlineKeyboardMarkup:
    """Build checkout keyboard with payment and support actions."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть страницу оплаты", url=url)],
            [
                InlineKeyboardButton(
                    text="🔃 Проверить оплату",
                    callback_data=CheckPaymentCallback(
                        payment_id=payment_id,
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=SUPPORT_BUTTON_TEXT,
                    callback_data=SHOW_SUPPORT_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ К тарифам",
                    callback_data=OPEN_BUY_CALLBACK,
                )
            ],
        ]
    )


def build_external_link_keyboard(
    button_text: str,
    url: str,
) -> InlineKeyboardMarkup:
    """Build single-button URL keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=button_text, url=url)]],
    )


def build_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Build persistent main menu keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ACCOUNT_BUTTON_TEXT)],
            [KeyboardButton(text=BUY_BUTTON_TEXT)],
            [KeyboardButton(text=CONNECT_BUTTON_TEXT)],
            [KeyboardButton(text=SUPPORT_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
    )


def build_subscribe_keyboard() -> InlineKeyboardMarkup:
    """Build quick action keyboard for subscription purchase flow."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BUY_BUTTON_TEXT,
                    callback_data=OPEN_BUY_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text=SUPPORT_BUTTON_TEXT,
                    callback_data=SHOW_SUPPORT_CALLBACK,
                )
            ],
        ]
    )


def build_account_keyboard(
    referral_code: str,
    show_buy_button: bool,
) -> InlineKeyboardMarkup:
    """Build account keyboard with referral copy and optional buy shortcut."""
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="📋 Скопировать реферальный код",
                switch_inline_query_current_chat=referral_code,
            )
        ]
    ]
    if show_buy_button:
        rows.append(
            [
                InlineKeyboardButton(
                    text=BUY_BUTTON_TEXT,
                    callback_data=OPEN_BUY_CALLBACK,
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=SUPPORT_BUTTON_TEXT,
                callback_data=SHOW_SUPPORT_CALLBACK,
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_promo_input_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard shown while waiting for promo code input."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад к подпискам",
                    callback_data=OPEN_BUY_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text=SUPPORT_BUTTON_TEXT,
                    callback_data=SHOW_SUPPORT_CALLBACK,
                )
            ],
        ]
    )


def build_support_keyboard() -> InlineKeyboardMarkup:
    """Build support response keyboard with back action."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад к подпискам",
                    callback_data=OPEN_BUY_CALLBACK,
                )
            ]
        ]
    )
