from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from helios_backend.services.balance.service import BalanceService
from helios_backend.services.marzban.service import (
    MarzbanService,
    MarzbanServiceError,
    MarzbanUserAlreadyExistsError,
)
from helios_backend.services.users.service import UserService
from helios_backend.web.api.subscriptions.schema import (
    SubscriptionStatusResponse,
    SubscriptionUrlResponse,
)
from helios_backend.web.dependencies.security import CurrentUser
from helios_backend.web.dependencies.services import (
    get_balance_service,
    get_marzban_service,
    get_user_service,
)

router = APIRouter(prefix="/subscription", tags=["subscription"])


def _build_status_response(
    status_payload: dict[str, int | bool | str | None] | None,
) -> SubscriptionStatusResponse:
    """Normalize balance status payload into API response shape."""
    if status_payload is None:
        status_payload = {
            "remaining_frozen_days": 0,
            "is_frozen": True,
            "active_expires_at": None,
            "activated_at": None,
            "frozen_at": None,
        }

    remaining_raw = status_payload.get("remaining_frozen_days")
    is_frozen_raw = status_payload.get("is_frozen")
    active_expires_at_raw = status_payload.get("active_expires_at")
    activated_at_raw = status_payload.get("activated_at")
    frozen_at_raw = status_payload.get("frozen_at")

    remaining_frozen_days = (
        remaining_raw
        if isinstance(remaining_raw, int) and not isinstance(remaining_raw, bool)
        else 0
    )
    is_frozen = is_frozen_raw if isinstance(is_frozen_raw, bool) else True
    active_expires_at = (
        active_expires_at_raw if isinstance(active_expires_at_raw, str) else None
    )
    activated_at = activated_at_raw if isinstance(activated_at_raw, str) else None
    frozen_at = frozen_at_raw if isinstance(frozen_at_raw, str) else None

    return SubscriptionStatusResponse(
        remaining_frozen_days=remaining_frozen_days,
        is_frozen=is_frozen,
        active_expires_at=active_expires_at,
        activated_at=activated_at,
        frozen_at=frozen_at,
    )


@router.get("", response_model=SubscriptionStatusResponse)
@router.get("/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    user: CurrentUser,
    balance_service: BalanceService = Depends(get_balance_service),
) -> SubscriptionStatusResponse:
    """Return current subscription balance status for current user."""
    status_payload = await balance_service.get_status(user)
    return _build_status_response(status_payload)


@router.post("/freeze", response_model=SubscriptionStatusResponse)
async def freeze_subscription(
    user: CurrentUser,
    balance_service: BalanceService = Depends(get_balance_service),
) -> SubscriptionStatusResponse:
    """Freeze active balance and return updated status."""
    status_payload = await balance_service.freeze(user)
    return _build_status_response(status_payload)


@router.post("/activate", response_model=SubscriptionStatusResponse)
async def activate_subscription(
    user: CurrentUser,
    balance_service: BalanceService = Depends(get_balance_service),
) -> SubscriptionStatusResponse:
    """Activate frozen balance and return updated status."""
    status_payload = await balance_service.activate(user)
    return _build_status_response(status_payload)


@router.get("/url", response_model=SubscriptionUrlResponse)
async def get_subscription_url(
    user: CurrentUser,
    balance_service: BalanceService = Depends(get_balance_service),
    marzban_service: MarzbanService = Depends(get_marzban_service),
    user_service: UserService = Depends(get_user_service),
) -> SubscriptionUrlResponse:
    """Return subscription URL only when local balance is already active."""
    status_payload = await balance_service.get_status(user)
    if status_payload is None or status_payload.get("is_frozen") is not False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="subscription is not active",
        )

    active_expires_at = status_payload.get("active_expires_at")
    if not isinstance(active_expires_at, str):
        return SubscriptionUrlResponse(subscription_url=None)

    marzban_username = await user_service.get_or_create_marzban_username(user)
    expires_at = datetime.fromisoformat(active_expires_at)

    try:
        try:
            await marzban_service.create_user(
                username=marzban_username,
                expires_at=expires_at,
            )
        except MarzbanUserAlreadyExistsError:
            # If user already exists remotely, extend expiry to match local state.
            await marzban_service.extend_user(
                username=marzban_username,
                expires_at=expires_at,
            )

        subscription_url = await marzban_service.get_subscription_url(marzban_username)
    except MarzbanServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="failed to sync subscription with marzban",
        ) from exc

    return SubscriptionUrlResponse(subscription_url=subscription_url)
