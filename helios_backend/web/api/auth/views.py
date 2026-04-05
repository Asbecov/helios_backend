from fastapi import APIRouter, Depends, HTTPException, status

from helios_backend.services.auth.jwt import JwtService
from helios_backend.services.auth.telegram import TelegramAuthService
from helios_backend.services.users.service import UserService
from helios_backend.web.api.auth.schema import AccessTokenResponse, TelegramAuthRequest
from helios_backend.web.dependencies.rate_limit import rate_limit
from helios_backend.web.dependencies.services import (
    get_jwt_service,
    get_telegram_auth_service,
    get_user_service,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/telegram",
    response_model=AccessTokenResponse,
    dependencies=[Depends(rate_limit(limit=20, window_seconds=60, prefix="auth"))],
)
async def telegram_auth(
    payload: TelegramAuthRequest,
    telegram_service: TelegramAuthService = Depends(get_telegram_auth_service),
    user_service: UserService = Depends(get_user_service),
    jwt_service: JwtService = Depends(get_jwt_service),
) -> AccessTokenResponse:
    """Validate Telegram initData and issue JWT token."""

    try:
        auth_data = telegram_service.validate_init_data(payload.init_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    user = await user_service.get_or_create_telegram_user(
        telegram_id=auth_data.user.id,
        username=auth_data.user.username,
    )
    return AccessTokenResponse(access_token=jwt_service.create_access_token(user.id))
