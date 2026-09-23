from datetime import datetime

from helios_backend.services.panel.base import (
    BasePanelService,
    PanelServiceError,
    PanelUserAlreadyExistsError,
)
from helios_backend.services.panel.marzban_service import MarzbanService
from helios_backend.services.panel.remnawave_service import RemnawaveService
from helios_backend.settings import settings


def create_panel_backend(
    panel_type: str | None = None,
    **kwargs: str | None,
) -> BasePanelService:
    """Create concrete panel backend instance based on type."""
    resolved_type = (panel_type or settings.panel_type or "remnawave").strip().lower()
    if resolved_type == "marzban":
        return MarzbanService(
            base_url=kwargs.get("base_url"),
            username=kwargs.get("username"),
            password=kwargs.get("password"),
        )
    if resolved_type == "remnawave":
        return RemnawaveService(
            base_url=kwargs.get("base_url"),
            api_token=kwargs.get("api_token"),
        )

    msg = f"unsupported panel type: {resolved_type}"
    raise PanelServiceError(msg)


class PanelService(BasePanelService):
    """Unified panel service delegating to the configured panel backend."""

    def __init__(
        self,
        backend: BasePanelService | None = None,
        panel_type: str | None = None,
    ) -> None:
        """Initialize panel service with explicit backend or configured default."""
        self._backend: BasePanelService = backend or create_panel_backend(
            panel_type=panel_type
        )

    @property
    def backend(self) -> BasePanelService:
        """Return underlying concrete panel backend."""
        return self._backend

    async def create_user(self, username: str, expires_at: datetime) -> None:
        """Create user via active panel backend."""
        await self._backend.create_user(username=username, expires_at=expires_at)

    async def extend_user(self, username: str, expires_at: datetime) -> None:
        """Extend user via active panel backend."""
        await self._backend.extend_user(username=username, expires_at=expires_at)

    async def get_user_info(self, username: str) -> dict[str, str | int | None]:
        """Fetch user info via active panel backend."""
        return await self._backend.get_user_info(username=username)

    async def get_subscription_url(self, username: str) -> str | None:
        """Fetch subscription URL via active panel backend."""
        return await self._backend.get_subscription_url(username=username)

    async def delete_user(self, username: str | None) -> None:
        """Delete user via active panel backend."""
        await self._backend.delete_user(username=username)

    async def close(self) -> None:
        """Close active panel backend client."""
        await self._backend.close()


def get_panel_service(panel_type: str | None = None) -> BasePanelService:
    """Return default panel service facade."""
    return PanelService(panel_type=panel_type)


__all__ = [
    "BasePanelService",
    "MarzbanService",
    "PanelService",
    "PanelServiceError",
    "PanelUserAlreadyExistsError",
    "RemnawaveService",
    "create_panel_backend",
    "get_panel_service",
]
