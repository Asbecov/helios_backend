from helios_backend.db.models.vpn.active_proxies import ActiveProxy


class ActiveProxyDao:
    """DB access for active proxy links."""

    async def get_all(self) -> list[ActiveProxy]:
        """Return all active proxies ordered by newest first."""
        return await ActiveProxy.all().order_by("-added_at")

    async def get_by_id(self, proxy_id: int) -> ActiveProxy | None:
        """Return active proxy by id if present."""
        return await ActiveProxy.filter(id=proxy_id).first()
