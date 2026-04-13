from datetime import datetime
from typing import Any, Protocol, cast
from urllib.parse import urlsplit, urlunsplit

from helios_backend.settings import settings


class MarzbanServiceError(RuntimeError):
    """Raised when Marzban operations fail."""


class MarzbanUserAlreadyExistsError(MarzbanServiceError):
    """Raised when Marzban create_user fails because user already exists."""


def normalize_marzban_base_url(base_url: str) -> str:
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


class MarzbanClientProtocol(Protocol):
    """Represent marzban client protocol."""

    async def get_token(self) -> Any:
        """Handle get token."""
        ...

    async def add_user(self, *, user: Any, token: Any) -> None:
        """Handle add user."""
        ...

    async def get_user(self, username: str, *, token: Any) -> Any:
        """Handle get user."""
        ...

    async def modify_user(self, username: str, *, token: Any, user: Any) -> None:
        """Handle modify user."""
        ...

    async def delete_user(self, username: str, *, token: Any) -> None:
        """Handle delete user."""
        ...


class MarzbanService:
    """Client for Marzban API operations backed by marzpy."""

    @staticmethod
    def _is_user_exists_error(exc: Exception) -> bool:
        """Return True when create_user failed because user already exists."""
        status_code = getattr(exc, "status", None)
        if isinstance(status_code, int) and status_code == 409:
            return True

        message = str(exc).lower()
        return "exist" in message and "user" in message

    async def _get_client_and_token(self) -> tuple[MarzbanClientProtocol, Any] | None:
        """Handle get client and token."""
        if (
            not settings.marzban_base_url
            or not settings.marzban_admin_username
            or not settings.marzban_admin_password
        ):
            return None

        panel_url = normalize_marzban_base_url(settings.marzban_base_url)

        from marzpy import Marzban

        client = cast(
            MarzbanClientProtocol,
            Marzban(
                settings.marzban_admin_username,
                settings.marzban_admin_password,
                panel_url,
            ),
        )

        try:
            token = await client.get_token()
        except Exception as exc:
            msg = "failed to authenticate against Marzban"
            raise MarzbanServiceError(msg) from exc

        if not isinstance(token, dict):
            msg = "failed to authenticate against Marzban: invalid token response"
            raise MarzbanServiceError(msg)

        access_token = token.get("access_token")
        token_type = token.get("token_type")
        if not access_token or not token_type:
            msg = "failed to authenticate against Marzban: check admin credentials"
            raise MarzbanServiceError(msg)

        return client, token

    async def create_user(self, username: str, expires_at: datetime) -> None:
        """Handle create user."""
        client_info = await self._get_client_and_token()
        if client_info is None:
            return

        client, token = client_info
        from marzpy.api.user import User as MarzbanUser

        marzban_user = MarzbanUser(
            username=username,
            proxies={},
            inbounds={},
            expire=int(expires_at.timestamp()),
            data_limit=0,
            data_limit_reset_strategy="no_reset",
            status="active",
        )
        try:
            await client.add_user(user=marzban_user, token=token)
        except Exception as exc:
            if self._is_user_exists_error(exc):
                msg = f"marzban user {username} already exists"
                raise MarzbanUserAlreadyExistsError(msg) from exc
            msg = f"failed to create Marzban user {username}"
            raise MarzbanServiceError(msg) from exc

    async def extend_user(self, username: str, expires_at: datetime) -> None:
        """Handle extend user."""
        client_info = await self._get_client_and_token()
        if client_info is None:
            return

        client, token = client_info
        try:
            user = await client.get_user(username, token=token)
            user.expire = int(expires_at.timestamp())
            await client.modify_user(username, token=token, user=user)
        except Exception as exc:
            msg = f"failed to extend Marzban user {username}"
            raise MarzbanServiceError(msg) from exc

    async def get_user_info(self, username: str) -> dict[str, str | int | None]:
        """Handle get user info."""
        client_info = await self._get_client_and_token()
        if client_info is None:
            return {"expire": None}

        client, token = client_info
        try:
            user = await client.get_user(username, token=token)
        except Exception as exc:
            msg = f"failed to fetch Marzban user info for {username}"
            raise MarzbanServiceError(msg) from exc

        return {
            "expire": getattr(user, "expire", None),
            "subscription_url": getattr(user, "subscription_url", None),
        }

    async def get_subscription_url(self, username: str) -> str | None:
        """Handle get subscription url."""
        user_info = await self.get_user_info(username)
        subscription_url = user_info.get("subscription_url")
        if isinstance(subscription_url, str):
            return subscription_url
        return None

    async def delete_user(self, username: str) -> None:
        """Handle delete user."""
        client_info = await self._get_client_and_token()
        if client_info is None:
            return

        client, token = client_info
        try:
            await client.delete_user(username, token=token)
        except Exception as exc:
            msg = f"failed to delete Marzban user {username}"
            raise MarzbanServiceError(msg) from exc
