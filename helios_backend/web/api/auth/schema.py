from pydantic import BaseModel, Field


class TelegramAuthRequest(BaseModel):
    """Incoming auth payload from Telegram Mini App."""

    init_data: str = Field(min_length=10)


class AccessTokenResponse(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str = "bearer"
