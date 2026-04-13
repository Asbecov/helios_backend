from uuid import UUID

from pydantic import BaseModel


class PaymentCreateRequest(BaseModel):
    """Represent payment create request."""

    plan_id: UUID
    provider: str = "dummy"
    code: str | None = None


class PaymentCreateResponse(BaseModel):
    """Represent payment create response."""

    payment_id: UUID
    status: str
    external_id: str
    checkout_url: str


class WebhookResponse(BaseModel):
    """Represent webhook response."""

    payment_id: UUID
    status: str
