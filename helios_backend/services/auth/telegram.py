import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from json import JSONDecodeError
from urllib.parse import parse_qsl

from pydantic import BaseModel

from helios_backend.settings import settings


class TelegramUserData(BaseModel):
    """Telegram user payload decoded from initData."""

    id: int
    username: str | None = None


class TelegramAuthData(BaseModel):
    """Validated auth data from Telegram Mini App."""

    user: TelegramUserData
    start_param: str | None = None


class TelegramAuthService:
    """Validates Telegram initData according to Telegram specification."""

    def validate_init_data(self, init_data: str) -> TelegramAuthData:
        """Handle validate init data."""
        if not settings.telegram_bot_token:
            msg = "telegram bot token is not configured"
            raise ValueError(msg)

        parsed = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            msg = "initData hash is missing"
            raise ValueError(msg)

        data_check_string = "\n".join(
            sorted(f"{key}={value}" for key, value in parsed.items()),
        )
        secret = hmac.new(
            key=b"WebAppData",
            msg=settings.telegram_bot_token.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        computed_hash = hmac.new(
            key=secret,
            msg=data_check_string.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        if not secrets.compare_digest(computed_hash, received_hash):
            msg = "invalid initData hash"
            raise ValueError(msg)

        auth_date_raw = parsed.get("auth_date")
        if not auth_date_raw or not auth_date_raw.isdigit():
            msg = "invalid auth_date"
            raise ValueError(msg)
        auth_date = datetime.fromtimestamp(int(auth_date_raw), tz=UTC)
        age_seconds = (datetime.now(tz=UTC) - auth_date).total_seconds()
        if age_seconds > settings.telegram_auth_max_age_seconds:
            msg = "initData is expired"
            raise ValueError(msg)

        user_raw = parsed.get("user")
        if not user_raw:
            msg = "missing user payload"
            raise ValueError(msg)
        try:
            user_data = TelegramUserData.model_validate(json.loads(user_raw))
        except JSONDecodeError as exc:
            msg = "invalid user payload json"
            raise ValueError(msg) from exc
        return TelegramAuthData(user=user_data, start_param=parsed.get("start_param"))
