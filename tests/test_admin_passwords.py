import secrets
from typing import Any, cast

from fastapi import FastAPI
from pytest import MonkeyPatch

from helios_backend.services.auth.passwords import (
    hash_password,
    is_password_hash,
    verify_password,
)
from helios_backend.web.admin import panel


def test_hash_password_roundtrip() -> None:
    """Hashing helper should validate correct password and reject incorrect one."""
    sample_secret = secrets.token_urlsafe(24)

    hashed = hash_password(sample_secret)

    assert hashed != sample_secret
    assert is_password_hash(hashed)
    assert verify_password(sample_secret, hashed)
    assert not verify_password("wrong-password", hashed)


async def test_authenticate_migrates_plaintext_admin_password() -> None:
    """Legacy plaintext admin password should be migrated to hash on login."""
    legacy_secret = "".join(("plain", "-pass"))

    class _FakeAccount:
        def __init__(self) -> None:
            self.id = 7
            self.username = "legacy"
            self.password = legacy_secret
            self.saved_update_fields: list[str] | None = None

        async def save(self, *, update_fields: list[str]) -> None:
            self.saved_update_fields = update_fields

    class _FakeQuery:
        def __init__(self, account: _FakeAccount | None) -> None:
            self.account = account

        async def first(self) -> _FakeAccount | None:
            return self.account

    class _FakeModel:
        account = _FakeAccount()

        @classmethod
        def filter(cls, **_: str) -> _FakeQuery:
            return _FakeQuery(cls.account)

    class _DummyModelAdmin:
        model_cls = _FakeModel

    authenticated_id = await panel.AdminAccountModelAdmin.authenticate(
        cast(Any, _DummyModelAdmin()),
        "legacy",
        legacy_secret,
    )

    account = _FakeModel.account

    assert authenticated_id == account.id
    assert is_password_hash(account.password)
    assert verify_password(legacy_secret, account.password)
    assert account.saved_update_fields == ["password"]


async def test_configure_admin_panel_stores_hashed_password(
    monkeypatch: MonkeyPatch,
) -> None:
    """Bootstrap admin account should be stored with hashed password."""

    class _FakeAccount:
        def __init__(self, username: str, password: str) -> None:
            self.id = 1
            self.username = username
            self.password = password
            self.saved_update_fields: list[str] | None = None

        async def save(self, *, update_fields: list[str]) -> None:
            self.saved_update_fields = update_fields

    class _FakeQuery:
        async def first(self) -> None:
            return None

    class _FakeAdminAccount:
        created_account: _FakeAccount | None = None

        @classmethod
        def filter(cls, **_: str) -> _FakeQuery:
            return _FakeQuery()

        @classmethod
        async def create(cls, *, username: str, password: str) -> _FakeAccount:
            cls.created_account = _FakeAccount(username=username, password=password)
            return cls.created_account

    monkeypatch.setattr(panel, "_bootstrap_state", {"done": False})
    monkeypatch.setattr(panel, "AdminAccount", _FakeAdminAccount)
    monkeypatch.setattr(panel.settings, "environment", "dev")
    monkeypatch.setattr(panel.settings, "admin_panel_username", "bootstrap")
    monkeypatch.setattr(panel.settings, "admin_panel_password", "bootstrap-pass")

    await panel.configure_admin_panel(FastAPI())

    account = _FakeAdminAccount.created_account
    assert account is not None
    assert is_password_hash(account.password)
    assert verify_password("bootstrap-pass", account.password)
