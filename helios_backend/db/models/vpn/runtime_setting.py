import uuid
from datetime import datetime
from typing import Any

from tortoise import fields, models


class RuntimeSetting(models.Model):
    """Mutable operational settings persisted in database."""

    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    key = fields.CharField(max_length=120, unique=True)
    value: fields.Field[Any] = fields.JSONField()
    created_at: datetime = fields.DatetimeField(auto_now_add=True)
    updated_at: datetime = fields.DatetimeField(auto_now=True)

    class Meta:
        """Represent meta."""

        table = "runtime_settings"

    def __str__(self) -> str:
        """Return key-based representation for diagnostics."""
        return f"RuntimeSetting(key={self.key})"
