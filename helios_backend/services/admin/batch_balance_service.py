"""Batch balance service for administrative bulk adjustments."""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from helios_backend.db.dao.vpn.balance_dao import BalanceDao
from helios_backend.db.models.vpn.balance import Balance
from helios_backend.db.models.vpn.user import User
from helios_backend.services.admin.runtime_settings import RuntimeSettingService
from helios_backend.services.balance.service import BalanceService
from helios_backend.tasks.notifications import schedule_expiry_notification

logger = logging.getLogger(__name__)


def _normalize_uuids(ids: Sequence[UUID | str | int]) -> list[UUID]:
    """Convert input id representations to UUID instances safely."""
    result: list[UUID] = []
    for raw_id in ids:
        if isinstance(raw_id, UUID):
            result.append(raw_id)
        else:
            try:
                result.append(UUID(str(raw_id)))
            except (ValueError, TypeError):
                logger.warning("Ignoring invalid UUID in batch operation: %r", raw_id)
    return result


class BatchBalanceService:
    """Service handling bulk balance additions and modifications."""

    def __init__(
        self,
        balance_dao: BalanceDao | None = None,
        balance_service: BalanceService | None = None,
        runtime_setting_service: RuntimeSettingService | None = None,
    ) -> None:
        """Initialize batch balance service with DAO and service dependencies."""
        self._balance_dao = balance_dao or BalanceDao()
        self._balance_service = balance_service or BalanceService(
            balance_dao=self._balance_dao,
        )
        self._runtime_setting_service = (
            runtime_setting_service or RuntimeSettingService()
        )

    async def get_custom_days_from_settings(self) -> int:
        """Fetch batch days increment from runtime settings, falling back to 5."""
        try:
            return await self._runtime_setting_service.batch_balance_days()
        except Exception:
            logger.exception("Failed to resolve batch_balance_days, using 5")
            return 5

    async def add_days_to_user(self, user: User, days: int) -> Balance:
        """Add specified number of days to a user balance on the server."""
        return await self._balance_service.apply_bonus(user, days)

    async def add_days_to_users(
        self,
        days: int,
        user_ids: Sequence[UUID | str | int] | None = None,
    ) -> int:
        """Add days to specified users or ALL users when user_ids is None."""
        if days <= 0:
            return 0

        if user_ids is not None:
            normalized_ids = _normalize_uuids(user_ids)
            if not normalized_ids:
                return 0
            users = await User.filter(id__in=normalized_ids).all()
        else:
            users = await User.all()

        updated_count = 0
        for user in users:
            try:
                await self.add_days_to_user(user, days)
                updated_count += 1
            except Exception:
                logger.exception("Failed to add %d days to user %s", days, user.id)

        logger.info(
            "Batch balance edit: added %d days to %d users (all_users=%s)",
            days,
            updated_count,
            user_ids is None,
        )
        return updated_count

    async def add_days_to_balance(self, balance: Balance, days: int) -> Balance:
        """Add specified days to a balance record directly on the server."""
        updated = await self._balance_dao.add_days(balance, days)

        if not updated.is_frozen and updated.expires_at is not None:
            await schedule_expiry_notification(
                balance_id=str(updated.id),
                expected_expires_at=updated.expires_at,
            )

        return updated

    async def add_days_to_balances(
        self,
        days: int,
        balance_ids: Sequence[UUID | str | int] | None = None,
    ) -> int:
        """Add days to specified balances or ALL balances when balance_ids is None."""
        if days <= 0:
            return 0

        if balance_ids is not None:
            normalized_ids = _normalize_uuids(balance_ids)
            if not normalized_ids:
                return 0
            balances = await Balance.filter(id__in=normalized_ids).all()
        else:
            balances = await Balance.all()

        updated_count = 0
        for balance in balances:
            try:
                await self.add_days_to_balance(balance, days)
                updated_count += 1
            except Exception:
                logger.exception(
                    "Failed to add %d days to balance %s",
                    days,
                    balance.id,
                )

        logger.info(
            "Batch balance edit: added %d days to %d balances (all_balances=%s)",
            days,
            updated_count,
            balance_ids is None,
        )
        return updated_count

    async def freeze_balances(
        self,
        balance_ids: Sequence[UUID | str | int] | None = None,
    ) -> int:
        """Freeze selected balances or all active balances."""
        if balance_ids is not None:
            normalized_ids = _normalize_uuids(balance_ids)
            if not normalized_ids:
                return 0
            balances = await Balance.filter(id__in=normalized_ids).all()
        else:
            balances = await Balance.filter(is_frozen=False).all()

        now = datetime.now(tz=UTC)
        count = 0
        for balance in balances:
            if not balance.is_frozen:
                try:
                    await self._balance_dao.freeze(balance, now=now)
                    count += 1
                except Exception:
                    logger.exception("Failed to freeze balance %s", balance.id)
        return count

    async def activate_balances(
        self,
        balance_ids: Sequence[UUID | str | int] | None = None,
    ) -> int:
        """Activate selected balances or all frozen balances."""
        if balance_ids is not None:
            normalized_ids = _normalize_uuids(balance_ids)
            if not normalized_ids:
                return 0
            balances = await Balance.filter(id__in=normalized_ids).all()
        else:
            balances = await Balance.filter(is_frozen=True).all()

        now = datetime.now(tz=UTC)
        count = 0
        for balance in balances:
            if balance.is_frozen:
                try:
                    await self._balance_dao.activate(balance, now=now)
                    if balance.expires_at is not None:
                        await schedule_expiry_notification(
                            balance_id=str(balance.id),
                            expected_expires_at=balance.expires_at,
                        )
                    count += 1
                except Exception:
                    logger.exception("Failed to activate balance %s", balance.id)
        return count
