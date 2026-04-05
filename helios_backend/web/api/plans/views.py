from fastapi import APIRouter, Depends, Query

from helios_backend.services.codes.service import CodeService
from helios_backend.services.plans.service import PlanService
from helios_backend.web.api.plans.schema import PlanResponse
from helios_backend.web.dependencies.security import CurrentUser
from helios_backend.web.dependencies.services import get_code_service, get_plan_service

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanResponse])
async def get_plans(
    user: CurrentUser,
    code: str | None = Query(default=None),
    code_service: CodeService = Depends(get_code_service),
    plan_service: PlanService = Depends(get_plan_service),
) -> list[PlanResponse]:
    """Return available plans with optional promo-adjusted pricing."""
    resolved_code = await code_service.resolve_valid_code(code, user_id=user.id)
    plans = await plan_service.get_plans_with_discount(resolved_code)
    return [
        PlanResponse(
            id=plan.id,
            name=plan.name,
            duration_days=plan.duration_days,
            price=plan.price,
            final_price=final_price,
            tags=plan.tags,
        )
        for plan, final_price in plans
    ]


@router.get("/base", response_model=PlanResponse)
async def get_base_plan(
    plan_service: PlanService = Depends(get_plan_service),
) -> PlanResponse:
    """Return base subscription plan used for new users."""
    plan = await plan_service.get_base_plan()
    return PlanResponse(
        id=plan.id,
        name=plan.name,
        duration_days=plan.duration_days,
        price=plan.price,
        final_price=plan.price,
        tags=plan.tags,
    )
