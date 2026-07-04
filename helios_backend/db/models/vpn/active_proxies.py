from datetime import datetime

from tortoise import fields, models


class ActiveProxy(models.Model):
    """ActiveProxy represents a currently active proxy in the system."""

    id = fields.IntField(pk=True)
    proxy = fields.CharField(max_length = 4096, unique = True)
    added_at: datetime = fields.DatetimeField(auto_now_add=True)

    class Meta(models.Model.Meta):
        """Represent meta."""

        table = "active_proxies"

    def __str__(self) -> str:
        """Return compact representation for logs and debugging."""
        return f"ActiveProxy(proxy={self.proxy})"