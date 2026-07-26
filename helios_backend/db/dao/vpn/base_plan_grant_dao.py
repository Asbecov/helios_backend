from uuid import UUID

from helios_backend.db.models.vpn.base_plan_grant import BasePlanGrant


class BasePlanGrantDao:
    """DB access for one-time base-plan grant ledger."""

    async def has_grant(
        self,
        telegram_id: int | None = None,
        google_sub: str | None = None,
    ) -> bool:
        """Return whether base plan was already granted for telegram_id or google_sub."""
        if telegram_id is not None:
            return await BasePlanGrant.filter(telegram_id=telegram_id).exists()
        if google_sub is not None:
            return await BasePlanGrant.filter(google_sub=google_sub).exists()
        return False

    async def record_if_absent(
        self,
        user_id: UUID,
        telegram_id: int | None = None,
        google_sub: str | None = None,
    ) -> bool:
        """Record grant once and return True only on first insert."""
        if telegram_id is not None:
            _, created = await BasePlanGrant.get_or_create(
                telegram_id=telegram_id,
                defaults={"user_id": user_id},
            )
            return created
        if google_sub is not None:
            _, created = await BasePlanGrant.get_or_create(
                google_sub=google_sub,
                defaults={"user_id": user_id},
            )
            return created
        return False
