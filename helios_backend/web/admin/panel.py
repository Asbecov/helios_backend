# ruff: noqa: PLC0415

import logging
from typing import Any

from fastapi import FastAPI

from helios_backend.db.models.vpn.admin_account import AdminAccount
from helios_backend.db.models.vpn.balance import Balance
from helios_backend.db.models.vpn.code import Code
from helios_backend.db.models.vpn.payment import Payment
from helios_backend.db.models.vpn.runtime_setting import RuntimeSetting
from helios_backend.db.models.vpn.subscription_plan import SubscriptionPlan
from helios_backend.db.models.vpn.user import User
from helios_backend.settings import settings

logger = logging.getLogger(__name__)

_resource_state = {"registered": False}


def mount_admin_panel(app: FastAPI) -> None:
    """Mount FastAPI-Admin app at /admin when enabled."""
    if not settings.admin_panel_enabled or settings.environment.lower() == "pytest":
        return

    from fastapi_admin.app import app as admin_app

    app.mount("/admin", admin_app)


async def configure_admin_panel(app: FastAPI) -> None:
    """Configure FastAPI-Admin providers/resources using app Redis client."""
    if not settings.admin_panel_enabled or settings.environment.lower() == "pytest":
        return

    from fastapi_admin.app import app as admin_app
    from fastapi_admin.providers.login import UsernamePasswordProvider

    _register_resources()

    provider = UsernamePasswordProvider(
        admin_model=AdminAccount,
        login_title="Helios Admin",
    )
    await admin_app.configure(
        logo_url="https://tabler.io/static/logo-white.svg",
        providers=[provider],
        redis=app.state.redis,
    )

    await _bootstrap_admin(provider)


async def _bootstrap_admin(provider: Any) -> None:
    """Create initial admin panel account from environment when absent."""
    username = settings.admin_panel_username
    password = settings.admin_panel_password
    if not username or not password:
        return

    exists = await AdminAccount.all().limit(1).exists()
    if exists:
        return

    await provider.create_user(username=username, password=password)
    logger.info("Bootstrap admin account created for FastAPI-Admin panel")


def _register_resources() -> None:
    """Register admin panel resources exactly once."""
    if _resource_state["registered"]:
        return

    from fastapi_admin.app import app as admin_app
    from fastapi_admin.resources import Link, Model

    @admin_app.register
    class Dashboard(Link):
        label = "Dashboard"
        icon = "fas fa-home"
        url = "/admin"

    @admin_app.register
    class UserResource(Model):
        label = "Users"
        model = User
        fields = (
            "id",
            "telegram_id",
            "username",
            "created_at",
            "marzban_username",
        )

    @admin_app.register
    class BalanceResource(Model):
        label = "Balances"
        model = Balance
        fields = (
            "id",
            "user",
            "remaining_frozen_days",
            "is_frozen",
            "frozen_at",
            "expires_at",
            "activated_at",
            "created_at",
        )

    @admin_app.register
    class PlanResource(Model):
        label = "Plans"
        model = SubscriptionPlan
        fields = ("id", "name", "duration_days", "price", "is_base", "tags")

    @admin_app.register
    class PaymentResource(Model):
        label = "Payments"
        model = Payment
        fields = (
            "id",
            "user",
            "plan",
            "code",
            "amount",
            "status",
            "provider",
            "external_id",
            "created_at",
        )

    @admin_app.register
    class CodeResource(Model):
        label = "Codes"
        model = Code
        fields = (
            "id",
            "code",
            "type",
            "owner",
            "discount_percent",
            "reward_days_percent",
            "expires_at",
            "is_active",
        )

    @admin_app.register
    class RuntimeSettingResource(Model):
        label = "Runtime Settings"
        model = RuntimeSetting
        fields = ("id", "key", "value", "created_at", "updated_at")

    @admin_app.register
    class AdminAccountResource(Model):
        label = "Admin Accounts"
        model = AdminAccount
        fields = ("id", "username", "password", "created_at")

    _resource_state["registered"] = True
