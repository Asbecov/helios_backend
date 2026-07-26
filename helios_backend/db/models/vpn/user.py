import uuid

from tortoise import fields, models


class User(models.Model):
    """User profile for subscription management."""

    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    telegram_id = fields.BigIntField(unique=True, null=True)
    google_sub = fields.CharField(max_length=255, unique=True, null=True)
    google_email = fields.CharField(max_length=255, null=True)
    username = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    marzban_username = fields.CharField(max_length=120, unique=True, null=True)

    class Meta(models.Model.Meta):
        """Represent meta."""

        table = "users"

    def __str__(self) -> str:
        """Return a string representation of user."""
        return f"User(id={self.id}, telegram_id={self.telegram_id}, google_sub={self.google_sub})"
