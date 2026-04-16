from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from helios_backend.bot.callbacks import (
    APPLY_PROMO_CALLBACK,
    CLEAR_PROMO_CALLBACK,
    OPEN_BUY_CALLBACK,
    SHOW_SUPPORT_CALLBACK,
    CheckPaymentCallback,
)
from helios_backend.bot.keyboards import (
    build_account_keyboard,
    build_checkout_keyboard,
    build_plans_keyboard,
)


def test_build_plans_keyboard_includes_tags_in_parentheses() -> None:
    """Render plan tags in parentheses in subscription buttons."""
    plan = SimpleNamespace(
        id=uuid4(),
        name="Fade",
        duration_days=450,
        tags={"region": "EU", "speed": "max"},
    )

    keyboard = build_plans_keyboard(
        [(plan, Decimal("1990.00"))],
        promo_applied=False,
    )
    button_text = keyboard.inline_keyboard[0][0].text

    assert button_text is not None
    assert "(region: EU, speed: max)" in button_text


def test_build_plans_keyboard_omits_parentheses_without_tags() -> None:
    """Do not add empty parentheses when plan has no tags."""
    plan = SimpleNamespace(
        id=uuid4(),
        name="Fade",
        duration_days=30,
        tags={},
    )

    keyboard = build_plans_keyboard(
        [(plan, Decimal("299.00"))],
        promo_applied=False,
    )
    button_text = keyboard.inline_keyboard[0][0].text

    assert button_text is not None
    assert "(" not in button_text


def test_build_plans_keyboard_adds_promo_and_support_actions() -> None:
    """Include promo and support action rows in plans keyboard."""
    plan = SimpleNamespace(
        id=uuid4(),
        name="Fade",
        duration_days=30,
        tags={},
    )

    keyboard = build_plans_keyboard(
        [(plan, Decimal("299.00"))],
        promo_applied=False,
    )
    callback_values = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data is not None
    ]

    assert APPLY_PROMO_CALLBACK in callback_values
    assert SHOW_SUPPORT_CALLBACK in callback_values
    assert CLEAR_PROMO_CALLBACK not in callback_values


def test_build_plans_keyboard_shows_clear_promo_when_applied() -> None:
    """Show clear-promo action only when promo is already applied."""
    plan = SimpleNamespace(
        id=uuid4(),
        name="Fade",
        duration_days=30,
        tags={},
    )

    keyboard = build_plans_keyboard(
        [(plan, Decimal("299.00"))],
        promo_applied=True,
    )
    callback_values = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data is not None
    ]

    assert CLEAR_PROMO_CALLBACK in callback_values


def test_build_account_keyboard_contains_copy_button() -> None:
    """Expose quick copy action for referral code in account route."""
    keyboard = build_account_keyboard(referral_code="ABC123", show_buy_button=True)

    copy_button = keyboard.inline_keyboard[0][0]
    assert copy_button.switch_inline_query_current_chat == "ABC123"

    callback_values = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data is not None
    ]
    assert OPEN_BUY_CALLBACK in callback_values
    assert SHOW_SUPPORT_CALLBACK in callback_values


def test_build_checkout_keyboard_contains_support_and_back() -> None:
    """Keep support and back actions near checkout URL button."""
    keyboard = build_checkout_keyboard(
        "https://example.com/checkout",
        payment_id="payment-1",
    )

    callback_values = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data is not None
    ]
    assert SHOW_SUPPORT_CALLBACK in callback_values
    assert OPEN_BUY_CALLBACK in callback_values
    assert CheckPaymentCallback(payment_id="payment-1").pack() in callback_values
