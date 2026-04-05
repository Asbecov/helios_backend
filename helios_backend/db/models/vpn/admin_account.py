from datetime import datetime

from fastapi_admin.models import AbstractAdmin
from tortoise import fields


class AdminAccount(AbstractAdmin):
    """Credentials used by FastAPI-Admin panel login provider."""

    created_at: datetime = fields.DatetimeField(auto_now_add=True)

    class Meta:
        """Represent meta."""

        table = "admin_accounts"

    def __str__(self) -> str:
        """Return compact representation for logs and debugging."""
        return f"AdminAccount(username={self.username})"
