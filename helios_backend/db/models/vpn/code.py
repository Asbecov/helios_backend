import enum
import uuid
from typing import Any

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

    @staticmethod
    def _validate_percent(name: str, value: int | None) -> None:
        """Validate optional percentage field boundaries."""
        if value is None:
            return
        if value < 0 or value > 100:
            msg = f"{name} must be between 0 and 100"
            raise ValueError(msg)

    def validate_constraints(self) -> None:
        """Enforce logical code constraints in Python before persisting."""
        self._validate_percent("discount_percent", self.discount_percent)
        self._validate_percent("reward_days_percent", self.reward_days_percent)

        owner_id = getattr(self, "owner_id", None)
        if self.type is CodeType.PROMO and owner_id is not None:
            msg = "PROMO code must not have an owner"
            raise ValueError(msg)
        if self.type is CodeType.REFERRAL and owner_id is None:
            msg = "REFERRAL code must have an owner"
            raise ValueError(msg)

    async def save(self, *args: Any, **kwargs: Any) -> None:
        """Persist code after validating model-level constraints."""
        self.validate_constraints()
        await super().save(*args, **kwargs)
