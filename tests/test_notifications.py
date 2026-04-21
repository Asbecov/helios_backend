from datetime import UTC, datetime, timedelta

from fakeredis.aioredis import FakeRedis
from pytest import MonkeyPatch

from helios_backend.db.dao.vpn.balance_dao import BalanceDao
from helios_backend.db.models.vpn.balance import Balance
from helios_backend.db.models.vpn.user import User
from helios_backend.services.notifications.service import TelegramNotifierService
from helios_backend.tasks.notifications import (
    notify_subscription_expired_once,
    notify_unactivated_subscriptions_daily,
    rehydrate_expiry_notifications,
)


async def test_get_frozen_with_remaining_days_filters_balances() -> None:
    """Return only frozen balances with positive remaining day counter."""
    user_with_days = await User.create(telegram_id=8101, username="u8101")
    user_without_days = await User.create(telegram_id=8102, username="u8102")
    user_active = await User.create(telegram_id=8103, username="u8103")

    await Balance.create(
        user=user_with_days,
        remaining_frozen_days=5,
        is_frozen=True,
    )
    await Balance.create(
        user=user_without_days,
        remaining_frozen_days=0,
        is_frozen=True,
    )
    await Balance.create(
        user=user_active,
        remaining_frozen_days=0,
        is_frozen=False,
        activated_at=datetime.now(tz=UTC),
        expires_at=datetime.now(tz=UTC) + timedelta(days=7),
    )

    balances = await BalanceDao().get_frozen_with_remaining_days()
    assert len(balances) == 1
    assert balances[0].user is not None
    assert balances[0].user.telegram_id == 8101


async def test_notify_unactivated_balances_sends_messages(
    monkeypatch: MonkeyPatch,
) -> None:
    """Send notifications only to users with frozen balances and remaining days."""
    first = await User.create(telegram_id=8111, username="u8111")
    second = await User.create(telegram_id=8112, username="u8112")
    active = await User.create(telegram_id=8113, username="u8113")

    await Balance.create(user=first, remaining_frozen_days=3, is_frozen=True)
    await Balance.create(user=second, remaining_frozen_days=1, is_frozen=True)
    await Balance.create(
        user=active,
        remaining_frozen_days=0,
        is_frozen=False,
        activated_at=datetime.now(tz=UTC),
        expires_at=datetime.now(tz=UTC) + timedelta(days=3),
    )

    sent_to: list[int] = []

    async def fake_notify_user(self: object, telegram_id: int, text: str) -> None:
        _ = self
        _ = text
        sent_to.append(telegram_id)

    monkeypatch.setattr(TelegramNotifierService, "notify_user", fake_notify_user)

    result = await TelegramNotifierService().notify_unactivated_balances()

    assert result["frozen_with_remaining_days"] == 2
    assert set(sent_to) == {8111, 8112}


async def test_notify_subscription_expired_once_sends_only_once(
    monkeypatch: MonkeyPatch,
) -> None:
    """Send expiration message once and skip duplicates for same expiry."""
    user = await User.create(telegram_id=8121, username="u8121")
    expires_at = datetime.now(tz=UTC) - timedelta(minutes=2)
    balance = await Balance.create(
        user=user,
        is_frozen=False,
        remaining_frozen_days=0,
        activated_at=expires_at - timedelta(days=1),
        expires_at=expires_at,
    )

    sent_to: list[int] = []

    async def fake_notify_user(self: object, telegram_id: int, text: str) -> None:
        _ = self
        _ = text
        sent_to.append(telegram_id)

    monkeypatch.setattr(TelegramNotifierService, "notify_user", fake_notify_user)

    redis = FakeRedis()
    notifier = TelegramNotifierService(redis_client=redis)
    first = await notifier.notify_subscription_expired_once(
        balance_id=str(balance.id),
        expected_expires_at=expires_at.isoformat(),
    )
    second = await notifier.notify_subscription_expired_once(
        balance_id=str(balance.id),
        expected_expires_at=expires_at.isoformat(),
    )

    assert first is True
    assert second is False
    assert sent_to == [8121]
    await redis.aclose()


