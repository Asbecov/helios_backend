from fastapi import APIRouter, Depends

from helios_backend.services.proxies.service import ProxyService
from helios_backend.web.api.proxies.schema import ProxyResponse
from helios_backend.web.dependencies.services import get_proxy_service


router = APIRouter(prefix="/proxies", tags=["proxies"])


@router.get("", response_model=list[ProxyResponse])
async def get_proxies(
    proxy_service: ProxyService = Depends(get_proxy_service),
) -> list[ProxyResponse]:
    """Return list of active proxies."""
    proxies = await proxy_service.get_active_proxies()
    return [
        ProxyResponse(
            url=proxy.proxy,
            added_at=proxy.added_at.isoformat(),
        )
        for proxy in proxies
    ]

