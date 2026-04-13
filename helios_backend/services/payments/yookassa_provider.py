import uuid
from ipaddress import ip_address, ip_network
from typing import Any, Final

from yookassa import Configuration
from yookassa import Payment as YookassaPayment
from yookassa.domain.notification import WebhookNotification

from helios_backend.db.models.vpn.payment import Payment
from helios_backend.services.payments.base import BasePaymentProvider
from helios_backend.settings import settings

_ALLOWED_SOURCE_NETWORKS: Final = (
    ip_network("185.71.76.0/27"),
    ip_network("185.71.77.0/27"),
    ip_network("77.75.153.0/25"),
    ip_network("77.75.156.11/32"),
    ip_network("77.75.156.35/32"),
    ip_network("77.75.154.128/25"),
    ip_network("2a02:5180::/32"),
)


class YookassaProvider(BasePaymentProvider):
    """Yookassa payment provider implementation."""

    def __init__(self) -> None:
        if settings.yookassa_shop_id is None or settings.yookassa_api_key is None:
            msg = "yookassa credentials are not configured"
            raise ValueError(msg)
        Configuration.configure(settings.yookassa_shop_id, settings.yookassa_api_key)

    name = "yookassa"

    async def create_payment(self, payment: Payment) -> dict[str, str]:
        """Create YooKassa payment and return normalized provider payload."""
        if settings.yookassa_return_url is None:
            msg = "yookassa return url is not configured"
            raise ValueError(msg)

        idempotence_key = str(uuid.uuid4())

        external_payment = YookassaPayment.create(
            {
                "amount": {
                    "value": f"{payment.amount:.2f}",
                    "currency": "RUB",
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": settings.yookassa_return_url,
                },
                "capture": True,
                "description": (
                    f"Оплата по тарифу {payment.plan.name} "
                    f"для пользователя {payment.user.username}"
                ),
            },
            idempotence_key,
        )

        return {
            "external_id": external_payment.id,
            "checkout_url": external_payment.confirmation.confirmation_url,
        }

    async def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle webhook."""
        try:
            notification_object = WebhookNotification(payload)
        except Exception as exc:
            raise ValueError("invalid webhook payload") from exc

        external_payment = notification_object.object

        return {
            "external_id": external_payment.id,
            "status": self._normalize_event(notification_object.event),
        }

    async def verify(
        self,
        payload: dict[str, Any],
        signature: str | None = None,
        source_ip: str | None = None,
    ) -> bool:
        """Verify webhook."""
        _ = signature

        if not self._is_allowed_source_ip(source_ip):
            return False

        event = payload.get("event")
        if not isinstance(event, str) or not event.startswith("payment."):
            return False

        object_payload = payload.get("object")
        if not isinstance(object_payload, dict):
            return False

        external_id = object_payload.get("id")
        status = object_payload.get("status")
        return isinstance(external_id, str) and isinstance(status, str)

    @staticmethod
    def _normalize_event(yookassa_event: str) -> str:
        """Map YooKassa event to internal event."""
        match yookassa_event:
            case "payment.succeeded":
                return "paid"
            case "payment.canceled":
                return "failed"
            case "payment.waiting_for_capture":
                return "pending"
            case _:
                raise ValueError("unsupported event type")

    @staticmethod
    def _is_allowed_source_ip(source_ip: str | None) -> bool:
        """Check source IP against YooKassa documented ranges."""
        if source_ip is None:
            return False

        candidate = source_ip.strip()
        if not candidate:
            return False

        try:
            parsed = ip_address(candidate)
        except ValueError:
            return False

        return any(parsed in network for network in _ALLOWED_SOURCE_NETWORKS)
