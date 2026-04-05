from decimal import Decimal
from uuid import UUID

from helios_backend.db.models.vpn.subscription_plan import SubscriptionPlan
from helios_backend.settings import settings


class PlanDao:
    """DB access for subscription plans."""

    async def _get_base_plan(self) -> SubscriptionPlan | None:
        """Handle get base plan."""
        return await SubscriptionPlan.filter(is_base=True).first()

    async def get_all(self) -> list[SubscriptionPlan]:
        """Handle get all."""
        return await SubscriptionPlan.filter(is_base=False).order_by("price")

    async def get_by_id(self, plan_id: UUID) -> SubscriptionPlan | None:
        """Handle get by id."""
        return await SubscriptionPlan.filter(id=plan_id).first()

    async def get_or_create_base_plan(
        self,
        name: str | None = None,
        duration_days: int | None = None,
    ) -> SubscriptionPlan:
        """Handle get or create base plan."""
        resolved_name = name or settings.base_plan_name
        resolved_duration_days = duration_days or settings.base_plan_duration_days

        base_plan: SubscriptionPlan | None = await self._get_base_plan()
        if base_plan:
            update_fields: list[str] = []
            if base_plan.name != resolved_name:
                base_plan.name = resolved_name
                update_fields.append("name")
            if base_plan.duration_days != resolved_duration_days:
                base_plan.duration_days = resolved_duration_days
                update_fields.append("duration_days")
            if update_fields:
                await base_plan.save(update_fields=update_fields)
            return base_plan

        plan, _ = await SubscriptionPlan.get_or_create(
            name=resolved_name,
            defaults={
                "duration_days": resolved_duration_days,
                "price": Decimal("0.00"),
                "is_base": True,
                "tags": {"type": "base"},
            },
        )
        return plan
