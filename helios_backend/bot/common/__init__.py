"""Common helpers facade for bot routes."""

from helios_backend.bot.common.buy import (
    extract_promo_code_from_state,
    process_buy_plan_selection,
    send_buy_flow,
)
from helios_backend.bot.common.connect import send_connect_flow
from helios_backend.bot.common.messaging import (
    delete_callback_message,
    send_route_message,
)
from helios_backend.bot.common.text import (
    build_help_text,
    build_support_text,
    format_user_profile,
)
from helios_backend.bot.common.users import resolve_user, resolve_user_from_callback

__all__ = [
    "build_help_text",
    "build_support_text",
    "delete_callback_message",
    "extract_promo_code_from_state",
    "format_user_profile",
    "process_buy_plan_selection",
    "resolve_user",
    "resolve_user_from_callback",
    "send_buy_flow",
    "send_connect_flow",
    "send_route_message",
]
