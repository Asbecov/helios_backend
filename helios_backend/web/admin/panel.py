import logging

from fastadmin import TortoiseModelAdmin, register
from fastadmin import fastapi_app as admin_app
from fastapi import FastAPI

from helios_backend.db.models.vpn.admin_account import AdminAccount
from helios_backend.db.models.vpn.balance import Balance
from helios_backend.db.models.vpn.base_plan_grant import BasePlanGrant
from helios_backend.db.models.vpn.code import Code
from helios_backend.db.models.vpn.code_usage import CodeUsage
from helios_backend.db.models.vpn.payment import Payment
from helios_backend.db.models.vpn.runtime_setting import RuntimeSetting
from helios_backend.db.models.vpn.subscription_plan import SubscriptionPlan
from helios_backend.db.models.vpn.user import User
from helios_backend.settings import settings

logger = logging.getLogger(__name__)
_bootstrap_state = {"done": False}


@register(AdminAccount)
class AdminAccountModelAdmin(TortoiseModelAdmin):
    """Admin users used to authenticate into FastAdmin."""

    menu_section = "Administration"
    list_display = ("id", "username", "created_at")
    list_display_links = ("id", "username")
    search_fields = ("username",)
    readonly_fields = ("created_at",)

    async def authenticate(self, username: str, password: str) -> int | None:
        """Authenticate admin account and return primary key on success."""
        account = await self.model_cls.filter(username=username).first()
        if not account or account.password != password:
            return None
        return account.id

    async def change_password(self, id: int | str, password: str) -> None:
        """Update admin password."""
        account = await self.model_cls.filter(id=id).first()
        if account is None:
            msg = "admin account not found"
            raise ValueError(msg)
        account.password = password
        await account.save(update_fields=["password"])


@register(User)
class UserModelAdmin(TortoiseModelAdmin):
    """Admin interface for users that represent customers of the VPN service."""

    menu_section = "Users"
    list_display = ("id", "telegram_id", "username", "marzban_username", "created_at")
    list_display_links = ("id", "telegram_id")
    search_fields = ("username", "marzban_username")
    readonly_fields = ("created_at",)


@register(Balance)
class BalanceModelAdmin(TortoiseModelAdmin):
    """Admin interface for user balances."""

    menu_section = "Subscriptions"
    list_display = (
        "id",
        "user",
        "remaining_frozen_days",
        "is_frozen",
        "frozen_at",
        "expires_at",
        "created_at",
    )
    list_display_links = ("id", "user")
    list_filter = ("is_frozen",)


@register(SubscriptionPlan)
class SubscriptionPlanModelAdmin(TortoiseModelAdmin):
    """Admin interface for subscription plans."""

    menu_section = "Subscriptions"
    list_display = ("id", "name", "duration_days", "price", "is_base")
    list_display_links = ("id", "name")
    list_filter = ("is_base",)
    search_fields = ("name",)


@register(Payment)
class PaymentModelAdmin(TortoiseModelAdmin):
    """Admin interface for payments."""

    menu_section = "Payments"
    list_display = ("id", "user", "plan", "amount", "status", "provider", "created_at")
    list_display_links = ("id", "external_id")
    list_filter = ("status", "provider")
    search_fields = ("external_id",)


@register(Code)
class CodeModelAdmin(TortoiseModelAdmin):
    """Admin interface for promotional codes."""

    menu_section = "Promotions"
    list_display = (
        "id",
        "code",
        "type",
        "owner",
        "discount_percent",
        "reward_days_percent",
        "is_active",
        "expires_at",
    )
    list_display_links = ("id", "code")
    list_filter = ("type", "is_active")
    search_fields = ("code",)


@register(CodeUsage)
class CodeUsageModelAdmin(TortoiseModelAdmin):
    """Admin interface for tracking the usage of promotional codes."""

    menu_section = "Promotions"
    list_display = ("id", "user", "code", "created_at")
    list_display_links = ("id",)


@register(BasePlanGrant)
class BasePlanGrantModelAdmin(TortoiseModelAdmin):
    """Admin interface for grants of base subscription plans."""

    menu_section = "Subscriptions"
    list_display = ("id", "telegram_id", "user", "granted_at")
    list_display_links = ("id", "telegram_id")


@register(RuntimeSetting)
class RuntimeSettingModelAdmin(TortoiseModelAdmin):
    """Admin interface for runtime settings."""

    menu_section = "Configuration"
    list_display = ("id", "key", "value", "updated_at")
    list_display_links = ("id", "key")
    search_fields = ("key",)


def mount_admin_panel(app: FastAPI) -> None:
    """Mount FastAdmin application to the main FastAPI app."""
    if settings.environment.lower() == "pytest":
        return

    app.mount("/admin", admin_app)


async def configure_admin_panel(_: FastAPI) -> None:
    """Bootstrap initial admin account when credentials are configured."""
    if settings.environment.lower() == "pytest":
        return

    if _bootstrap_state["done"]:
        return

    username = settings.admin_panel_username
    password = settings.admin_panel_password
    if not username or not password:
        _bootstrap_state["done"] = True
        return

    account = await AdminAccount.filter(username=username).first()
    if account is None:
        await AdminAccount.create(username=username, password=password)
        logger.info("Bootstrap admin account created for FastAdmin panel")
    elif account.password != password:
        account.password = password
        await account.save(update_fields=["password"])
        logger.info("Bootstrap admin account password synchronized for FastAdmin panel")

    _bootstrap_state["done"] = True
