from decimal import Decimal
from uuid import UUID

from helios_backend.db.dao.vpn.plan_dao import PlanDao
from helios_backend.db.models.vpn.code import Code
from helios_backend.db.models.vpn.subscription_plan import SubscriptionPlan
from helios_backend.services.admin.runtime_settings import RuntimeSettingService


class PlanService:
    """Plan listing with dynamic discount application."""

    def __init__(
        self,
        plan_dao: PlanDao | None = None,
        runtime_setting_service: RuntimeSettingService | None = None,
    ) -> None:
        """Initialize plan service."""
        self._plan_dao = plan_dao or PlanDao()
        self._runtime_setting_service = (
            runtime_setting_service or RuntimeSettingService()
        )

    async def get_plan_by_id(self, plan_id: UUID) -> SubscriptionPlan | None:
        """Returns a subscription plan by id, or None if it does not exist."""
        return await self._plan_dao.get_by_id(plan_id)

    async def get_base_plan(self) -> SubscriptionPlan:
        """Return base subscription plan, creating it when missing."""
        return await self._plan_dao.get_or_create_base_plan(
            name=await self._runtime_setting_service.base_plan_name(),
            duration_days=await self._runtime_setting_service.base_plan_duration_days(),
        )

    def calculate_with_discount(
        self,
        plan: SubscriptionPlan,
        code: Code | None,
    ) -> Decimal:
        """Returns plan price with code discount applied and rounded to cents."""
        discount = code.discount_percent if code and code.discount_percent else 0
        if discount <= 0:
            return Decimal(plan.price).quantize(Decimal("0.01"))

        return (
            Decimal(plan.price)
            - (Decimal(plan.price) * Decimal(discount) / Decimal(100))
        ).quantize(Decimal("0.01"))

    async def get_plans_with_discount(
        self,
        code: Code | None,
    ) -> list[tuple[SubscriptionPlan, Decimal]]:
        """Return all plans with discount applied when code is valid."""
        plans = await self._plan_dao.get_all()
        result: list[tuple[SubscriptionPlan, Decimal]] = []
        for plan in plans:
            final_price = self.calculate_with_discount(plan=plan, code=code)
            result.append((plan, final_price))
        return result
