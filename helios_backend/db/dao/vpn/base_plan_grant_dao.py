from uuid import UUID

from helios_backend.db.models.vpn.base_plan_grant import BasePlanGrant


class BasePlanGrantDao:
    """DB access for one-time base-plan grant ledger."""

    async def has_grant(self, telegram_id: int) -> bool:
        """Return whether base plan was already granted for telegram_id."""
        return await BasePlanGrant.filter(telegram_id=telegram_id).exists()

    async def record_if_absent(self, telegram_id: int, user_id: UUID) -> bool:
        """Record grant once and return True only on first insert."""
        _, created = await BasePlanGrant.get_or_create(
            telegram_id=telegram_id,
            defaults={"user_id": user_id},
        )
        return created
