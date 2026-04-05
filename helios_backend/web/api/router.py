from fastapi.routing import APIRouter

from helios_backend.web.api import (
    auth,
    monitoring,
    payments,
    plans,
    subscriptions,
    users,
)

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(auth.router)
api_router.include_router(plans.router)
api_router.include_router(users.router)
api_router.include_router(subscriptions.router)
api_router.include_router(payments.router)
