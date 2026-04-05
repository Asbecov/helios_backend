import enum
import uuid

from tortoise import fields, models
from tortoise.fields.relational import ForeignKeyNullableRelation

from helios_backend.db.models.vpn.user import User


class CodeType(enum.StrEnum):
    """Unified code types."""

    PROMO = "PROMO"
    REFERRAL = "REFERRAL"


class Code(models.Model):
    """Unified promo and referral code model."""

    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    code = fields.CharField(max_length=64, unique=True)
    type = fields.CharEnumField(CodeType)
    owner: ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User",
        null=True,
        related_name="codes",
    )
    discount_percent = fields.IntField(null=True)
    reward_days_percent = fields.IntField(null=True)
    expires_at = fields.DatetimeField(null=True)
    is_active = fields.BooleanField(default=True)

    class Meta:
        """Represent meta."""

        table = "codes"

    def __str__(self) -> str:
        """Return a string representation of code."""
        return self.code
