
from helios_backend.db.dao.vpn.active_server_dao import ActiveServerDao
from helios_backend.db.models.vpn.active_servers import ActiveServer

class ActiveServerService:
    """Active Servers Service."""
    def __init__(self, servers_dao: ActiveServerDao | None = None) -> None:
        self._servers_dao = servers_dao or ActiveServerDao()
        
    async def get_active_servers(self) -> list[ActiveServer]:
        """Return all active servers"""
        return await self._servers_dao.get_all()

    async def get_active_server(self, id: int) -> ActiveServer | None:
        """Return active server based on id"""
        return await self._servers_dao.get_by_id(id)


