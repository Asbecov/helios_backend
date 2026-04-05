from typing import Any

from helios_backend.db.models.vpn.payment import Payment
from helios_backend.services.payments.base import BasePaymentProvider


class DummyProvider(BasePaymentProvider):
    """Test provider for local and staging workflows."""

    name = "dummy"

    async def create_payment(self, payment: Payment) -> dict[str, Any]:
        """Handle create payment."""
        return {
            "external_id": f"dummy-{payment.id}",
            "checkout_url": f"https://dummy-pay.local/checkout/{payment.id}?amount={payment.amount}",
        }

    async def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle handle webhook."""
        return {
            "external_id": payload["external_id"],
            "status": payload.get("status", "paid"),
        }

    async def verify(
        self, payload: dict[str, Any], signature: str | None = None
    ) -> bool:
        """Handle verify."""
        _ = payload
        _ = signature
        return True
