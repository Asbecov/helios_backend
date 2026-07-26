from pydantic import BaseModel
import httpx

from helios_backend.settings import settings


class GoogleUserData(BaseModel):
    """Google user payload decoded from id_token or tokeninfo."""

    sub: str
    email: str | None = None
    name: str | None = None


class GoogleAuthService:
    """Validates Google ID tokens with Google OAuth API."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        """Initialize Google auth service."""
        self._http_client = http_client

    async def validate_id_token(self, id_token: str) -> GoogleUserData:
        """Validate Google id_token using Google tokeninfo API."""
        if not id_token or not id_token.strip():
            msg = "id_token is empty"
            raise ValueError(msg)

        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
        if self._http_client:
            response = await self._http_client.get(url)
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)

        if response.status_code != 200:
            msg = "invalid google id_token"
            raise ValueError(msg)

        data = response.json()
        sub = data.get("sub")
        if not sub:
            msg = "missing sub in google token payload"
            raise ValueError(msg)

        aud = data.get("aud")
        if settings.google_client_id and aud != settings.google_client_id:
            msg = "google id_token audience mismatch"
            raise ValueError(msg)

        return GoogleUserData(
            sub=sub,
            email=data.get("email"),
            name=data.get("name") or data.get("given_name"),
        )
