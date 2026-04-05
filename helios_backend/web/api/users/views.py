from fastapi import APIRouter, Depends

from helios_backend.services.codes.service import CodeService
from helios_backend.services.users.service import UserService
from helios_backend.web.api.users.schema import (
    ReferralCodeResponse,
    ReferralUsageResponse,
    UserResponse,
)
from helios_backend.web.dependencies.security import CurrentUser
from helios_backend.web.dependencies.services import get_code_service, get_user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(user: CurrentUser) -> UserResponse:
    """Return current user profile."""
    return UserResponse.model_validate(user, from_attributes=True)


@router.delete("/me")
async def delete_me(
    user: CurrentUser,
    user_service: UserService = Depends(get_user_service),
) -> None:
    """Delete user and related resources through user service."""
    await user_service.delete_user(user)


@router.get("/me/referral-code", response_model=ReferralCodeResponse)
async def get_my_referral_code(
    user: CurrentUser,
    code_service: CodeService = Depends(get_code_service),
) -> ReferralCodeResponse:
    """Return current user's referral code, creating it when absent."""
    code = await code_service.get_or_create_user_referral_code(user)
    return ReferralCodeResponse(
        id=code.id,
        code=code.code,
        discount_percent=code.discount_percent,
        reward_days_percent=code.reward_days_percent,
        expires_at=code.expires_at,
        is_active=code.is_active,
    )


@router.get("/me/referral-usages", response_model=list[ReferralUsageResponse])
async def get_my_referral_usages(
    user: CurrentUser,
    code_service: CodeService = Depends(get_code_service),
) -> list[ReferralUsageResponse]:
    """Return usage events for referral codes owned by current user."""
    usages = await code_service.get_referral_usages_by_user(user.id)
    response: list[ReferralUsageResponse] = []
    for usage in usages:
        response.append(
            ReferralUsageResponse(
                id=usage.id,
                created_at=usage.created_at,
                code_id=usage.code.id,
                code=usage.code.code,
                user_id=usage.user.id,
                user_telegram_id=usage.user.telegram_id,
                user_username=usage.user.username,
            )
        )
    return response
