"""Callback data factories for bot interactions."""

from aiogram.filters.callback_data import CallbackData

OPEN_BUY_CALLBACK = "open_buy"
OPEN_CONNECT_CALLBACK = "open_connect"
APPLY_PROMO_CALLBACK = "apply_promo"
CLEAR_PROMO_CALLBACK = "clear_promo"
SHOW_SUPPORT_CALLBACK = "show_support"


class BuyPlanCallback(CallbackData, prefix="buy"):
    """Callback payload for selecting a subscription plan to buy."""

    plan_id: str


class CheckPaymentCallback(CallbackData, prefix="check_payment"):
    """Callback payload for checking payment status in checkout message."""

    payment_id: str
