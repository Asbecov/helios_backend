from datetime import UTC, datetime, timedelta

from pytest import MonkeyPatch

from helios_backend.db.dao.vpn.balance_dao import BalanceDao
from helios_backend.db.models.vpn.balance import Balance
from helios_backend.db.models.vpn.user import User
from helios_backend.services.notifications.service import TelegramNotifierService
from helios_backend.tasks.notifications import notify_unactivated_subscriptions_daily


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
