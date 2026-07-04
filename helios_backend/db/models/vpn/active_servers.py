from datetime import date

from tortoise import Model, fields


class ActiveServer(Model):
    """ActiveServer represents an active VPN server."""

    id = fields.IntField(pk=True)
    server_name = fields.CharField(max_length = 4096)
    server_address = fields.CharField(max_length = 4096, unique = True)
    added_at: date = fields.DateField(default=date.today)

    class Meta(Model.Meta):
        """Represents Active Server class meta."""

        table = "active_server"

    def __str__(self) -> str:
        """Return compact representation for logs and debugging."""
        return f"ActiveServer(proxy={self.server_address})"


