from helios_backend.db.dao.vpn.active_proxy_dao import ActiveProxyDao
from helios_backend.db.models.vpn.active_proxies import ActiveProxy


class ProxyService:
    """Proxy retrieval service."""

    def __init__(self, proxy_dao: ActiveProxyDao | None = None) -> None:
        """Initialize proxy service."""
        self._proxy_dao = proxy_dao or ActiveProxyDao()

    async def get_active_proxies(self) -> list[ActiveProxy]:
        """Return all active proxies."""
        return await self._proxy_dao.get_all()

    async def get_proxy(self, proxy_id: int) -> ActiveProxy | None:
        """Return one proxy by id."""
        return await self._proxy_dao.get_by_id(proxy_id)