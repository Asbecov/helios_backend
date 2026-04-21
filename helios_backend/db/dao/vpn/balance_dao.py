from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from helios_backend.db.models.vpn.balance import Balance
from helios_backend.db.models.vpn.user import User


class BalanceDao:
    """DB access for user balance records."""

    @staticmethod
    def _remaining_days_with_half_day_threshold(remaining_seconds: float) -> int:
        """Handle remaining days with half day threshold."""
        day_seconds = 86400
        full_days = int(remaining_seconds // day_seconds)
        remainder = remaining_seconds - (full_days * day_seconds)
        return full_days + (1 if remainder >= day_seconds / 2 else 0)

    async def get_by_user(self, user: User) -> Balance | None:
        """Handle get by user."""
        return await Balance.filter(user=user).first()

    async def get_by_id_with_user(self, balance_id: UUID) -> Balance | None:
        """Return balance by id with prefetched user relation."""
        return await Balance.filter(id=balance_id).select_related("user").first()

    async def create_for_user(self, user: User, days_duration: int) -> Balance:
        """Handle create for user."""
        return await Balance.create(user=user, remaining_frozen_days=days_duration)

    async def add_days(self, balance: Balance, days: int) -> Balance:
        """Handle add days."""
        if days <= 0:
            return balance

        if not balance.is_frozen and balance.expires_at is not None:
            anchor: datetime = (
                balance.expires_at
                if balance.expires_at > datetime.now(tz=UTC)
                else datetime.now(tz=UTC)
            )
            balance.expires_at = anchor + timedelta(days=days)
            await balance.save(update_fields=["expires_at"])
            return balance

        balance.remaining_frozen_days += days
        await balance.save(update_fields=["remaining_frozen_days"])
        return balance

    async def activate(self, balance: Balance, now: datetime) -> None:
        """Handle activate."""
        if not balance.is_frozen:
            return

        balance.expires_at = now + timedelta(days=balance.remaining_frozen_days)
        balance.remaining_frozen_days = 0

        balance.is_frozen = False
        balance.activated_at = now
        await balance.save(
            update_fields=[
                "is_frozen",
                "activated_at",
                "expires_at",
                "remaining_frozen_days",
            ]
        )

    async def freeze(self, balance: Balance, now: datetime) -> None:
        """Handle freeze."""
        if balance.is_frozen:
            return

        if balance.expires_at is not None:
            remaining_seconds = max((balance.expires_at - now).total_seconds(), 0)
            balance.remaining_frozen_days = (
                self._remaining_days_with_half_day_threshold(
                    remaining_seconds,
                )
            )
        else:
            balance.remaining_frozen_days = 0

        balance.is_frozen = True
        balance.frozen_at = now
        balance.expires_at = cast(datetime | None, None)
        await balance.save(
            update_fields=[
                "is_frozen",
                "frozen_at",
                "remaining_frozen_days",
                "expires_at",
            ]
        )

    async def get_expiring_active_between(
        self, start_at: datetime, end_at: datetime
    ) -> list[Balance]:
        """Handle get expiring active between."""
        return await Balance.filter(
            is_frozen=False,
            expires_at__gte=start_at,
            expires_at__lt=end_at,
        ).select_related("user")

    async def get_expired_active_before(self, threshold: datetime) -> list[Balance]:
        """Handle get expired active before."""
        return await Balance.filter(
            is_frozen=False,
            expires_at__lt=threshold,
        ).select_related("user")

    async def get_active_with_expiry(self) -> list[Balance]:
        """Return active balances that have an explicit expiry timestamp."""
        return await Balance.filter(
            is_frozen=False,
            expires_at__isnull=False,
        ).order_by("expires_at")

    async def get_frozen_with_remaining_days(self) -> list[Balance]:
        """Handle get frozen balances with available days."""
        return await Balance.filter(
            is_frozen=True,
            remaining_frozen_days__gt=0,
        ).select_related("user")

    async def delete_by_user(self, user: User) -> None:
        """Handle delete by user."""
        await Balance.filter(user=user).delete()
