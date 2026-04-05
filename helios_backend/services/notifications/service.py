from datetime import UTC, datetime, timedelta

import httpx

from helios_backend.db.dao.vpn.balance_dao import BalanceDao
from helios_backend.settings import settings


class TelegramNotifierService:
    """Sends Telegram notifications for subscription lifecycle events."""

    def __init__(self, balance_dao: BalanceDao | None = None) -> None:
        """Initialize telegram notifier service."""
        self._balance_dao = balance_dao or BalanceDao()

    async def notify_user(self, telegram_id: int, text: str) -> None:
        """Handle notify user."""
        if not settings.telegram_bot_token:
            return
        endpoint = (
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        )
        payload = {"chat_id": telegram_id, "text": text}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(endpoint, json=payload)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                msg = f"telegram notification failed for chat_id={telegram_id}"
                raise RuntimeError(msg) from exc

    async def notify_expiring_subscriptions(self) -> dict[str, int]:
        """Handle notify expiring subscriptions."""
        now = datetime.now(tz=UTC)
        day3_start = now + timedelta(days=3)
        day3_end = day3_start + timedelta(hours=24)
        day1_start = now + timedelta(days=1)
        day1_end = day1_start + timedelta(hours=24)

        expiring_3d = await self._balance_dao.get_expiring_active_between(
            day3_start, day3_end
        )
        expiring_1d = await self._balance_dao.get_expiring_active_between(
            day1_start, day1_end
        )
        expired = await self._balance_dao.get_expired_active_before(now)

        for balance in expiring_3d:
            if balance.user is None:
                continue
            await self.notify_user(
                balance.user.telegram_id,
                "Your VPN subscription expires in 3 days.",
            )
        for balance in expiring_1d:
            if balance.user is None:
                continue
            await self.notify_user(
                balance.user.telegram_id,
                "Your VPN subscription expires in 1 day.",
            )
        for balance in expired:
            if balance.user is None:
                continue
            await self.notify_user(
                balance.user.telegram_id,
                "Your VPN subscription has expired.",
            )

        return {
            "expiring_3d": len(expiring_3d),
            "expiring_1d": len(expiring_1d),
            "expired": len(expired),
        }
