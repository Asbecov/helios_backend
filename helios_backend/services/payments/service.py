from decimal import Decimal
from uuid import UUID

from tortoise.transactions import in_transaction

from helios_backend.db.dao.vpn.payment_dao import PaymentDao
from helios_backend.db.models.vpn.code import CodeType
from helios_backend.db.models.vpn.payment import Payment, PaymentStatus
from helios_backend.db.models.vpn.user import User
from helios_backend.services.balance.service import BalanceService
from helios_backend.services.codes.service import CodeService
from helios_backend.services.payments.base import BasePaymentProvider
from helios_backend.services.payments.dummy_provider import DummyProvider
from helios_backend.services.plans.service import PlanService
from helios_backend.services.users.service import UserService


class PaymentService:
    """Payment lifecycle with provider abstraction and activation hooks."""

    def __init__(
        self,
        payment_dao: PaymentDao | None = None,
        plan_service: PlanService | None = None,
        code_service: CodeService | None = None,
        user_service: UserService | None = None,
        balance_service: BalanceService | None = None,
    ) -> None:
        """Initialize payment service."""
        self._payment_dao = payment_dao or PaymentDao()
        self._plan_service = plan_service or PlanService()
        self._code_service = code_service or CodeService()
        self._user_service = user_service or UserService()
        self._balance_service = balance_service or BalanceService()
        self._providers: dict[str, BasePaymentProvider] = {
            DummyProvider.name: DummyProvider()
        }

    def _provider(self, name: str) -> BasePaymentProvider:
        """Handle provider."""
        provider = self._providers.get(name.lower())
        if provider is None:
            msg = "provider is not supported"
            raise ValueError(msg)
        return provider

    async def create_payment(
        self,
        user: User,
        plan_id: UUID,
        provider_name: str,
        code_raw: str | None,
    ) -> tuple[Payment, dict[str, str]]:
        """Handle create payment."""
        plan = await self._plan_service.get_plan_by_id(plan_id)
        if plan is None:
            msg = "plan not found"
            raise ValueError(msg)

        code = await self._code_service.resolve_valid_code(
            code=code_raw, user_id=user.id
        )
        if code_raw and code is None:
            msg = "invalid or already used code"
            raise ValueError(msg)

        amount = self._plan_service.calculate_with_discount(plan=plan, code=code)

        provider_key = provider_name.lower()

        payment = await self._payment_dao.create_pending(
            user=user,
            plan=plan,
            code=code,
            amount=amount,
            provider=provider_key,
        )

        if payment.amount == Decimal("0.00"):
            await self._finalize_paid_payment(payment)
            return payment, {
                "external_id": payment.external_id,
                "checkout_url": "",
            }

        provider_payload = await self._provider(provider_name).create_payment(payment)
        await self._payment_dao.set_external_id(
            payment, provider_payload["external_id"]
        )

        return payment, provider_payload

    async def process_webhook(
        self,
        provider_name: str,
        payload: dict[str, str],
        signature: str | None,
    ) -> Payment:
        """Handle process webhook."""
        provider = self._provider(provider_name)
        if not await provider.verify(payload, signature):
            msg = "invalid webhook signature"
            raise ValueError(msg)

        normalized = await provider.handle_webhook(payload)
        payment = await self._payment_dao.get_by_external_id(normalized["external_id"])
        if payment is None:
            msg = "payment not found"
            raise ValueError(msg)

        if payment.provider != provider_name.lower():
            msg = "provider mismatch"
            raise ValueError(msg)

        # Ignore duplicate callbacks once payment is finalized as paid.
        if payment.status is PaymentStatus.PAID:
            return payment

        try:
            status = PaymentStatus(normalized["status"])
        except ValueError as exc:
            msg = "invalid payment status"
            raise ValueError(msg) from exc

        if status is not PaymentStatus.PAID:
            await self._payment_dao.set_status(payment, status)
            return payment

        await self._finalize_paid_payment(payment)
        return payment

    async def _finalize_paid_payment(self, payment: Payment) -> None:
        """Handle finalize paid payment."""
        async with in_transaction():
            # Compare-and-set ensures only one concurrent callback
            # finalizes side effects.
            marked_paid = await self._payment_dao.mark_paid_if_unpaid(payment)
            if not marked_paid:
                refreshed = await self._payment_dao.get_by_id(payment.id)
                if refreshed is not None:
                    payment.status = refreshed.status
                return

            if payment.user is None or payment.plan is None:
                msg = "payment relation data is incomplete"
                raise RuntimeError(msg)

            await self._balance_service.apply_plan(payment.user, payment.plan)
            await self._code_service.consume(payment.code, user_id=payment.user.id)
            await self._apply_referral_reward(payment)

    async def _apply_referral_reward(self, payment: Payment) -> None:
        """Handle apply referral reward."""
        if payment.plan is None:
            return

        reward_code = payment.code
        if reward_code is None or reward_code.type is not CodeType.REFERRAL:
            return

        await reward_code.fetch_related("owner")
        if reward_code.owner is None or not reward_code.reward_days_percent:
            return

        owner = await self._user_service.get_user_by_id(reward_code.owner.id)
        if owner is None:
            return

        reward_days = max(
            1,
            int(payment.plan.duration_days * reward_code.reward_days_percent / 100),
        )
        await self._balance_service.apply_bonus(owner, reward_days)
