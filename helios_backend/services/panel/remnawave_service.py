from contextlib import suppress
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

from remnawave import RemnawaveSDK
from remnawave.exceptions import ConflictError, NotFoundError
from remnawave.models.users import CreateUserRequestDto, UpdateUserRequestDto

from helios_backend.services.panel.base import (
    BasePanelService,
    PanelServiceError,
    PanelUserAlreadyExistsError,
)
from helios_backend.settings import settings

RemnawaveServiceError = PanelServiceError
RemnawaveUserAlreadyExistsError = PanelUserAlreadyExistsError


def _normalize_remnawave_base_url(base_url: str) -> str:
    """Validate and normalize Remnawave panel base URL."""
    raw_value = base_url.strip()
    if not raw_value:
        msg = "HELIOS_BACKEND_REMNAWAVE_BASE_URL is empty"
        raise RemnawaveServiceError(msg)

    parsed = urlsplit(raw_value)
    if not parsed.scheme:
        msg = (
            "HELIOS_BACKEND_REMNAWAVE_BASE_URL must include scheme (http:// or https://)"
        )
        raise RemnawaveServiceError(msg)

    if parsed.scheme not in {"http", "https"}:
        msg = "HELIOS_BACKEND_REMNAWAVE_BASE_URL must use http or https"
        raise RemnawaveServiceError(msg)

    if not parsed.netloc:
        msg = "HELIOS_BACKEND_REMNAWAVE_BASE_URL must include host"
        raise RemnawaveServiceError(msg)

    normalized_path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, "", ""))


class RemnawaveService(BasePanelService):
    """Client for Remnawave API operations via remnawave SDK."""

    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
    ) -> None:
        """Initialize lazy Remnawave API client."""
        self._custom_base_url = base_url
        self._custom_api_token = api_token
        self._sdk: RemnawaveSDK | None = None
        self._fingerprint: tuple[str, str] | None = None

    @property
    def base_url(self) -> str | None:
        """Get resolved base URL."""
        return self._custom_base_url or settings.remnawave_base_url

    @property
    def api_token(self) -> str | None:
        """Get resolved API token."""
        return self._custom_api_token or settings.remnawave_api_token

    @staticmethod
    def _is_user_exists_error(exc: Exception) -> bool:
        """Return True when create_user failed because user already exists."""
        if isinstance(exc, ConflictError):
            return True

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

    def _is_configured(self) -> bool:
        """Check whether Remnawave settings are configured."""
        return bool(self.base_url and self.api_token)

    async def _ensure_client(self) -> RemnawaveSDK | None:
        """Build or reuse Remnawave SDK client."""
        if not self._is_configured():
            return None

        base_url = _normalize_remnawave_base_url(self.base_url or "")
        token = self.api_token or ""
        fingerprint = (base_url, token)

        if self._sdk is not None:
            if self._fingerprint == fingerprint:
                return self._sdk

            client = getattr(self._sdk, "_client", None)
            if client is not None:
                with suppress(Exception):
                    await client.aclose()
            self._sdk = None

        sdk = RemnawaveSDK(base_url=base_url, token=token)
        self._sdk = sdk
        self._fingerprint = fingerprint
        return sdk

    @staticmethod
    def _ensure_timezone(dt: datetime) -> datetime:
        """Ensure datetime object is timezone-aware."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

    async def create_user(self, username: str, expires_at: datetime) -> None:
        """Create a user in Remnawave."""
        sdk = await self._ensure_client()
        if sdk is None:
            return

        body = CreateUserRequestDto(
            username=username,
            expire_at=self._ensure_timezone(expires_at),
        )

        try:
            await sdk.users.create_user(body=body)
        except Exception as exc:
            if self._is_user_exists_error(exc):
                msg = f"remnawave user {username} already exists"
                raise RemnawaveUserAlreadyExistsError(msg) from exc

            msg = f"failed to create Remnawave user {username}"
            raise RemnawaveServiceError(msg) from exc

    async def extend_user(self, username: str, expires_at: datetime) -> None:
        """Update user expiry in Remnawave."""
        sdk = await self._ensure_client()
        if sdk is None:
            return

        body = UpdateUserRequestDto(
            username=username,
            expire_at=self._ensure_timezone(expires_at),
        )

        try:
            await sdk.users.update_user(body=body)
        except Exception as exc:
            msg = f"failed to extend Remnawave user {username}"
            raise RemnawaveServiceError(msg) from exc

    async def get_user_info(self, username: str) -> dict[str, str | int | None]:
        """Fetch user details from Remnawave."""
        sdk = await self._ensure_client()
        if sdk is None:
            return {"expire": None, "subscription_url": None}

        try:
            user = await sdk.users.get_user_by_username(username=username)
        except NotFoundError:
            return {"expire": None, "subscription_url": None}
        except Exception as exc:
            msg = f"failed to fetch Remnawave user info for {username}"
            raise RemnawaveServiceError(msg) from exc

        expire_val: int | None = None
        if getattr(user, "expire_at", None):
            expire_val = int(user.expire_at.timestamp())

        sub_url = getattr(user, "subscription_url", None)
        return {
            "expire": expire_val,
            "subscription_url": sub_url if isinstance(sub_url, str) else None,
        }

    async def get_subscription_url(self, username: str) -> str | None:
        """Get user subscription URL from Remnawave."""
        user_info = await self.get_user_info(username)
        subscription_url = user_info.get("subscription_url")
        if isinstance(subscription_url, str):
            return subscription_url
        return None

    async def delete_user(self, username: str | None) -> None:
        """Delete user from Remnawave."""
        if not username:
            return

        sdk = await self._ensure_client()
        if sdk is None:
            return

        try:
            user = await sdk.users.get_user_by_username(username=username)
            if user and getattr(user, "uuid", None):
                await sdk.users.delete_user(uuid=str(user.uuid))
        except NotFoundError:
            return
        except Exception as exc:
            msg = f"failed to delete Remnawave user {username}"
            raise RemnawaveServiceError(msg) from exc

    async def close(self) -> None:
        """Close underlying Remnawave API client resources."""
        if self._sdk is not None:
            client = getattr(self._sdk, "_client", None)
            if client is not None:
                with suppress(Exception):
                    await client.aclose()

        self._sdk = None
        self._fingerprint = None
