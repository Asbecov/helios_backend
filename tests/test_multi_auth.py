import hmac
import hashlib
from datetime import UTC, datetime
from httpx import AsyncClient
import pytest
from starlette import status

from helios_backend.db.models.vpn.balance import Balance
from helios_backend.db.models.vpn.payment import Payment, PaymentStatus
from helios_backend.db.models.vpn.subscription_plan import SubscriptionPlan
from helios_backend.db.models.vpn.user import User
from helios_backend.services.auth.google import GoogleUserData, GoogleAuthService
from helios_backend.services.auth.jwt import JwtService
from helios_backend.services.users.service import UserService
from helios_backend.settings import settings


@pytest.mark.anyio
async def test_google_auth_and_base_plan_grant(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Google OAuth login creates user, grants base plan trial, and returns tokens."""
    base_plan = await SubscriptionPlan.create(
        name=settings.base_plan_name,
        duration_days=settings.base_plan_duration_days,
        price=0,
        is_base=True,
        tags=[],
    )

    async def mock_validate(self: GoogleAuthService, id_token: str) -> GoogleUserData:
        return GoogleUserData(
            sub="google_sub_12345",
            email="user@gmail.com",
            name="Google User",
        )

    monkeypatch.setattr(GoogleAuthService, "validate_id_token", mock_validate)

    response = await client.post(
        "/api/auth/google",
        json={"id_token": "valid_mock_google_id_token"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

    # Verify user created in DB
    user = await User.filter(google_sub="google_sub_12345").first()
    assert user is not None
    assert user.google_email == "user@gmail.com"

    # Verify base plan applied
    balance = await Balance.filter(user=user).first()
    assert balance is not None
    assert balance.remaining_frozen_days == settings.base_plan_duration_days


@pytest.mark.anyio
async def test_refresh_token_endpoint(client: AsyncClient) -> None:
    """Test refreshing an access token using a valid refresh token."""
    user = await User.create(google_sub="refresh_user_sub", google_email="ref@test.com")
    jwt_svc = JwtService()
    ref_token = jwt_svc.create_refresh_token(user.id)

    response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": ref_token},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

    new_user_id = jwt_svc.decode_access_token(data["access_token"])
    assert new_user_id == user.id


@pytest.mark.anyio
async def test_link_new_telegram_identity_to_google_user(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test linking a new Telegram identity to an existing Google user (status='linked')."""
    user = await User.create(google_sub="google_sub_link_1", google_email="link1@test.com")
    jwt_svc = JwtService()
    acc_token = jwt_svc.create_access_token(user.id)

    # Mock widget data validation
    bot_token = "123456:test_bot_token"
    monkeypatch.setattr(settings, "telegram_bot_token", bot_token)

    auth_date = str(int(datetime.now(tz=UTC).timestamp()))
    widget_dict = {
        "id": "777888999",
        "username": "tg_linked_user",
        "auth_date": auth_date,
    }
    data_check = f"auth_date={auth_date}\nid=777888999\nusername=tg_linked_user"
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    widget_dict["hash"] = hmac.new(
        key=secret_key,
        msg=data_check.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    response = await client.post(
        "/api/auth/link/telegram",
        headers={"Authorization": f"Bearer {acc_token}"},
        json={"widget_data": widget_dict},
    )
    assert response.status_code == status.HTTP_200_OK
    res_data = response.json()
    assert res_data["status"] == "linked"
    assert res_data["user"]["telegram_id"] == 777888999
    assert res_data["user"]["google_sub"] == "google_sub_link_1"

    # Reload from DB
    reloaded = await User.get(id=user.id)
    assert reloaded.telegram_id == 777888999


@pytest.mark.anyio
async def test_auto_merge_existing_telegram_account_into_google_account(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test auto-merging an existing Telegram user into Google user when Telegram proof is provided."""
    # Create Google User A with 5 frozen days balance
    user_a = await User.create(google_sub="google_sub_target", google_email="target@gmail.com")
    await Balance.create(user=user_a, remaining_frozen_days=5, is_frozen=True)

    # Create Telegram User B with 10 frozen days balance and a payment
    user_b = await User.create(telegram_id=999111, username="tg_source_user")
    await Balance.create(user=user_b, remaining_frozen_days=10, is_frozen=True)

    plan = await SubscriptionPlan.create(
        name="Plan 1",
        duration_days=30,
        price=100,
        tags=[],
    )
    payment = await Payment.create(
        user=user_b,
        plan=plan,
        amount=100,
        status=PaymentStatus.PAID,
        provider="yookassa",
        external_id="ext_pay_999",
    )

    jwt_svc = JwtService()
    acc_token_a = jwt_svc.create_access_token(user_a.id)

    bot_token = "123456:test_bot_token"
    monkeypatch.setattr(settings, "telegram_bot_token", bot_token)

    auth_date = str(int(datetime.now(tz=UTC).timestamp()))
    widget_dict = {
        "id": "999111",
        "username": "tg_source_user",
        "auth_date": auth_date,
    }
    data_check = f"auth_date={auth_date}\nid=999111\nusername=tg_source_user"
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    widget_dict["hash"] = hmac.new(
        key=secret_key,
        msg=data_check.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    # User A links Telegram User B -> auto merges
    response = await client.post(
        "/api/auth/link/telegram",
        headers={"Authorization": f"Bearer {acc_token_a}"},
        json={"widget_data": widget_dict},
    )
    assert response.status_code == status.HTTP_200_OK
    res_data = response.json()
    assert res_data["status"] == "merged"
    assert res_data["user"]["id"] == str(user_a.id)
    assert res_data["user"]["telegram_id"] == 999111
    assert res_data["user"]["google_sub"] == "google_sub_target"

    # Verify user_b was deleted
    deleted_b = await User.filter(id=user_b.id).first()
    assert deleted_b is None

    # Verify target user_a has aggregated balance (5 + 10 = 15 days)
    target_bal = await Balance.get(user=user_a)
    assert target_bal.remaining_frozen_days == 15

    # Verify payment transferred to user_a
    reassigned_payment = await Payment.get(id=payment.id)
    assert reassigned_payment.user_id == user_a.id


@pytest.mark.anyio
async def test_link_google_identity_to_telegram_user(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test linking a Google identity to an existing Telegram user."""
    user = await User.create(telegram_id=555444, username="tg_user_link")
    jwt_svc = JwtService()
    acc_token = jwt_svc.create_access_token(user.id)

    async def mock_validate(self: GoogleAuthService, id_token: str) -> GoogleUserData:
        return GoogleUserData(
            sub="google_sub_link_2",
            email="link2@test.com",
            name="Google Link 2",
        )

    monkeypatch.setattr(GoogleAuthService, "validate_id_token", mock_validate)

    response = await client.post(
        "/api/auth/link/google",
        headers={"Authorization": f"Bearer {acc_token}"},
        json={"id_token": "valid_mock_google_id_token"},
    )
    assert response.status_code == status.HTTP_200_OK
    res_data = response.json()
    assert res_data["status"] == "linked"
    assert res_data["user"]["telegram_id"] == 555444
    assert res_data["user"]["google_sub"] == "google_sub_link_2"
    assert res_data["user"]["google_email"] == "link2@test.com"


@pytest.mark.anyio
async def test_auto_merge_google_account_into_telegram_account(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test merging an existing Google account into a Telegram account when Google proof is provided from Telegram user."""
    # Target Telegram user
    user_tg = await User.create(telegram_id=777111, username="target_tg_user")
    await Balance.create(user=user_tg, remaining_frozen_days=7, is_frozen=True)

    # Source Google user
    user_g = await User.create(google_sub="google_sub_to_merge", google_email="source_g@test.com")
    await Balance.create(user=user_g, remaining_frozen_days=3, is_frozen=True)

    jwt_svc = JwtService()
    acc_token_tg = jwt_svc.create_access_token(user_tg.id)

    async def mock_validate(self: GoogleAuthService, id_token: str) -> GoogleUserData:
        return GoogleUserData(
            sub="google_sub_to_merge",
            email="source_g@test.com",
            name="Source Google",
        )

    monkeypatch.setattr(GoogleAuthService, "validate_id_token", mock_validate)

    response = await client.post(
        "/api/auth/link/google",
        headers={"Authorization": f"Bearer {acc_token_tg}"},
        json={"id_token": "valid_mock_google_id_token"},
    )
    assert response.status_code == status.HTTP_200_OK
    res_data = response.json()
    assert res_data["status"] == "merged"
    assert res_data["user"]["id"] == str(user_tg.id)
    assert res_data["user"]["telegram_id"] == 777111
    assert res_data["user"]["google_sub"] == "google_sub_to_merge"

    # Verify source Google user deleted
    deleted_g = await User.filter(id=user_g.id).first()
    assert deleted_g is None

    # Verify target balance (7 + 3 = 10 days)
    target_bal = await Balance.get(user=user_tg)
    assert target_bal.remaining_frozen_days == 10
