from decimal import Decimal
from uuid import UUID, uuid4

from helios_backend.db.models.vpn.code import Code
from helios_backend.db.models.vpn.payment import Payment, PaymentStatus
from helios_backend.db.models.vpn.subscription_plan import SubscriptionPlan
from helios_backend.db.models.vpn.user import User


class PaymentDao:
    """DB access for payments table."""

    async def create_pending(
        self,
        user: User,
        plan: SubscriptionPlan,
        code: Code | None,
        amount: Decimal,
        provider: str,
    ) -> Payment:
        """Handle create pending."""
        return await Payment.create(
            user=user,
            plan=plan,
            code=code,
            amount=amount,
            status=PaymentStatus.PENDING,
            provider=provider,
            external_id=f"pending-{uuid4()}",
        )

    async def get_by_external_id(self, external_id: str) -> Payment | None:
        """Handle get by external id."""
        return (
            await Payment.filter(external_id=external_id)
            .select_related(
                "user",
                "plan",
                "code",
            )
            .first()
        )

    async def set_external_id(self, payment: Payment, external_id: str) -> None:
        """Handle set external id."""
        payment.external_id = external_id
        await payment.save(update_fields=["external_id"])

    async def set_status(self, payment: Payment, status: PaymentStatus) -> None:
        """Handle set status."""
        payment.status = status
        await payment.save(update_fields=["status"])

    async def mark_paid_if_unpaid(self, payment: Payment) -> bool:
        """Handle mark paid if unpaid."""
        updated = (
            await Payment.filter(id=payment.id)
            .exclude(status=PaymentStatus.PAID)
            .update(
                status=PaymentStatus.PAID,
            )
        )
        if updated:
            payment.status = PaymentStatus.PAID
        return bool(updated)

    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        """Handle get by id."""
        return (
            await Payment.filter(id=payment_id)
            .select_related("user", "plan", "code")
            .first()
        )

    async def get_by_id_and_user(
        self,
        payment_id: UUID,
        user_id: UUID,
    ) -> Payment | None:
        """Handle get by id restricted to owner user."""
        return (
            await Payment.filter(id=payment_id, user_id=user_id)
            .select_related("user", "plan", "code")
            .first()
        )
