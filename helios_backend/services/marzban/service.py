import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, cast
from urllib.parse import urlsplit, urlunsplit

from helios_backend.settings import settings


class MarzbanServiceError(RuntimeError):
    """Raised when Marzban operations fail."""


class MarzbanUserAlreadyExistsError(MarzbanServiceError):
    """Raised when Marzban create_user fails because user already exists."""


_MARZBAN_USERNAME_RE = re.compile(r"^[a-z0-9_]{3,32}$")


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


def validate_marzban_username(username: str) -> None:
    """Validate username according to Marzban API constraints."""
    if _MARZBAN_USERNAME_RE.fullmatch(username):
        return

    msg = "invalid Marzban username format"
    raise MarzbanServiceError(msg)


@dataclass
class MarzbanCreateUserPayload:
    """Minimal request payload accepted by Marzban create-user endpoint."""

    username: str
    proxies: dict[str, Any]
    inbounds: dict[str, Any]
    expire: int
    data_limit: int
    data_limit_reset_strategy: str
    status: str
    on_hold_expire_duration: int = 0


def build_create_user_payload(
    username: str,
    expires_at: datetime,
) -> MarzbanCreateUserPayload:
    """Build payload without response-only fields (created_at, links, etc.)."""
    return MarzbanCreateUserPayload(
        username=username,
        proxies={},
        inbounds={},
        expire=int(expires_at.timestamp()),
        data_limit=0,
        data_limit_reset_strategy="no_reset",
        status="active",
    )


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

    async def get_inbounds(self, token: Any) -> Any:
        """Fetch available inbounds configuration from Marzban."""
        ...


_KNOWN_PROTOCOLS = {
    "vmess",
    "vless",
    "trojan",
    "shadowsocks",
    "hysteria",
    "hysteria2",
    "tuic",
    "wireguard",
    "ssh",
    "socks",
    "http",
}


def _unique_tags(values: list[str]) -> list[str]:
    """Keep order while dropping duplicate tags."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _extract_tags(value: Any) -> list[str]:
    """Extract inbound tags from nested Marzban inbounds payload."""
    if isinstance(value, str):
        return [value]

    if isinstance(value, list):
        list_tags: list[str] = []
        for item in value:
            list_tags.extend(_extract_tags(item))
        return _unique_tags(list_tags)

    if isinstance(value, dict):
        dict_tags: list[str] = []
        tag_value = value.get("tag")
        if isinstance(tag_value, str):
            dict_tags.append(tag_value)
        for nested in value.values():
            dict_tags.extend(_extract_tags(nested))
        return _unique_tags(dict_tags)

    return []


def build_inbounds_and_proxies(
    inbounds_payload: Any,
) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
    """Build user inbounds/proxies maps from Marzban /api/inbounds response."""
    inbounds: dict[str, list[str]] = {}

    if isinstance(inbounds_payload, dict):
        for protocol, payload in inbounds_payload.items():
            if not isinstance(protocol, str) or protocol not in _KNOWN_PROTOCOLS:
                continue
            extracted_tags = _extract_tags(payload)
            if extracted_tags:
                inbounds[protocol] = extracted_tags

    proxies: dict[str, dict[str, Any]] = {protocol: {} for protocol in inbounds}
    return inbounds, proxies


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

    @staticmethod
    def _is_payload_validation_error(exc: Exception) -> bool:
        """Return True when Marzban rejects request payload with 422."""
        status_code = getattr(exc, "status", None)
        return isinstance(status_code, int) and status_code == 422

    async def _build_payload_from_inbounds(
        self,
        client: MarzbanClientProtocol,
        token: Any,
        username: str,
        expires_at: datetime,
    ) -> MarzbanCreateUserPayload | None:
        """Build create-user payload from live Marzban inbounds."""
        try:
            inbounds_payload = await client.get_inbounds(token=token)
        except Exception:
            return None

        inbounds, proxies = build_inbounds_and_proxies(inbounds_payload)
        if not inbounds:
            return None

        payload = build_create_user_payload(username=username, expires_at=expires_at)
        payload.inbounds = inbounds
        payload.proxies = proxies
        return payload

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

        validate_marzban_username(username)

        client, token = client_info
        payload = build_create_user_payload(username=username, expires_at=expires_at)
        try:
            await client.add_user(user=payload, token=token)
        except Exception as exc:
            if self._is_user_exists_error(exc):
                msg = f"marzban user {username} already exists"
                raise MarzbanUserAlreadyExistsError(msg) from exc

            if self._is_payload_validation_error(exc):
                retry_payload = await self._build_payload_from_inbounds(
                    client=client,
                    token=token,
                    username=username,
                    expires_at=expires_at,
                )
                if retry_payload is not None:
                    try:
                        await client.add_user(user=retry_payload, token=token)
                        return
                    except Exception as retry_exc:
                        if self._is_user_exists_error(retry_exc):
                            msg = f"marzban user {username} already exists"
                            raise MarzbanUserAlreadyExistsError(msg) from retry_exc

                msg = (
                    f"failed to create Marzban user {username}: "
                    "invalid payload for /api/user"
                )
                raise MarzbanServiceError(msg) from exc

            msg = f"failed to create Marzban user {username}"
            raise MarzbanServiceError(msg) from exc

    async def extend_user(self, username: str, expires_at: datetime) -> None:
        """Handle extend user."""
        client_info = await self._get_client_and_token()
        if client_info is None:
            return

        validate_marzban_username(username)

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

        validate_marzban_username(username)

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

        validate_marzban_username(username)

        client, token = client_info
        try:
            await client.delete_user(username, token=token)
        except Exception as exc:
            msg = f"failed to delete Marzban user {username}"
            raise MarzbanServiceError(msg) from exc
