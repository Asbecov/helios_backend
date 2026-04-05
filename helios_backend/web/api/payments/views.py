from fastapi import APIRouter, Depends, Header, HTTPException, status

from helios_backend.services.payments.service import PaymentService
from helios_backend.web.api.payments.schema import (
    PaymentCreateRequest,
    PaymentCreateResponse,
    WebhookPayload,
    WebhookResponse,
)
from helios_backend.web.dependencies.rate_limit import rate_limit
from helios_backend.web.dependencies.security import CurrentUser
from helios_backend.web.dependencies.services import get_payment_service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "/create",
    response_model=PaymentCreateResponse,
    dependencies=[Depends(rate_limit(limit=20, window_seconds=60, prefix="payments"))],
)
async def create_payment(
    payload: PaymentCreateRequest,
    user: CurrentUser,
    service: PaymentService = Depends(get_payment_service),
) -> PaymentCreateResponse:
    """Create a payment via configured provider."""
    try:
        payment, provider_payload = await service.create_payment(
            user=user,
            plan_id=payload.plan_id,
            provider_name=payload.provider,
            code_raw=payload.code,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return PaymentCreateResponse(
        payment_id=payment.id,
        status=payment.status,
        external_id=payment.external_id,
        checkout_url=provider_payload["checkout_url"],
    )


@router.post(
    "/webhook/{provider}",
    response_model=WebhookResponse,
    dependencies=[Depends(rate_limit(limit=100, window_seconds=60, prefix="webhook"))],
)
async def payment_webhook(
    provider: str,
    payload: WebhookPayload,
    x_signature: str | None = Header(default=None),
    service: PaymentService = Depends(get_payment_service),
) -> WebhookResponse:
    """Handle provider webhook notifications."""
    try:
        payment = await service.process_webhook(
            provider_name=provider,
            payload=payload.model_dump(),
            signature=x_signature,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return WebhookResponse(payment_id=payment.id, status=payment.status)
