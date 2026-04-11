"""Internal admin panel integration helpers."""

import os

from helios_backend.settings import settings


def _apply_fastadmin_env() -> None:
    """Populate FastAdmin env vars before FastAdmin modules are imported."""
    env_map = {
        "ADMIN_PREFIX": "admin",
        "ADMIN_SITE_NAME": settings.admin_site_name,
        "ADMIN_USER_MODEL": "AdminAccount",
        "ADMIN_USER_MODEL_USERNAME_FIELD": "username",
        "ADMIN_SECRET_KEY": settings.admin_secret_key or settings.jwt_secret,
    }

    for key, value in env_map.items():
        if value and not os.environ.get(key):
            os.environ[key] = value


_apply_fastadmin_env()


__all__ = ["configure_admin_panel", "mount_admin_panel"]

from helios_backend.web.admin.panel import configure_admin_panel, mount_admin_panel
