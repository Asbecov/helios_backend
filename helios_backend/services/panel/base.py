from abc import ABC, abstractmethod
from datetime import datetime


class PanelServiceError(RuntimeError):
    """Raised when panel operations fail."""


class PanelUserAlreadyExistsError(PanelServiceError):
    """Raised when panel create_user fails because user already exists."""


class BasePanelService(ABC):
    """Abstract base class for VPN panel integrations."""

    @abstractmethod
    async def create_user(self, username: str, expires_at: datetime) -> None:
        """Create a user in the panel."""

    @abstractmethod
    async def extend_user(self, username: str, expires_at: datetime) -> None:
        """Update user expiry in the panel."""

    @abstractmethod
    async def get_user_info(self, username: str) -> dict[str, str | int | None]:
        """Fetch user details from the panel."""

    @abstractmethod
    async def get_subscription_url(self, username: str) -> str | None:
        """Get user subscription URL from the panel."""

    @abstractmethod
    async def delete_user(self, username: str | None) -> None:
        """Delete user from the panel."""

    @abstractmethod
    async def close(self) -> None:
        """Close underlying panel API client resources."""