async def test_notify_subscription_expired_once_skips_stale_schedule(
    monkeypatch: MonkeyPatch,
) -> None:
    """Skip one-shot task when expected expiry does not match current balance."""
    user = await User.create(telegram_id=8122, username="u8122")
    expires_at = datetime.now(tz=UTC) + timedelta(hours=5)
    balance = await Balance.create(
        user=user,
        is_frozen=False,
        remaining_frozen_days=0,
        activated_at=datetime.now(tz=UTC),
        expires_at=expires_at,
    )

    sent_to: list[int] = []

    async def fake_notify_user(self: object, telegram_id: int, text: str) -> None:
        _ = self
        _ = text
        sent_to.append(telegram_id)

    monkeypatch.setattr(TelegramNotifierService, "notify_user", fake_notify_user)

    redis = FakeRedis()
    notifier = TelegramNotifierService(redis_client=redis)
    result = await notifier.notify_subscription_expired_once(
        balance_id=str(balance.id),
        expected_expires_at=(expires_at + timedelta(minutes=1)).isoformat(),
    )

    assert result is False
    assert sent_to == []
    await redis.aclose()


async def test_schedule_expiry_notifications_for_existing_balances() -> None:
    """Schedule notifications for active balances, including immediate catch-up."""
    now = datetime.now(tz=UTC)
    user_future = await User.create(telegram_id=8123, username="u8123")
    user_expired = await User.create(telegram_id=8124, username="u8124")
    user_frozen = await User.create(telegram_id=8125, username="u8125")

    future_balance = await Balance.create(
        user=user_future,
        is_frozen=False,
        remaining_frozen_days=0,
        activated_at=now - timedelta(days=1),
        expires_at=now + timedelta(hours=6),
    )
    expired_balance = await Balance.create(
        user=user_expired,
        is_frozen=False,
        remaining_frozen_days=0,
        activated_at=now - timedelta(days=2),
        expires_at=now - timedelta(minutes=5),
    )
    await Balance.create(
        user=user_frozen,
        is_frozen=True,
        remaining_frozen_days=3,
    )

    scheduled_calls: list[tuple[str, datetime, datetime | None]] = []

    async def fake_schedule_expiry_notification(
        balance_id: str,
        expected_expires_at: datetime,
        run_at: datetime | None = None,
    ) -> str:
        scheduled_calls.append((balance_id, expected_expires_at, run_at))
        return "scheduled"

    result = await TelegramNotifierService(
        schedule_expiry_notification=fake_schedule_expiry_notification,
    ).schedule_expiry_notifications_for_existing_balances()

    assert result == {"scheduled": 2, "immediate": 1}
    assert len(scheduled_calls) == 2

    by_balance = {call[0]: call for call in scheduled_calls}
    assert str(future_balance.id) in by_balance
    assert str(expired_balance.id) in by_balance

    assert (
        by_balance[str(future_balance.id)][2] == by_balance[str(future_balance.id)][1]
    )
    expired_run_at = by_balance[str(expired_balance.id)][2]
    assert expired_run_at is not None
    assert expired_run_at >= now


async def test_daily_unactivated_task_returns_service_payload(
    monkeypatch: MonkeyPatch,
) -> None:
    """Proxy task returns notifier summary as-is."""

    async def fake_notify_unactivated(self: object) -> dict[str, int]:
        _ = self
        return {"frozen_with_remaining_days": 4}

    monkeypatch.setattr(
        TelegramNotifierService,
        "notify_unactivated_balances",
        fake_notify_unactivated,
    )

    result = await notify_unactivated_subscriptions_daily()
    assert result == {"frozen_with_remaining_days": 4}


async def test_one_shot_expiry_task_returns_status(
    monkeypatch: MonkeyPatch,
) -> None:
    """One-shot task should proxy notifier result into status payload."""

    async def fake_notify_expired(
        self: object,
        balance_id: str,
        expected_expires_at: str,
    ) -> bool:
        _ = self
        _ = balance_id
        _ = expected_expires_at
        return True

    monkeypatch.setattr(
        TelegramNotifierService,
        "notify_subscription_expired_once",
        fake_notify_expired,
    )

    result = await notify_subscription_expired_once(
        balance_id="balance-1",
        expected_expires_at="2026-01-01T00:00:00+00:00",
    )
    assert result == {
        "balance_id": "balance-1",
        "status": "sent",
    }


async def test_rehydrate_task_returns_service_payload(
    monkeypatch: MonkeyPatch,
) -> None:
    """Rehydration task should return notifier summary as-is."""

    async def fake_schedule_existing(self: object) -> dict[str, int]:
        _ = self
        return {"scheduled": 9, "immediate": 2}

    monkeypatch.setattr(
        TelegramNotifierService,
        "schedule_expiry_notifications_for_existing_balances",
        fake_schedule_existing,
    )

    result = await rehydrate_expiry_notifications()
    assert result == {"scheduled": 9, "immediate": 2}
