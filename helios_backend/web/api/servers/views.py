from fastapi import APIRouter, Depends

from helios_backend.services.servers.service import ActiveServerService
from helios_backend.web.api.servers.schemas import ActiveServerResponse
from helios_backend.web.dependencies.services import get_server_service

router = APIRouter(prefix="/servers", tags=["servers"])

@router.get("", response_model = list[ActiveServerResponse])
async def get_servers(
    server_service : ActiveServerService = Depends(get_server_service)
) -> list[ActiveServerResponse]:
    """Return list of active servers."""
    server_list = await server_service.get_active_servers()
    return [
        ActiveServerResponse(
            server_name=server.server_name,
            server_address=server.server_address,
            added_at=server.added_at.isoformat()
        )
        for server in server_list
    ]
