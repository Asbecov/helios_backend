from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UserResponse(BaseModel):
    """User profile response."""

    id: UUID
    telegram_id: int
    username: str | None
    created_at: datetime
    marzban_username: str | None


class ReferralCodeResponse(BaseModel):
    """Referral code details for current user."""

    id: UUID
    code: str
    discount_percent: int | None
    reward_days_percent: int | None
    expires_at: datetime | None
    is_active: bool


class ReferralUsageResponse(BaseModel):
    """Referral code usage event for code owner."""

    id: UUID
    created_at: datetime
    code_id: UUID
    code: str
    user_id: UUID
    user_telegram_id: int
    user_username: str | None
