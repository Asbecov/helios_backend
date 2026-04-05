import uuid

from tortoise import fields, models
from tortoise.fields.relational import ForeignKeyRelation

from helios_backend.db.models.vpn.code import Code
from helios_backend.db.models.vpn.user import User


class CodeUsage(models.Model):
    """Tracks per-user code usage to enforce one-time usage per code per user."""

    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user: ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="code_usages",
    )
    code: ForeignKeyRelation[Code] = fields.ForeignKeyField(
        "models.Code",
        related_name="usages",
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        """Represent meta."""

        table = "code_usages"
        unique_together = (("user", "code"),)
