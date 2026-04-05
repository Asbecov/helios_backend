import enum
import uuid

from tortoise import fields, models
from tortoise.fields.relational import ForeignKeyNullableRelation

from helios_backend.db.models.vpn.code import Code
from helios_backend.db.models.vpn.subscription_plan import SubscriptionPlan
from helios_backend.db.models.vpn.user import User


class PaymentStatus(enum.StrEnum):
    """Supported payment statuses."""

    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


class Payment(models.Model):
    """Payment entity for subscription purchase attempts."""

    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    user: ForeignKeyNullableRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="payments",
    )
    plan: ForeignKeyNullableRelation[SubscriptionPlan] = fields.ForeignKeyField(
        "models.SubscriptionPlan",
        related_name="payments",
    )
    code: ForeignKeyNullableRelation[Code] = fields.ForeignKeyField(
        "models.Code",
        related_name="payments",
        null=True,
    )
    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    status = fields.CharEnumField(PaymentStatus, default=PaymentStatus.PENDING)
    provider = fields.CharField(max_length=64)
    external_id = fields.CharField(max_length=255, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        """Represent meta."""

        table = "payments"

    def __str__(self) -> str:
        """Return a string representation of payment."""
        return f"Payment(id={self.id}, status={self.status})"
