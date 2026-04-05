from decimal import Decimal
from uuid import UUID

from helios_backend.db.models.vpn.subscription_plan import SubscriptionPlan
from helios_backend.settings import settings


class PlanDao:
    """DB access for subscription plans."""

    @staticmethod
    def _base_plan_name() -> str:
        """Handle base plan name."""
        return settings.base_plan_name

    @staticmethod
    def _base_plan_duration_days() -> int:
        """Handle base plan duration days."""
        return settings.base_plan_duration_days

    async def _get_base_plan(self) -> SubscriptionPlan | None:
        """Handle get base plan."""
        return await SubscriptionPlan.filter(is_base=True).first()

    async def get_all(self) -> list[SubscriptionPlan]:
        """Handle get all."""
        return await SubscriptionPlan.all().order_by("price")

    async def get_by_id(self, plan_id: UUID) -> SubscriptionPlan | None:
        """Handle get by id."""
        return await SubscriptionPlan.filter(id=plan_id).first()

    async def get_or_create_base_plan(self) -> SubscriptionPlan:
        """Handle get or create base plan."""
        base_plan: SubscriptionPlan | None = await self._get_base_plan()
        if base_plan:
            return base_plan

        plan, _ = await SubscriptionPlan.get_or_create(
            name=self._base_plan_name(),
            defaults={
                "duration_days": self._base_plan_duration_days(),
                "price": Decimal("0.00"),
                "is_base": True,
                "tags": {"type": "base"},
            },
        )
        return plan
