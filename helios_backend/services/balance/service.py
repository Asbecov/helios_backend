from datetime import UTC, datetime

from helios_backend.db.dao.vpn.balance_dao import BalanceDao
from helios_backend.db.models.vpn.balance import Balance
from helios_backend.db.models.vpn.subscription_plan import SubscriptionPlan
from helios_backend.db.models.vpn.user import User
from helios_backend.tasks.notifications import schedule_expiry_notification


class BalanceService:
    """Business logic around user day balances."""

    def __init__(
        self,
        balance_dao: BalanceDao | None = None,
    ) -> None:
        """Initialize balance service."""
        self._balance_dao = balance_dao or BalanceDao()

    async def _create_balance_for_user(self, user: User, days_duration: int) -> Balance:
        """Handle create balance for user."""
        return await self._balance_dao.create_for_user(user, days_duration)

    async def _get_balance_by_user(self, user: User) -> Balance | None:
        """Handle get balance by user."""
        return await self._balance_dao.get_by_user(user)

    async def _schedule_expiry_notification_if_active(self, balance: Balance) -> None:
        """Schedule one-shot expiry notification for active balances only."""
        if balance.is_frozen or balance.expires_at is None:
            return

        await schedule_expiry_notification(
            balance_id=str(balance.id),
            expected_expires_at=balance.expires_at,
        )

    async def apply_plan(self, user: User, plan: SubscriptionPlan) -> Balance:
        """Apply subscription plan days to balance, creating one if needed."""
        balance = await self._get_balance_by_user(user)
        if balance is None:
            return await self._create_balance_for_user(
                user,
                plan.duration_days,
            )

        updated: Balance = await self._balance_dao.add_days(balance, plan.duration_days)
        await self._schedule_expiry_notification_if_active(updated)
        return updated

    async def apply_bonus(self, user: User, bonus_days: int) -> Balance:
        """Add bonus days to balance, creating one if needed."""
        balance = await self._get_balance_by_user(user)
        if balance is None:
            return await self._create_balance_for_user(
                user,
                bonus_days,
            )

        updated: Balance = await self._balance_dao.add_days(balance, bonus_days)
        await self._schedule_expiry_notification_if_active(updated)
        return updated

    async def get_status(self, user: User) -> dict[str, int | bool | str | None] | None:
        """Return current balance status for user, or None when absent."""
        balance = await self._get_balance_by_user(user)
        if not balance:
            return None

        return {
            "remaining_frozen_days": balance.remaining_frozen_days,
            "is_frozen": balance.is_frozen,
            "activated_at": balance.activated_at.isoformat()
            if balance.activated_at
            else None,
            "frozen_at": balance.frozen_at.isoformat() if balance.frozen_at else None,
            "active_expires_at": balance.expires_at.isoformat()
            if balance.expires_at
            else None,
        }

    async def activate(self, user: User) -> dict[str, int | bool | str | None] | None:
        """Activate user's balance if frozen and return updated status."""
        balance = await self._get_balance_by_user(user)
        if not balance:
            return None

        now = datetime.now(tz=UTC)
        was_frozen = balance.is_frozen
        if balance.is_frozen:
            await self._balance_dao.activate(balance, now=now)
        if was_frozen:
            await self._schedule_expiry_notification_if_active(balance)

        return {
            "remaining_frozen_days": balance.remaining_frozen_days,
            "is_frozen": balance.is_frozen,
            "active_expires_at": balance.expires_at.isoformat()
            if balance.expires_at
            else None,
            "activated_at": balance.activated_at.isoformat()
            if balance.activated_at
            else None,
            "frozen_at": balance.frozen_at.isoformat() if balance.frozen_at else None,
        }

    async def freeze(self, user: User) -> dict[str, int | bool | str | None] | None:
        """Freeze user's balance if active and return updated status."""
        balance = await self._get_balance_by_user(user)
        if not balance:
            return None

        now = datetime.now(tz=UTC)
        if not balance.is_frozen:
            await self._balance_dao.freeze(balance, now=now)

        return {
            "remaining_frozen_days": balance.remaining_frozen_days,
            "is_frozen": balance.is_frozen,
            "active_expires_at": balance.expires_at.isoformat()
            if balance.expires_at
            else None,
            "activated_at": balance.activated_at.isoformat()
            if balance.activated_at
            else None,
            "frozen_at": balance.frozen_at.isoformat() if balance.frozen_at else None,
        }

    async def delete_user_balance(self, user: User) -> None:
        """Delete all balance records for given user."""
        await self._balance_dao.delete_by_user(user)
