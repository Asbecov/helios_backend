import uuid
from datetime import datetime

from tortoise import fields, models
from tortoise.fields.relational import ForeignKeyNullableRelation

from helios_backend.db.models.vpn.user import User


class BasePlanGrant(models.Model):
    """Tracks one-time base-plan grants by Telegram identity."""

    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    telegram_id = fields.BigIntField(unique=True)
    user: ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="base_plan_grants",
        null=True,
        on_delete=fields.SET_NULL,
    )
    granted_at: datetime = fields.DatetimeField(auto_now_add=True)

    class Meta:
        """Represent meta."""

        table = "base_plan_grants"
