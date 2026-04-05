from pydantic import BaseModel


class SubscriptionStatusResponse(BaseModel):
    """Represent subscription status response."""

    remaining_frozen_days: int
    is_frozen: bool
    active_expires_at: str | None
    activated_at: str | None = None
    frozen_at: str | None = None


class SubscriptionUrlResponse(BaseModel):
    """Represent subscription url response."""

    subscription_url: str | None
