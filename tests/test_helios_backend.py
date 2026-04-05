from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient
from pytest import MonkeyPatch
from starlette import status

from helios_backend.db.dao.vpn.balance_dao import BalanceDao
from helios_backend.db.models.vpn.balance import Balance
from helios_backend.db.models.vpn.code import Code, CodeType
from helios_backend.db.models.vpn.subscription_plan import SubscriptionPlan
from helios_backend.db.models.vpn.user import User
from helios_backend.services.auth.jwt import JwtService
from helios_backend.services.codes.service import CodeService
from helios_backend.services.users.service import UserService


async def test_health(client: AsyncClient, fastapi_app: FastAPI) -> None:
    """
    Checks the health endpoint.

    :param client: client for the app.
    :param fastapi_app: current FastAPI application.
    """
    url = fastapi_app.url_path_for("health_check")
    response = await client.get(url)
    assert response.status_code == status.HTTP_200_OK


async def test_protected_routes_require_jwt(client: AsyncClient) -> None:
    """Ensure protected endpoints reject requests without a valid token."""
    response = await client.get("/api/plans")
    assert response.status_code in {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }


async def test_get_plans_applies_discount(client: AsyncClient) -> None:
    """Verify promo code discounts are reflected in the plans response."""
    user = await User.create(
        telegram_id=1111,
        username="u1",
        marzban_username="mz_u1",
    )
    plan = await SubscriptionPlan.create(
        name="Base",
        duration_days=30,
        price=Decimal("10.00"),
        tags={"region": "EU"},
    )
    _ = plan
    await Code.create(
        code="PROMO10",
        type=CodeType.PROMO,
        discount_percent=10,
        reward_days_percent=None,
        expires_at=datetime.now(tz=UTC) + timedelta(days=10),
        is_active=True,
    )

    token = JwtService().create_access_token(user.id)
    response = await client.get(
        "/api/plans",
        params={"code": "PROMO10"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload[0]["final_price"] == "9.00"


async def test_subscription_status_returns_local_and_marzban(
    client: AsyncClient,
) -> None:
    """Return local balance fields expected by the subscription status API."""
    user = await User.create(
        telegram_id=2222,
        username="u2",
    )
    await Balance.create(
        user=user,
        remaining_frozen_days=7,
        is_frozen=True,
    )
    token = JwtService().create_access_token(user.id)
    response = await client.get(
        "/api/subscription/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["remaining_frozen_days"] == 7
    assert data["is_frozen"] is True
    assert data["active_expires_at"] is None


async def test_balance_dao_create_marks_balance_as_frozen() -> None:
    """Create balances in frozen state with frozen-day counters initialized."""
    user = await User.create(
        telegram_id=9921,
        username="u9921",
    )

    dao = BalanceDao()
    balance = await dao.create_for_user(user, days_duration=12)

    assert balance.is_frozen is True
    assert balance.remaining_frozen_days == 12
    assert balance.frozen_at is not None
    assert balance.activated_at is None
    assert balance.expires_at is None


async def test_balance_dao_reallocates_frozen_duration_on_reactivation() -> None:
    """Reallocate remaining frozen days into a new expiration on activation."""
    user = await User.create(
        telegram_id=9922,
        username="u9922",
    )

    dao = BalanceDao()
    balance = await dao.create_for_user(user, days_duration=5)

    activated_at = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
    await dao.activate(balance, now=activated_at)

    assert balance.is_frozen is False
    assert balance.expires_at == activated_at + timedelta(days=5)

    frozen_at = activated_at + timedelta(days=2)
    await dao.freeze(balance, now=frozen_at)

    assert balance.is_frozen is True
    assert balance.frozen_at == frozen_at
    assert balance.expires_at is None
    assert balance.remaining_frozen_days == 3

    reactivated_at = frozen_at + timedelta(days=4)
    await dao.activate(balance, now=reactivated_at)

    assert balance.is_frozen is False
    assert balance.activated_at == reactivated_at
    assert balance.expires_at == reactivated_at + timedelta(days=3)


async def test_balance_freeze_rounds_down_below_half_day() -> None:
    """Round down frozen-day carryover when remainder is below half a day."""
    user = await User.create(
        telegram_id=9923,
        username="u9923",
    )
    dao = BalanceDao()
    balance = await dao.create_for_user(user, days_duration=3)

    activated_at = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
    await dao.activate(balance, now=activated_at)

    # 2 days and 11 hours remaining -> 2 frozen days with half-day threshold.
    freeze_at = activated_at + timedelta(hours=13)
    await dao.freeze(balance, now=freeze_at)

    assert balance.is_frozen is True
    assert balance.remaining_frozen_days == 2


async def test_balance_freeze_rounds_up_at_half_day() -> None:
    """Round up frozen-day carryover when remainder reaches half a day."""
    user = await User.create(
        telegram_id=9924,
        username="u9924",
    )
    dao = BalanceDao()
    balance = await dao.create_for_user(user, days_duration=3)

    activated_at = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
    await dao.activate(balance, now=activated_at)

    # 2 days and 12 hours remaining -> 3 frozen days with half-day threshold.
    freeze_at = activated_at + timedelta(hours=12)
    await dao.freeze(balance, now=freeze_at)

    assert balance.is_frozen is True
    assert balance.remaining_frozen_days == 3


async def test_subscription_url_endpoint(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    """Return a subscription URL for an authenticated user."""
    user = await User.create(
        telegram_id=3333,
        username="u3",
    )
    await Balance.create(user=user, remaining_frozen_days=5, is_frozen=True)
    token = JwtService().create_access_token(user.id)

    async def fake_create_user(
        self: object,
        username: str,
        expires_at: datetime,
    ) -> None:
        _ = username
        _ = expires_at

    async def fake_get_subscription_url(self: object, username: str) -> str | None:
        _ = username
        return "https://sub.example.com/sub/token123"

    from helios_backend.services.marzban.service import MarzbanService

    monkeypatch.setattr(MarzbanService, "create_user", fake_create_user)
    monkeypatch.setattr(
        MarzbanService, "get_subscription_url", fake_get_subscription_url
    )
    response = await client.get(
        "/api/subscription/url",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "subscription_url": "https://sub.example.com/sub/token123",
    }


async def test_subscription_url_creates_marzban_user_and_sets_username(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    """Provision Marzban user and persist generated username on first request."""
    user = await User.create(
        telegram_id=3344,
        username="u3344",
    )
    await Balance.create(user=user, remaining_frozen_days=2, is_frozen=True)

    calls: list[tuple[str, datetime]] = []

    async def fake_create_user(
        self: object,
        username: str,
        expires_at: datetime,
    ) -> None:
        _ = self
        calls.append((username, expires_at))

    async def fake_get_subscription_url(self: object, username: str) -> str | None:
        _ = self
        return f"https://sub.example.com/sub/{username}"

    from helios_backend.services.marzban.service import MarzbanService

    monkeypatch.setattr(MarzbanService, "create_user", fake_create_user)
    monkeypatch.setattr(
        MarzbanService, "get_subscription_url", fake_get_subscription_url
    )

    response = await client.get(
        "/api/subscription/url",
        headers={
            "Authorization": f"Bearer {JwtService().create_access_token(user.id)}"
        },
    )

    assert response.status_code == status.HTTP_200_OK
    updated_user = await User.filter(id=user.id).first()
    assert updated_user is not None
    assert updated_user.marzban_username is not None
    assert response.json() == {
        "subscription_url": f"https://sub.example.com/sub/{updated_user.marzban_username}",
    }
    assert len(calls) == 1
    assert calls[0][0] == updated_user.marzban_username


async def test_code_can_be_used_only_once_per_user_in_payment_creation(
    client: AsyncClient,
) -> None:
    """Allow one code use per user while permitting use by different users."""
    user1 = await User.create(
        telegram_id=4444,
        username="u4",
    )
    user2 = await User.create(
        telegram_id=5555,
        username="u5",
    )
    plan = await SubscriptionPlan.create(
        name="SingleUsePlan",
        duration_days=30,
        price=Decimal("15.00"),
        tags={},
    )
    await Code.create(
        code="ONETIME",
        type=CodeType.PROMO,
        discount_percent=10,
        reward_days_percent=None,
        expires_at=datetime.now(tz=UTC) + timedelta(days=10),
        is_active=True,
    )

    headers_user1 = {
        "Authorization": f"Bearer {JwtService().create_access_token(user1.id)}"
    }
    headers_user2 = {
        "Authorization": f"Bearer {JwtService().create_access_token(user2.id)}"
    }

    first = await client.post(
        "/api/payments/create",
        json={"plan_id": str(plan.id), "provider": "dummy", "code": "ONETIME"},
        headers=headers_user1,
    )
    assert first.status_code == status.HTTP_200_OK

    first_webhook = await client.post(
        "/api/payments/webhook/dummy",
        json={"external_id": first.json()["external_id"], "status": "paid"},
    )
    assert first_webhook.status_code == status.HTTP_200_OK

    second = await client.post(
        "/api/payments/create",
        json={"plan_id": str(plan.id), "provider": "dummy", "code": "ONETIME"},
        headers=headers_user1,
    )
    assert second.status_code == status.HTTP_400_BAD_REQUEST
    assert second.json()["detail"] == "invalid or already used code"

    third = await client.post(
        "/api/payments/create",
        json={"plan_id": str(plan.id), "provider": "dummy", "code": "ONETIME"},
        headers=headers_user2,
    )
    assert third.status_code == status.HTTP_200_OK


async def test_zero_amount_payment_is_auto_paid_without_provider_call(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    """Auto-complete zero-amount payments without invoking payment providers."""
    user = await User.create(
        telegram_id=8888,
        username="u8",
    )
    plan = await SubscriptionPlan.create(
        name="FreeByPromo",
        duration_days=30,
        price=Decimal("10.00"),
        tags={},
    )
    await Code.create(
        code="FREE100",
        type=CodeType.PROMO,
        discount_percent=100,
        reward_days_percent=None,
        expires_at=datetime.now(tz=UTC) + timedelta(days=10),
        is_active=True,
    )

    from helios_backend.services.payments.dummy_provider import DummyProvider

    async def fail_if_called(self: object, payment: Any) -> Any:
        _ = self
        _ = payment
        msg = "provider create_payment should not be called for zero-amount payments"
        raise AssertionError(msg)

    monkeypatch.setattr(DummyProvider, "create_payment", fail_if_called)

    response = await client.post(
        "/api/payments/create",
        json={"plan_id": str(plan.id), "provider": "dummy", "code": "FREE100"},
        headers={
            "Authorization": f"Bearer {JwtService().create_access_token(user.id)}"
        },
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["status"] == "paid"
    assert payload["checkout_url"] == ""


async def test_registration_creates_base_pending_subscription() -> None:
    """Create initial frozen base balance and referral code on registration."""
    user = await UserService().get_or_create_telegram_user(
        telegram_id=6666, username="u6"
    )
    balance = await Balance.filter(user=user).first()
    referral_code = await Code.filter(owner_id=user.id, type=CodeType.REFERRAL).first()

    assert balance is not None
    assert balance.remaining_frozen_days == 3
    assert balance.is_frozen is True
    assert balance.activated_at is None
    assert balance.expires_at is None
    assert referral_code is not None


async def test_subscription_url_activates_frozen_balance(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    """Activate a frozen balance when subscription URL is requested."""
    user = await User.create(telegram_id=7777, username="u7")
    await Balance.create(
        user=user,
        remaining_frozen_days=5,
        is_frozen=True,
    )

    async def fake_create_user(
        self: object,
        username: str,
        expires_at: datetime,
    ) -> None:
        _ = username
        _ = expires_at

    async def fake_get_subscription_url(self: object, username: str) -> str | None:
        _ = username
        return "https://sub.example.com/sub/activated"

    from helios_backend.services.marzban.service import MarzbanService

    monkeypatch.setattr(MarzbanService, "create_user", fake_create_user)
    monkeypatch.setattr(
        MarzbanService, "get_subscription_url", fake_get_subscription_url
    )

    response = await client.get(
        "/api/subscription/url",
        headers={
            "Authorization": f"Bearer {JwtService().create_access_token(user.id)}"
        },
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "subscription_url": "https://sub.example.com/sub/activated"
    }

    updated = await Balance.filter(user=user).first()
    assert updated is not None
    assert updated.is_frozen is False


async def test_get_or_create_referral_code_is_stable_for_same_user() -> None:
    """Return the same referral code when called repeatedly for one user."""
    user = await User.create(telegram_id=9991, username="ref_u1")
    service = CodeService()

    first = await service.get_or_create_user_referral_code(user)
    second = await service.get_or_create_user_referral_code(user)

    assert first.id == second.id
    assert first.code == second.code
    assert len(first.code) == 6
    assert first.code.isdigit()
    assert first.type == CodeType.REFERRAL
    assert first.owner_id == user.id


async def test_get_or_create_referral_code_is_unique_between_users() -> None:
    """Generate distinct referral codes for different users."""
    user1 = await User.create(telegram_id=9992, username="ref_u2")
    user2 = await User.create(telegram_id=9993, username="ref_u3")
    service = CodeService()

    code1 = await service.get_or_create_user_referral_code(user1)
    code2 = await service.get_or_create_user_referral_code(user2)

    assert code1.code != code2.code
    assert len(code1.code) == 6
    assert len(code2.code) == 6
    assert code1.owner_id == user1.id
    assert code2.owner_id == user2.id


async def test_delete_user_removes_referral_code_from_db() -> None:
    """Delete a user's referral code when the user is removed."""
    user = await User.create(telegram_id=9994, username="ref_u4")
    code_service = CodeService()
    user_service = UserService()

    created_code = await code_service.get_or_create_user_referral_code(user)
    assert await Code.filter(id=created_code.id).exists() is True

    await user_service.delete_user(user)

    assert await Code.filter(id=created_code.id).exists() is False


async def test_get_referral_usages_by_user_returns_only_owner_referral_usages() -> None:
    """Return only usages tied to referral codes owned by the queried user."""
    owner = await User.create(telegram_id=9995, username="ref_owner")
    other_owner = await User.create(telegram_id=9996, username="other_owner")
    consumer = await User.create(telegram_id=9997, username="consumer")
    service = CodeService()

    owner_ref = await service.get_or_create_user_referral_code(owner)
    other_ref = await service.get_or_create_user_referral_code(other_owner)

    await service.consume(owner_ref, consumer.id)
    await service.consume(other_ref, consumer.id)

    usages = await service.get_referral_usages_by_user(owner.id)

    assert len(usages) == 1
    assert usages[0].code_id == owner_ref.id
    assert usages[0].user_id == consumer.id
