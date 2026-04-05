import uuid

from tortoise import fields, models


class SubscriptionPlan(models.Model):
    """Subscription plan entity."""

    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    name = fields.CharField(max_length=120, unique=True)
    duration_days = fields.IntField()
    price = fields.DecimalField(max_digits=12, decimal_places=2)
    is_base = fields.BooleanField(default=False)
    tags: fields.Field[dict[str, str]] = fields.JSONField(default=dict)

    class Meta:
        """Represent meta."""

        table = "subscription_plans"

    def __str__(self) -> str:
        """Return a string representation of subscription plan."""
        return self.name
