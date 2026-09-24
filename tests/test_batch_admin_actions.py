"""Tests for admin panel batch editing functionality."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastadmin.api.service import get_admin_model

from helios_backend.db.models.vpn.balance import Balance
from helios_backend.db.models.vpn.runtime_setting import RuntimeSetting
from helios_backend.db.models.vpn.user import User
from helios_backend.services.admin.batch_balance_service import BatchBalanceService
from helios_backend.services.admin.runtime_settings import RuntimeSettingKey
from helios_backend.web.admin.panel import BalanceModelAdmin, UserModelAdmin


@pytest.mark.anyio
async def test_batch_add_days_to_frozen_user() -> None:
    """Adding days to frozen balance should increment remaining_frozen_days."""
    user = await User.create(telegram_id=10001, username="frozen_user")
    balance = await Balance.create(
        user=user,
        remaining_frozen_days=3,
        is_frozen=True,
    )

    service = BatchBalanceService()
    updated_count = await service.add_days_to_users(days=5, user_ids=[user.id])

    assert updated_count == 1
    await balance.refresh_from_db()
    assert balance.remaining_frozen_days == 8
    assert balance.is_frozen is True


@pytest.mark.anyio
async def test_batch_add_days_to_active_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adding days to active user should extend expires_at on server."""
    now = datetime.now(tz=UTC)
    user = await User.create(
        telegram_id=10002,
        username="active_user",
        marzban_username="marz_active",
    )
    initial_expiry = now + timedelta(days=2)
    balance = await Balance.create(
        user=user,
        is_frozen=False,
        expires_at=initial_expiry,
        remaining_frozen_days=0,
    )

    mock_schedule = AsyncMock()
    monkeypatch.setattr(
        "helios_backend.services.balance.service.schedule_expiry_notification",
        mock_schedule,
    )
    monkeypatch.setattr(
        "helios_backend.services.admin.batch_balance_service.schedule_expiry_notification",
        mock_schedule,
    )

    service = BatchBalanceService()
    updated_count = await service.add_days_to_users(days=5, user_ids=[user.id])

    assert updated_count == 1
    await balance.refresh_from_db()
    assert balance.expires_at is not None
    diff = balance.expires_at - initial_expiry
    assert abs(diff.total_seconds() - 5 * 86400) < 5

    # Notification was scheduled
    mock_schedule.assert_awaited_once()


@pytest.mark.anyio
async def test_batch_add_days_to_all_users() -> None:
    """Batch add days with user_ids=None should apply to ALL users in DB."""
    u1 = await User.create(telegram_id=20001, username="u1")
    await Balance.create(user=u1, remaining_frozen_days=1, is_frozen=True)

    u2 = await User.create(telegram_id=20002, username="u2")
    await Balance.create(user=u2, remaining_frozen_days=2, is_frozen=True)

    u3 = await User.create(telegram_id=20003, username="u3")
    # u3 has no balance initially

    service = BatchBalanceService()
    total_users_before = await User.all().count()
    updated_count = await service.add_days_to_users(days=5, user_ids=None)

    assert updated_count == total_users_before

    b1 = await Balance.filter(user=u1).first()
    assert b1 is not None and b1.remaining_frozen_days == 6

    b2 = await Balance.filter(user=u2).first()
    assert b2 is not None and b2.remaining_frozen_days == 7

    b3 = await Balance.filter(user=u3).first()
    assert b3 is not None and b3.remaining_frozen_days == 5


@pytest.mark.anyio
async def test_batch_freeze_and_activate_balances() -> None:
    """Freezing and activating balances in bulk should update their status."""
    now = datetime.now(tz=UTC)
    user1 = await User.create(telegram_id=40001, username="user1")
    b1 = await Balance.create(
        user=user1,
        is_frozen=False,
        expires_at=now + timedelta(days=4),
    )

    user2 = await User.create(telegram_id=40002, username="user2")
    b2 = await Balance.create(
        user=user2,
        is_frozen=True,
        remaining_frozen_days=7,
    )

    service = BatchBalanceService()

    # Freeze b1
    frozen_count = await service.freeze_balances([b1.id])
    assert frozen_count == 1
    await b1.refresh_from_db()
    assert b1.is_frozen is True
    assert b1.remaining_frozen_days >= 3

    # Activate b2
    active_count = await service.activate_balances([b2.id])
    assert active_count == 1
    await b2.refresh_from_db()
    assert b2.is_frozen is False
    assert b2.expires_at is not None


@pytest.mark.anyio
async def test_batch_custom_days_from_runtime_settings() -> None:
    """Custom days increment should be loaded from RuntimeSetting or default to 5."""
    service = BatchBalanceService()

    # Default without explicit setting
    default_days = await service.get_custom_days_from_settings()
    assert default_days == 5

    # Update runtime setting
    await RuntimeSetting.create(
        key=RuntimeSettingKey.BATCH_BALANCE_DAYS.value,
        value=14,
    )

    custom_days = await service.get_custom_days_from_settings()
    assert custom_days == 14


@pytest.mark.anyio
async def test_fastadmin_user_model_admin_actions() -> None:
    """FastAdmin UserModelAdmin actions should execute successfully."""
    user = await User.create(telegram_id=50001, username="admin_action_user")
    balance = await Balance.create(user=user, remaining_frozen_days=0, is_frozen=True)

    admin = get_admin_model("User") or UserModelAdmin(User)

    # Add 5 days to selected
    await admin.add_5_days([user.id])
    await balance.refresh_from_db()
    assert balance.remaining_frozen_days == 5

    # Add 10 days to selected
    await admin.add_10_days([user.id])
    await balance.refresh_from_db()
    assert balance.remaining_frozen_days == 15

    # Add 30 days to selected
    await admin.add_30_days([user.id])
    await balance.refresh_from_db()
    assert balance.remaining_frozen_days == 45

    # Add 5 days to all
    await admin.add_5_days_all([user.id])
    await balance.refresh_from_db()
    assert balance.remaining_frozen_days == 50

    # Add custom days from settings to selected
    await RuntimeSetting.create(
        key=RuntimeSettingKey.BATCH_BALANCE_DAYS.value,
        value=7,
    )
    await admin.add_custom_days_settings([user.id])
    await balance.refresh_from_db()
    assert balance.remaining_frozen_days == 57


@pytest.mark.anyio
async def test_fastadmin_balance_model_admin_actions() -> None:
    """FastAdmin BalanceModelAdmin actions should execute successfully."""
    user = await User.create(telegram_id=60001, username="balance_action_user")
    balance = await Balance.create(user=user, remaining_frozen_days=2, is_frozen=True)

    admin = get_admin_model("Balance") or BalanceModelAdmin(Balance)

    # Add 5 days to balance
    await admin.add_5_days([balance.id])
    await balance.refresh_from_db()
    assert balance.remaining_frozen_days == 7

    # Add 10 days to balance
    await admin.add_10_days([balance.id])
    await balance.refresh_from_db()
    assert balance.remaining_frozen_days == 17

    # Add 30 days to balance
    await admin.add_30_days([balance.id])
    await balance.refresh_from_db()
    assert balance.remaining_frozen_days == 47

    # Add 5 days to all balances
    await admin.add_5_days_all([balance.id])
    await balance.refresh_from_db()
    assert balance.remaining_frozen_days == 52

    # Activate
    await admin.activate_subscriptions([balance.id])
    await balance.refresh_from_db()
    assert balance.is_frozen is False
    assert balance.expires_at is not None

    # Freeze
    await admin.freeze_subscriptions([balance.id])
    await balance.refresh_from_db()
    assert balance.is_frozen is True
