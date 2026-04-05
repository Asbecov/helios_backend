from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from helios_backend.settings import settings


class JwtService:
    """JWT token generation and validation."""

    def create_access_token(self, user_id: UUID) -> str:
        """Handle create access token."""
        expires_at = datetime.now(tz=UTC) + timedelta(
            minutes=settings.jwt_access_token_exp_minutes,
        )
        payload = {
            "sub": str(user_id),
            "exp": expires_at,
            "type": "access",
        }
        return jwt.encode(
            payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
        )

    def decode_access_token(self, token: str) -> UUID:
        """Handle decode access token."""
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        token_type = payload.get("type")
        if token_type != "access":
            msg = "invalid token type"
            raise ValueError(msg)
        subject = payload.get("sub")
        if not subject:
            msg = "missing token subject"
            raise ValueError(msg)
        return UUID(subject)
