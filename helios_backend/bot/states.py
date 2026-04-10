"""FSM states for bot flows."""

from aiogram.fsm.state import State, StatesGroup


class BuyPromoState(StatesGroup):
    """FSM state for promo code input in buy flow."""

    waiting_code = State()
