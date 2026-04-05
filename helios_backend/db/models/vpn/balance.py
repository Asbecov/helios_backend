"""Balance model storing frozen and active subscription timing."""

import uuid
from datetime import datetime

from tortoise import fields, models
from tortoise.fields.relational import ForeignKeyRelation

from helios_backend.db.models.vpn.user import User


class Balance(models.Model):
    """User remaining days balance for VPN access."""

    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user: ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="balances",
        unique=True,
    )
    remaining_frozen_days: int = fields.IntField(default=0)
    is_frozen = fields.BooleanField(default=True)
    frozen_at: datetime = fields.DatetimeField(auto_now_add=True)
    expires_at: datetime | None = fields.DatetimeField(null=True)
    activated_at: datetime | None = fields.DatetimeField(null=True)
    created_at: datetime = fields.DatetimeField(auto_now_add=True)

    class Meta:
        """Represent meta."""

        table = "balances"

    def __str__(self) -> str:
        """Return a compact debug representation for logging and admin views."""
        return (
            "Balance("
            f"id={self.id}, "
            f"remaining_frozen_days={self.remaining_frozen_days}, "
            f"is_frozen={self.is_frozen})"
        )
