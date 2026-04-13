from datetime import UTC, datetime
from typing import Any

import pytest

from helios_backend.services.marzban.service import (
    MarzbanService,
    MarzbanServiceError,
    build_inbounds_and_proxies,
    validate_marzban_username,
)


def test_validate_marzban_username_accepts_valid_value() -> None:
    """Accept usernames that satisfy Marzban constraints."""
    validate_marzban_username("u_urbantelaviv")


@pytest.mark.parametrize(
    "username",
    [
        "ab",
        "A_user",
        "user-with-dash",
        "user.with.dot",
        "user@name",
        "u_" + "a" * 31,
    ],
)
def test_validate_marzban_username_rejects_invalid_value(username: str) -> None:
    """Reject usernames outside Marzban allowed pattern."""
    with pytest.raises(MarzbanServiceError, match="invalid Marzban username format"):
        validate_marzban_username(username)


async def test_create_user_sends_integer_expire_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create-user payload should send expire as UTC timestamp integer."""

    class _FakeClient:
        def __init__(self) -> None:
            self.received_user: Any | None = None

        async def add_user(self, *, user: object, token: object) -> None:
            _ = token
            self.received_user = user

    fake_client = _FakeClient()
    service = MarzbanService()

    async def fake_get_client_and_token() -> tuple[_FakeClient, dict[str, str]]:
        return fake_client, {"access_token": "t", "token_type": "Bearer"}

    monkeypatch.setattr(service, "_get_client_and_token", fake_get_client_and_token)

    expires_at = datetime(2026, 4, 14, 12, 30, tzinfo=UTC)
    await service.create_user(username="u_urbantelaviv", expires_at=expires_at)

    assert fake_client.received_user is not None
    assert fake_client.received_user.expire == int(expires_at.timestamp())
    assert set(fake_client.received_user.__dict__) == {
        "username",
        "proxies",
        "inbounds",
        "expire",
        "data_limit",
        "data_limit_reset_strategy",
        "status",
        "on_hold_expire_duration",
    }


def test_build_inbounds_and_proxies_from_nested_payload() -> None:
    """Convert Marzban inbounds payload into user inbounds/proxies maps."""
    source = {
        "vmess": {
            "ws": ["vmess-ws"],
            "tcp": ["vmess-tcp"],
        },
        "vless": [{"tag": "vless-reality"}],
        "unexpected": ["ignored"],
    }

    inbounds, proxies = build_inbounds_and_proxies(source)

    assert inbounds == {
        "vmess": ["vmess-ws", "vmess-tcp"],
        "vless": ["vless-reality"],
    }
    assert proxies == {
        "vmess": {},
        "vless": {},
    }


async def test_create_user_retries_with_inbounds_after_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry create-user with discovered inbounds when first payload gets 422."""

    class _PayloadValidationError(RuntimeError):
        def __init__(self) -> None:
            super().__init__("unprocessable entity")
            self.status = 422

    class _FakeClient:
        def __init__(self) -> None:
            self.calls = 0
            self.final_payload: Any | None = None

        async def add_user(self, *, user: object, token: object) -> None:
            _ = token
            self.calls += 1
            if self.calls == 1:
                raise _PayloadValidationError
            self.final_payload = user

        async def get_inbounds(self, *, token: object) -> dict[str, Any]:
            _ = token
            return {
                "vmess": {
                    "ws": ["vmess-ws"],
                },
            }

    fake_client = _FakeClient()
    service = MarzbanService()

    async def fake_get_client_and_token() -> tuple[_FakeClient, dict[str, str]]:
        return fake_client, {"access_token": "t", "token_type": "Bearer"}

    monkeypatch.setattr(service, "_get_client_and_token", fake_get_client_and_token)

    expires_at = datetime(2026, 4, 14, 12, 30, tzinfo=UTC)
    await service.create_user(username="u_urbantelaviv", expires_at=expires_at)

    assert fake_client.calls == 2
    assert fake_client.final_payload is not None
    assert fake_client.final_payload.inbounds == {"vmess": ["vmess-ws"]}
    assert fake_client.final_payload.proxies == {"vmess": {}}
