from contextlib import suppress
from datetime import datetime
from typing import ClassVar
from urllib.parse import urlsplit, urlunsplit

from marzban import MarzbanAPI, MarzbanTokenCache, ProxySettings, UserCreate, UserModify

from helios_backend.settings import settings


class MarzbanServiceError(RuntimeError):
    """Raised when Marzban operations fail."""


class MarzbanUserAlreadyExistsError(MarzbanServiceError):
    """Raised when Marzban create_user fails because user already exists."""


def _normalize_marzban_base_url(base_url: str) -> str:
    """Validate and normalize Marzban panel base URL."""
    raw_value = base_url.strip()
    if not raw_value:
        msg = "HELIOS_BACKEND_MARZBAN_BASE_URL is empty"
        raise MarzbanServiceError(msg)

    parsed = urlsplit(raw_value)
    if not parsed.scheme:
        msg = (
            "HELIOS_BACKEND_MARZBAN_BASE_URL must include scheme (http:// or https://)"
        )
        raise MarzbanServiceError(msg)

    if parsed.scheme not in {"http", "https"}:
        msg = "HELIOS_BACKEND_MARZBAN_BASE_URL must use http or https"
        raise MarzbanServiceError(msg)

    if not parsed.netloc:
        msg = "HELIOS_BACKEND_MARZBAN_BASE_URL must include host"
        raise MarzbanServiceError(msg)

    normalized_path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, "", ""))


class MarzbanService:
    """Client for Marzban API operations via marzban public API."""

    _DEFAULT_PROXY_NAME: ClassVar[str] = "vless"
    _DEFAULT_INBOUND_NAMES: ClassVar[tuple[str, ...]] = (
        "vless tls",
        "vless reality",
        "vless reality 443",
    )
    _DEFAULT_PROXY_SETTINGS: ClassVar[ProxySettings] = ProxySettings(
        flow="xtls-rprx-vision"
    )

    def __init__(self) -> None:
        """Initialize lazy Marzban API client and token cache."""
        self._api: MarzbanAPI | None = None
        self._token_cache: MarzbanTokenCache | None = None
        self._fingerprint: tuple[str, str, str] | None = None

    @staticmethod
    def _is_user_exists_error(exc: Exception) -> bool:
        """Return True when create_user failed because user already exists."""
        status_code = getattr(exc, "status", None)
        if not isinstance(status_code, int):
            status_code = getattr(exc, "status_code", None)
        if not isinstance(status_code, int):
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int) and status_code == 409:
            return True

        message = str(exc).lower()
        return ("exist" in message and "user" in message) or "already exists" in message

    @staticmethod
    def _is_configured() -> bool:
        """Check whether Marzban settings are configured."""
        return bool(
            settings.marzban_base_url
            and settings.marzban_admin_username
            and settings.marzban_admin_password
        )

    async def _ensure_client(self) -> tuple[MarzbanAPI, MarzbanTokenCache] | None:
        """Build or reuse Marzban API client and token cache."""
        if not self._is_configured():
            return None

        base_url = _normalize_marzban_base_url(settings.marzban_base_url or "")
        username = settings.marzban_admin_username or ""
        password = settings.marzban_admin_password or ""
        fingerprint = (base_url, username, password)

        if self._api is not None and self._token_cache is not None:
            if self._fingerprint == fingerprint:
                return self._api, self._token_cache

            with suppress(Exception):
                await self._api.close()
            self._api = None
            self._token_cache = None

        api = MarzbanAPI(base_url=base_url)
        token_cache = MarzbanTokenCache(
            client=api,
            username=username,
            password=password,
        )

        self._api = api
        self._token_cache = token_cache
        self._fingerprint = fingerprint
        return api, token_cache

    async def _get_token(self) -> tuple[MarzbanAPI, str] | None:
        """Get active Marzban token from token cache."""
        client_bundle = await self._ensure_client()
        if client_bundle is None:
            return None

        api, token_cache = client_bundle
        try:
            token = await token_cache.get_token()
        except Exception as exc:
            msg = "failed to authenticate against Marzban"
            raise MarzbanServiceError(msg) from exc

        if not isinstance(token, str) or not token:
            msg = "failed to authenticate against Marzban: check admin credentials"
            raise MarzbanServiceError(msg)

        return api, token

    async def create_user(self, username: str, expires_at: datetime) -> None:
        """Create a user in Marzban."""
        token_bundle = await self._get_token()
        if token_bundle is None:
            return

        api, token = token_bundle
        user = UserCreate(
            username=username,
            proxies={self._DEFAULT_PROXY_NAME: self._DEFAULT_PROXY_SETTINGS},
            inbounds={self._DEFAULT_PROXY_NAME: list(self._DEFAULT_INBOUND_NAMES)},
            expire=int(expires_at.timestamp()),
            data_limit=0,
            data_limit_reset_strategy="no_reset",
            status="active",
        )

        try:
            await api.add_user(user=user, token=token)
        except Exception as exc:
            if self._is_user_exists_error(exc):
                msg = f"marzban user {username} already exists"
                raise MarzbanUserAlreadyExistsError(msg) from exc

            msg = f"failed to create Marzban user {username}"
            raise MarzbanServiceError(msg) from exc

    async def extend_user(self, username: str, expires_at: datetime) -> None:
        """Update user expiry in Marzban."""
        token_bundle = await self._get_token()
        if token_bundle is None:
            return

        api, token = token_bundle
        try:
            await api.modify_user(
                username=username,
                user=UserModify(expire=int(expires_at.timestamp())),
                token=token,
            )
        except Exception as exc:
            msg = f"failed to extend Marzban user {username}"
            raise MarzbanServiceError(msg) from exc

    async def get_user_info(self, username: str) -> dict[str, str | int | None]:
        """Fetch user details from Marzban."""
        token_bundle = await self._get_token()
        if token_bundle is None:
            return {"expire": None}

        api, token = token_bundle
        try:
            user = await api.get_user(username=username, token=token)
        except Exception as exc:
            msg = f"failed to fetch Marzban user info for {username}"
            raise MarzbanServiceError(msg) from exc

        expire_value = getattr(user, "expire", None)
        subscription_value = getattr(user, "subscription_url", None)
        return {
            "expire": expire_value if isinstance(expire_value, int) else None,
            "subscription_url": (
                subscription_value if isinstance(subscription_value, str) else None
            ),
        }

    async def get_subscription_url(self, username: str) -> str | None:
        """Get user subscription URL from Marzban."""
        user_info = await self.get_user_info(username)
        subscription_url = user_info.get("subscription_url")
        if isinstance(subscription_url, str):
            return subscription_url
        return None

    async def delete_user(self, username: str | None) -> None:
        """Delete user from Marzban."""
        if not username:
            return

        token_bundle = await self._get_token()
        if token_bundle is None:
            return

        api, token = token_bundle
        try:
            await api.remove_user(username=username, token=token)
        except Exception as exc:
            msg = f"failed to delete Marzban user {username}"
            raise MarzbanServiceError(msg) from exc

    async def close(self) -> None:
        """Close underlying Marzban API client resources."""
        if self._api is not None:
            with suppress(Exception):
                await self._api.close()

        self._api = None
        self._token_cache = None
        self._fingerprint = None
