import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from redis.asyncio import Redis

from helios_backend.bot.callbacks import OPEN_BUY_CALLBACK
from helios_backend.db.dao.vpn.balance_dao import BalanceDao
from helios_backend.services.notifications.bot_client import get_shared_bot
from helios_backend.settings import settings

ScheduleExpiryNotificationFn = Callable[
    [str, datetime, datetime | None],
    Awaitable[str | None],
]

logger = logging.getLogger(__name__)


class TelegramNotifierService:
    """Sends Telegram notifications for subscription lifecycle events."""

    _EXPIRY_LOCK_TTL_SECONDS = 300
    _EXPIRY_SENT_TTL_SECONDS = 60 * 60 * 24 * 180
    _EXPIRY_REDIS_DB_PATH = "/1"
    _BUY_BUTTON_TEXT = "💠 Купить подписку"

    def __init__(
        self,
        balance_dao: BalanceDao | None = None,
        redis_client: Redis | None = None,
        schedule_expiry_notification: ScheduleExpiryNotificationFn | None = None,
    ) -> None:
        """Initialize telegram notifier service."""
        self._balance_dao = balance_dao or BalanceDao()
        self._redis_client = redis_client
        self._redis_url = str(settings.redis_url.with_path(self._EXPIRY_REDIS_DB_PATH))
        self._schedule_expiry_notification = schedule_expiry_notification

    @staticmethod
    def _normalize_utc(value: datetime) -> datetime:
        """Normalize datetime value to UTC-aware representation."""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _parse_expected_expires_at(raw_value: str) -> datetime | None:
        """Parse expected expiry string and normalize to UTC."""
        try:
            parsed = datetime.fromisoformat(raw_value)
        except ValueError:
            return None
        return TelegramNotifierService._normalize_utc(parsed)

    @staticmethod
    def _to_expiry_timestamp(expires_at: datetime) -> int:
        """Convert expiry datetime to second-precision timestamp."""
        return int(TelegramNotifierService._normalize_utc(expires_at).timestamp())

    def _build_expiry_lock_key(self, balance_id: str, expires_at: datetime) -> str:
        """Build short-lived lock key for a specific expiry notification."""
        expires_ts = self._to_expiry_timestamp(expires_at)
        return f"notifications:subscription_expired:lock:{balance_id}:{expires_ts}"

    def _build_expiry_sent_key(self, balance_id: str, expires_at: datetime) -> str:
        """Build dedupe key proving expiry notification has been sent."""
        expires_ts = self._to_expiry_timestamp(expires_at)
        return f"notifications:subscription_expired:sent:{balance_id}:{expires_ts}"

    @classmethod
    def _build_buy_subscription_markup(cls) -> InlineKeyboardMarkup:
        """Build CTA button that opens buy route in bot callback flow."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=cls._BUY_BUTTON_TEXT,
                        callback_data=OPEN_BUY_CALLBACK,
                    )
                ]
            ]
        )

    async def notify_user(
        self,
        telegram_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> bool:
        """Handle notify user."""
        if not settings.telegram_bot_token:
            return False
        bot = await get_shared_bot()
        if bot is None:
            return False
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=text,
                reply_markup=reply_markup,
            )
            return True
        except TelegramForbiddenError:
            logger.info(
                "Skipping telegram notification for chat_id=%s: bot was blocked by the user",  # noqa: E501
                telegram_id,
            )
            return False
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
        buy_markup = self._build_buy_subscription_markup()

        for balance in expiring_3d:
            if balance.user is None:
                continue
            await self.notify_user(
                balance.user.telegram_id,
                "⚠️ Срочно! \n\n"
                "Ваша подписка истекает через три дня.\n\n"
                "Чтобы продолжить пользоваться сервисом, приобретите подписку.\n"
                "Все актуальные промокоды смотрите в нашем канале - @vpn_helios",  # noqa: RUF001
                reply_markup=buy_markup,
            )
        for balance in expiring_1d:
            if balance.user is None:
                continue
            await self.notify_user(
                balance.user.telegram_id,
                "⚠️ Срочно! \n\n"
                "Ваша подписка истекает завтра.\n\n"
                "Чтобы продолжить пользоваться сервисом, приобретите подписку.\n"
                "Все актуальные промокоды смотрите в нашем канале - @vpn_helios",  # noqa: RUF001
                reply_markup=buy_markup,
            )
        for balance in expired:
            if balance.user is None:
                continue
            await self.notify_user(
                balance.user.telegram_id,
                "⚠️ Срочно! \n\n"
                "Ваша подписка истекла.\n\n"
                "Чтобы продолжить пользоваться сервисом, приобретите подписку.\n"
                "Все актуальные промокоды смотрите в нашем канале - @vpn_helios",  # noqa: RUF001
                reply_markup=buy_markup,
            )

        return {
            "expiring_3d": len(expiring_3d),
            "expiring_1d": len(expiring_1d),
            "expired": len(expired),
        }

    async def notify_subscription_expired_once(
        self,
        balance_id: str,
        expected_expires_at: str,
    ) -> bool:
        """Send single expiry notification with dedupe and stale guards."""
        notification_context = await self._resolve_expiry_notification_context(
            balance_id=balance_id,
            expected_expires_at=expected_expires_at,
        )
        if notification_context is None:
            return False

        scoped_balance_id, expires_at, telegram_id = notification_context
        return await self._send_expiry_notification_once(
            balance_id=scoped_balance_id,
            expires_at=expires_at,
            telegram_id=telegram_id,
        )

    async def _resolve_expiry_notification_context(
        self,
        balance_id: str,
        expected_expires_at: str,
    ) -> tuple[str, datetime, int] | None:
        """Validate payload and current balance state for one-shot expiry message."""
        parsed_expected = self._parse_expected_expires_at(expected_expires_at)
        parsed_balance_id: UUID | None = None
        try:
            parsed_balance_id = UUID(balance_id)
        except ValueError:
            parsed_balance_id = None

        context: tuple[str, datetime, int] | None = None
        if parsed_expected is not None and parsed_balance_id is not None:
            balance = await self._balance_dao.get_by_id_with_user(parsed_balance_id)
            if (
                balance is not None
                and balance.user is not None
                and balance.is_frozen is False
                and balance.expires_at is not None
            ):
                current_expires_at = self._normalize_utc(balance.expires_at)
                if (
                    current_expires_at == parsed_expected
                    and datetime.now(tz=UTC) >= current_expires_at
                ):
                    context = (
                        str(balance.id),
                        current_expires_at,
                        balance.user.telegram_id,
                    )
        return context

    async def _send_expiry_notification_once(
        self,
        balance_id: str,
        expires_at: datetime,
        telegram_id: int,
    ) -> bool:
        """Send and dedupe expiry notification for specific balance expiry version."""
        lock_key = self._build_expiry_lock_key(balance_id, expires_at)
        sent_key = self._build_expiry_sent_key(balance_id, expires_at)

        redis = self._redis_client or Redis.from_url(self._redis_url)
        close_redis = self._redis_client is None
        lock_acquired = False
        sent = False
        try:
            already_sent = bool(await redis.exists(sent_key))
            if not already_sent:
                lock_acquired = bool(
                    await redis.set(
                        lock_key,
                        "1",
                        ex=self._EXPIRY_LOCK_TTL_SECONDS,
                        nx=True,
                    )
                )
                if lock_acquired and not await redis.exists(sent_key):
                    delivered = await self.notify_user(
                        telegram_id,
                        "⚠️ Срочно! \n\n"
                        "Ваша подписка истекла.\n\n"
                        "Чтобы продолжить пользоваться сервисом, приобретите подписку.\n"  # noqa: E501
                        "Все актуальные промокоды смотрите в нашем канале - @vpn_helios",  # noqa: E501, RUF001
                        reply_markup=self._build_buy_subscription_markup(),
                    )
                    if delivered:
                        await redis.set(
                            sent_key,
                            "1",
                            ex=self._EXPIRY_SENT_TTL_SECONDS,
                        )
                        sent = True
        finally:
            if lock_acquired:
                await redis.delete(lock_key)
            if close_redis:
                await redis.aclose()
        return sent

    async def schedule_expiry_notifications_for_existing_balances(
        self,
    ) -> dict[str, int]:
        """Schedule one-shot expiry notifications for all active balances."""
        if self._schedule_expiry_notification is None:
            return {
                "scheduled": 0,
                "immediate": 0,
            }

        now = datetime.now(tz=UTC)
        balances = await self._balance_dao.get_active_with_expiry()

        scheduled = 0
        immediate = 0
        for balance in balances:
            expires_at = balance.expires_at
            if expires_at is None:
                continue

            normalized_expires_at = self._normalize_utc(expires_at)
            run_at = normalized_expires_at if normalized_expires_at > now else now

            schedule_id = await self._schedule_expiry_notification(
                str(balance.id),
                normalized_expires_at,
                run_at,
            )
            if schedule_id is None:
                continue

            scheduled += 1
            if normalized_expires_at <= now:
                immediate += 1

        return {
            "scheduled": scheduled,
            "immediate": immediate,
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
