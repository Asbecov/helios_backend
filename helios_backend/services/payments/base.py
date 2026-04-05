from abc import ABC, abstractmethod
from typing import Any

from helios_backend.db.models.vpn.payment import Payment


class BasePaymentProvider(ABC):
    """Base interface for payment providers."""

    name: str

    @abstractmethod
    async def create_payment(self, payment: Payment) -> dict[str, Any]:
        """Create external payment object and return provider payload."""

    @abstractmethod
    async def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Parse provider webhook into normalized payload."""

    @abstractmethod
    async def verify(
        self, payload: dict[str, Any], signature: str | None = None
    ) -> bool:
        """Verify webhook signature/authenticity."""
