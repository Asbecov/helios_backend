from click import UUID
from helios_backend.db.models.vpn.active_servers import ActiveServer


class ActiveServerDao:
    """DB access for active proxy links."""

    async def get_all(self) -> list[ActiveServer]:
        """Return all active proxies ordered by newest first."""
        return await ActiveServer.all().order_by("-added_at")

    async def get_by_id(self, proxy_id: int) -> ActiveServer | None:
        """Return active proxy by id if present."""
        return await ActiveServer.filter(id=proxy_id).first()
