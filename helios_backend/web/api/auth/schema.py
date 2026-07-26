from pydantic import BaseModel, Field

from helios_backend.web.api.users.schema import UserResponse


class TelegramAuthRequest(BaseModel):
    """Incoming auth payload from Telegram Mini App or Web Widget."""

    init_data: str | None = None
    widget_data: dict[str, str | int] | None = None


class GoogleAuthRequest(BaseModel):
    """Incoming auth payload from Google OAuth."""

    id_token: str = Field(min_length=10)


class TokenResponse(BaseModel):
    """JWT token response containing access and refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(TokenResponse):
    """JWT access token response for backward compatibility."""

    refresh_token: str = ""


class RefreshTokenRequest(BaseModel):
    """Payload to refresh an access token."""

    refresh_token: str = Field(min_length=10)


class LinkTelegramRequest(BaseModel):
    """Payload to link Telegram identity to active user."""

    init_data: str | None = None
    widget_data: dict[str, str | int] | None = None


class LinkGoogleRequest(BaseModel):
    """Payload to link Google identity to active user."""

    id_token: str = Field(min_length=10)


class LinkMergeResponse(BaseModel):
    """Response after linking or merging identity."""

    status: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
