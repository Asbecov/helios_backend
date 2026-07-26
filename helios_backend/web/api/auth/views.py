from fastapi import APIRouter, Depends, HTTPException, status

from helios_backend.services.admin.runtime_settings import RuntimeSettingService
from helios_backend.services.auth.google import GoogleAuthService
from helios_backend.services.auth.jwt import JwtService
from helios_backend.services.auth.telegram import TelegramAuthService
from helios_backend.services.users.service import UserService
from helios_backend.web.api.auth.schema import (
    GoogleAuthRequest,
    LinkGoogleRequest,
    LinkMergeResponse,
    LinkTelegramRequest,
    RefreshTokenRequest,
    TelegramAuthRequest,
    TokenResponse,
)
from helios_backend.web.api.users.schema import UserResponse
from helios_backend.web.dependencies.rate_limit import rate_limit
from helios_backend.web.dependencies.security import CurrentUser
from helios_backend.web.dependencies.services import (
    get_google_auth_service,
    get_jwt_service,
    get_runtime_setting_service,
    get_telegram_auth_service,
    get_user_service,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/telegram",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(limit=20, window_seconds=60, prefix="auth"))],
)
async def telegram_auth(
    payload: TelegramAuthRequest,
    telegram_service: TelegramAuthService = Depends(get_telegram_auth_service),
    user_service: UserService = Depends(get_user_service),
    jwt_service: JwtService = Depends(get_jwt_service),
    runtime_setting_service: RuntimeSettingService = Depends(
        get_runtime_setting_service,
    ),
) -> TokenResponse:
    """Validate Telegram initData or Web Widget payload and issue access & refresh tokens."""
    if not await runtime_setting_service.registrations_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="registrations are disabled",
        )

    try:
        if payload.init_data:
            auth_data = telegram_service.validate_init_data(payload.init_data)
        elif payload.widget_data:
            auth_data = telegram_service.validate_widget_data(payload.widget_data)
        else:
            raise ValueError("init_data or widget_data required")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="authentication failed",
        ) from exc

    user = await user_service.get_or_create_telegram_user(
        telegram_id=auth_data.user.id,
        username=auth_data.user.username,
    )
    return TokenResponse(
        access_token=jwt_service.create_access_token(user.id),
        refresh_token=jwt_service.create_refresh_token(user.id),
    )


@router.post(
    "/google",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(limit=20, window_seconds=60, prefix="auth"))],
)
async def google_auth(
    payload: GoogleAuthRequest,
    google_service: GoogleAuthService = Depends(get_google_auth_service),
    user_service: UserService = Depends(get_user_service),
    jwt_service: JwtService = Depends(get_jwt_service),
    runtime_setting_service: RuntimeSettingService = Depends(
        get_runtime_setting_service,
    ),
) -> TokenResponse:
    """Validate Google ID token and issue access & refresh tokens."""
    if not await runtime_setting_service.registrations_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="registrations are disabled",
        )

    try:
        user_data = await google_service.validate_id_token(payload.id_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="google authentication failed",
        ) from exc

    user = await user_service.get_or_create_google_user(
        google_sub=user_data.sub,
        google_email=user_data.email,
        username=user_data.name,
    )
    return TokenResponse(
        access_token=jwt_service.create_access_token(user.id),
        refresh_token=jwt_service.create_refresh_token(user.id),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(limit=20, window_seconds=60, prefix="auth"))],
)
async def refresh_token(
    payload: RefreshTokenRequest,
    jwt_service: JwtService = Depends(get_jwt_service),
    user_service: UserService = Depends(get_user_service),
) -> TokenResponse:
    """Issue a new access token and rotated refresh token using a valid refresh_token."""
    try:
        user_id = jwt_service.decode_refresh_token(payload.refresh_token)
        user = await user_service.get_user_by_id(user_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return TokenResponse(
        access_token=jwt_service.create_access_token(user.id),
        refresh_token=jwt_service.create_refresh_token(user.id),
    )


@router.post(
    "/link/telegram",
    response_model=LinkMergeResponse,
    dependencies=[Depends(rate_limit(limit=20, window_seconds=60, prefix="auth"))],
)
async def link_telegram(
    payload: LinkTelegramRequest,
    current_user: CurrentUser,
    telegram_service: TelegramAuthService = Depends(get_telegram_auth_service),
    user_service: UserService = Depends(get_user_service),
    jwt_service: JwtService = Depends(get_jwt_service),
) -> LinkMergeResponse:
    """Link Telegram identity to active user or merge existing account."""
    try:
        if payload.init_data:
            auth_data = telegram_service.validate_init_data(payload.init_data)
        elif payload.widget_data:
            auth_data = telegram_service.validate_widget_data(payload.widget_data)
        else:
            raise ValueError("init_data or widget_data required")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="telegram authentication failed",
        ) from exc

    link_status, active_user = await user_service.link_or_merge_telegram(
        current_user=current_user,
        telegram_id=auth_data.user.id,
        username=auth_data.user.username,
    )

    return LinkMergeResponse(
        status=link_status,
        access_token=jwt_service.create_access_token(active_user.id),
        refresh_token=jwt_service.create_refresh_token(active_user.id),
        user=UserResponse.model_validate(active_user, from_attributes=True),
    )


@router.post(
    "/link/google",
    response_model=LinkMergeResponse,
    dependencies=[Depends(rate_limit(limit=20, window_seconds=60, prefix="auth"))],
)
async def link_google(
    payload: LinkGoogleRequest,
    current_user: CurrentUser,
    google_service: GoogleAuthService = Depends(get_google_auth_service),
    user_service: UserService = Depends(get_user_service),
    jwt_service: JwtService = Depends(get_jwt_service),
) -> LinkMergeResponse:
    """Link Google identity to active user or merge existing account."""
    try:
        user_data = await google_service.validate_id_token(payload.id_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="google authentication failed",
        ) from exc

    link_status, active_user = await user_service.link_or_merge_google(
        current_user=current_user,
        google_sub=user_data.sub,
        google_email=user_data.email,
    )

    return LinkMergeResponse(
        status=link_status,
        access_token=jwt_service.create_access_token(active_user.id),
        refresh_token=jwt_service.create_refresh_token(active_user.id),
        user=UserResponse.model_validate(active_user, from_attributes=True),
    )
