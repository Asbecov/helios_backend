from datetime import datetime

from tortoise import fields, models


class AdminAccount(models.Model):
    """Credentials used by FastAdmin panel authentication."""

    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    password = fields.CharField(max_length=200)

    created_at: datetime = fields.DatetimeField(auto_now_add=True)

    class Meta:
        """Represent meta."""

        table = "admin_accounts"

    def __str__(self) -> str:
        """Return compact representation for logs and debugging."""
        return f"AdminAccount(username={self.username})"
