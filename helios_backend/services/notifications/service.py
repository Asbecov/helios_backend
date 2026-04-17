from datetime import UTC, datetime, timedelta

from aiogram.exceptions import TelegramAPIError

from helios_backend.db.dao.vpn.balance_dao import BalanceDao
from helios_backend.services.notifications.bot_client import get_shared_bot
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
        bot = await get_shared_bot()
        if bot is None:
            return
        try:
            await bot.send_message(chat_id=telegram_id, text=text)
        except TelegramAPIError as exc:
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
                "😥 Напоминаем: подписка истекает через 3 дня!",
            )
        for balance in expiring_1d:
            if balance.user is None:
                continue
            await self.notify_user(
                balance.user.telegram_id,
                "😥 Напоминаем: подписка истекает через 1 день!",
            )
        for balance in expired:
            if balance.user is None:
                continue
            await self.notify_user(
                balance.user.telegram_id,
                "❗ Ваша подписка истекла.",
            )

        return {
            "expiring_3d": len(expiring_3d),
            "expiring_1d": len(expiring_1d),
            "expired": len(expired),
        }

    async def notify_unactivated_balances(self) -> dict[str, int]:
        """Handle daily reminders for frozen balances with remaining days."""
        frozen_balances = await self._balance_dao.get_frozen_with_remaining_days()

        for balance in frozen_balances:
            if balance.user is None:
                continue
            await self.notify_user(
                balance.user.telegram_id,
                (
                    "👋 У вас есть неактивный баланс с оставшимися днями. "  # noqa: RUF001
                    "Нажмите 🚀 Подключиться чтобы активировать баланс и начать пользоваться сервисом!"  # noqa: E501
                ),
            )

        return {
            "frozen_with_remaining_days": len(frozen_balances),
        }
