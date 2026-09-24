import hmac
import logging
from uuid import UUID

from fastadmin import TortoiseModelAdmin, action, register
from fastadmin import fastapi_app as admin_app
from fastapi import FastAPI

from helios_backend.db.models import ActiveServer
from helios_backend.db.models.vpn.active_proxies import ActiveProxy
from helios_backend.db.models.vpn.admin_account import AdminAccount
from helios_backend.db.models.vpn.balance import Balance
from helios_backend.db.models.vpn.base_plan_grant import BasePlanGrant
from helios_backend.db.models.vpn.code import Code
from helios_backend.db.models.vpn.code_usage import CodeUsage
from helios_backend.db.models.vpn.payment import Payment
from helios_backend.db.models.vpn.runtime_setting import RuntimeSetting
from helios_backend.db.models.vpn.subscription_plan import SubscriptionPlan
from helios_backend.db.models.vpn.user import User
from helios_backend.services.admin.batch_balance_service import BatchBalanceService
from helios_backend.services.auth.passwords import (
    hash_password,
    is_password_hash,
    verify_password,
)
from helios_backend.settings import settings

logger = logging.getLogger(__name__)
_bootstrap_state = {"done": False}
batch_balance_service = BatchBalanceService()


class HeliosTortoiseModelAdmin(TortoiseModelAdmin):
    """Allow relation lookup search fields for FastAdmin list validation."""

    relation_sort_fields: dict[str, str] = {}

    def get_fields_for_serialize(self) -> set[str]:
        """Expose valid relation lookup search fields to FastAdmin validators."""
        fields_for_serialize = super().get_fields_for_serialize()
        model_fields = {
            field.name for field in self.get_model_fields_with_widget_types()
        }

        for field in self.search_fields:
            if "__" not in field:
                continue
            relation_root = field.split("__", 1)[0]
            if relation_root in model_fields:
                fields_for_serialize.add(field)

        return fields_for_serialize

    def resolve_sort_by(self, sort_by: str) -> str:
        """Ensure relation fields are mapped to sortable ORM expressions."""
        resolved = super().resolve_sort_by(sort_by)
        if not resolved:
            return resolved

        prefix = "-" if resolved.startswith("-") else ""
        field_name = resolved.lstrip("-")

        mapped_field = self.relation_sort_fields.get(field_name)
        if mapped_field:
            return f"{prefix}{mapped_field}"

        if "__" in field_name:
            return resolved

        orm_field = self.model_cls._meta.fields_map.get(field_name)
        if orm_field and orm_field.__class__.__name__ in (
            "ForeignKeyFieldInstance",
            "OneToOneFieldInstance",
        ):
            return f"{prefix}{field_name}_id"

        return resolved

@register(ActiveServer)
class ActiveServerModelAdmin(HeliosTortoiseModelAdmin):
    """Admin interface for active servers."""\

    menu_section = "Servers"
    list_display = ("id", "server_name", "server_address", "added_at")
    list_display_links = ("id", "server_name", "server_address")
    search_fields = ("server_name",)
    readonly_fields = ("added_at",)

@register(ActiveProxy)
class ActiveProxyModelAdmin(HeliosTortoiseModelAdmin):
    """Admin interface for active proxies."""

    menu_section = "Proxies"
    list_display = ("id", "proxy", "added_at")
    list_display_links = ("id", "proxy")
    search_fields = ("proxy",)
    readonly_fields = ("added_at",)


@register(AdminAccount)
class AdminAccountModelAdmin(HeliosTortoiseModelAdmin):
    """Admin users used to authenticate into FastAdmin."""

    menu_section = "Administration"
    list_display = ("id", "username", "created_at")
    list_display_links = ("id", "username")
    search_fields = ("username",)
    readonly_fields = ("created_at",)

    async def authenticate(self, username: str, password: str) -> int | None:
        """Authenticate admin account and return primary key on success."""
        account = await self.model_cls.filter(username=username).first()
        if account is None:
            return None

        if verify_password(password, account.password):
            return account.id

        # Backward compatibility for legacy plaintext records before hashing.
        if not is_password_hash(account.password) and hmac.compare_digest(
            account.password,
            password,
        ):
            account.password = hash_password(password)
            await account.save(update_fields=["password"])
            logger.info(
                "Migrated plaintext admin password to hash for %s",
                account.username,
            )
            return account.id

        return None

    async def change_password(self, id: int | str, password: str) -> None:
        """Update admin password."""
        account = await self.model_cls.filter(id=id).first()
        if account is None:
            msg = "admin account not found"
            raise ValueError(msg)
        account.password = hash_password(password)
        await account.save(update_fields=["password"])


@register(User)
class UserModelAdmin(HeliosTortoiseModelAdmin):
    """Admin interface for users that represent customers of the VPN service."""

    menu_section = "Users"
    list_display = ("id", "telegram_id", "username", "marzban_username", "created_at")
    list_display_links = ("id", "telegram_id")
    search_fields = ("id", "telegram_id", "username", "marzban_username")
    readonly_fields = ("created_at",)
    actions = (
        "add_5_days",
        "add_10_days",
        "add_30_days",
        "add_5_days_all",
        "add_10_days_all",
        "add_30_days_all",
        "add_custom_days_settings",
        "add_custom_days_settings_all",
    )
    actions_on_top = True
    actions_on_bottom = True
    actions_selection_counter = True

    @action(description="➕ Добавить 5 дней к балансу (выбранным)")
    async def add_5_days(self, ids: list[UUID | int]) -> None:
        """Add 5 days to selected users."""
        await batch_balance_service.add_days_to_users(days=5, user_ids=ids)

    @action(description="➕ Добавить 10 дней к балансу (выбранным)")
    async def add_10_days(self, ids: list[UUID | int]) -> None:
        """Add 10 days to selected users."""
        await batch_balance_service.add_days_to_users(days=10, user_ids=ids)

    @action(description="➕ Добавить 30 дней к балансу (выбранным)")
    async def add_30_days(self, ids: list[UUID | int]) -> None:
        """Add 30 days to selected users."""
        await batch_balance_service.add_days_to_users(days=30, user_ids=ids)

    @action(description="🌐 Добавить 5 дней к балансу (всем пользователям)")
    async def add_5_days_all(self, ids: list[UUID | int]) -> None:
        """Add 5 days to all users in database."""
        await batch_balance_service.add_days_to_users(days=5, user_ids=None)

    @action(description="🌐 Добавить 10 дней к балансу (всем пользователям)")
    async def add_10_days_all(self, ids: list[UUID | int]) -> None:
        """Add 10 days to all users in database."""
        await batch_balance_service.add_days_to_users(days=10, user_ids=None)

    @action(description="🌐 Добавить 30 дней к балансу (всем пользователям)")
    async def add_30_days_all(self, ids: list[UUID | int]) -> None:
        """Add 30 days to all users in database."""
        await batch_balance_service.add_days_to_users(days=30, user_ids=None)

    @action(description="⚙️ Добавить дни из Runtime Settings (выбранным)")
    async def add_custom_days_settings(self, ids: list[UUID | int]) -> None:
        """Add custom days configured in RuntimeSetting to selected users."""
        days = await batch_balance_service.get_custom_days_from_settings()
        await batch_balance_service.add_days_to_users(days=days, user_ids=ids)

    @action(description="⚙️ Добавить дни из Runtime Settings (всем пользователям)")
    async def add_custom_days_settings_all(self, ids: list[UUID | int]) -> None:
        """Add custom days configured in RuntimeSetting to all users."""
        days = await batch_balance_service.get_custom_days_from_settings()
        await batch_balance_service.add_days_to_users(days=days, user_ids=None)


@register(Balance)
class BalanceModelAdmin(HeliosTortoiseModelAdmin):
    """Admin interface for user balances."""

    menu_section = "Subscriptions"
    relation_sort_fields = {"user": "user__telegram_id"}
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
    search_fields = (
        "user__telegram_id",
        "user__username",
        "user__marzban_username",
    )
    actions = (
        "add_5_days",
        "add_10_days",
        "add_30_days",
        "add_5_days_all",
        "add_10_days_all",
        "add_30_days_all",
        "add_custom_days_settings",
        "add_custom_days_settings_all",
        "freeze_subscriptions",
        "activate_subscriptions",
    )
    actions_on_top = True
    actions_on_bottom = True
    actions_selection_counter = True

    @action(description="➕ Добавить 5 дней (выбранным балансам)")
    async def add_5_days(self, ids: list[UUID | int]) -> None:
        """Add 5 days to selected balances."""
        await batch_balance_service.add_days_to_balances(days=5, balance_ids=ids)

    @action(description="➕ Добавить 10 дней (выбранным балансам)")
    async def add_10_days(self, ids: list[UUID | int]) -> None:
        """Add 10 days to selected balances."""
        await batch_balance_service.add_days_to_balances(days=10, balance_ids=ids)

    @action(description="➕ Добавить 30 дней (выбранным балансам)")
    async def add_30_days(self, ids: list[UUID | int]) -> None:
        """Add 30 days to selected balances."""
        await batch_balance_service.add_days_to_balances(days=30, balance_ids=ids)

    @action(description="🌐 Добавить 5 дней (всем балансам)")
    async def add_5_days_all(self, ids: list[UUID | int]) -> None:
        """Add 5 days to all balances in database."""
        await batch_balance_service.add_days_to_balances(days=5, balance_ids=None)

    @action(description="🌐 Добавить 10 дней (всем балансам)")
    async def add_10_days_all(self, ids: list[UUID | int]) -> None:
        """Add 10 days to all balances in database."""
        await batch_balance_service.add_days_to_balances(days=10, balance_ids=None)

    @action(description="🌐 Добавить 30 дней (всем балансам)")
    async def add_30_days_all(self, ids: list[UUID | int]) -> None:
        """Add 30 days to all balances in database."""
        await batch_balance_service.add_days_to_balances(days=30, balance_ids=None)

    @action(description="⚙️ Добавить дни из Runtime Settings (выбранным балансам)")
    async def add_custom_days_settings(self, ids: list[UUID | int]) -> None:
        """Add custom days configured in RuntimeSetting to selected balances."""
        days = await batch_balance_service.get_custom_days_from_settings()
        await batch_balance_service.add_days_to_balances(days=days, balance_ids=ids)

    @action(description="⚙️ Добавить дни из Runtime Settings (всем балансам)")
    async def add_custom_days_settings_all(self, ids: list[UUID | int]) -> None:
        """Add custom days configured in RuntimeSetting to all balances."""
        days = await batch_balance_service.get_custom_days_from_settings()
        await batch_balance_service.add_days_to_balances(days=days, balance_ids=None)

    @action(description="❄️ Заморозить подписку (выбранным)")
    async def freeze_subscriptions(self, ids: list[UUID | int]) -> None:
        """Freeze selected subscriptions."""
        await batch_balance_service.freeze_balances(balance_ids=ids)

    @action(description="⚡ Активировать подписку (выбранным)")
    async def activate_subscriptions(self, ids: list[UUID | int]) -> None:
        """Activate selected subscriptions."""
        await batch_balance_service.activate_balances(balance_ids=ids)


@register(SubscriptionPlan)
class SubscriptionPlanModelAdmin(HeliosTortoiseModelAdmin):
    """Admin interface for subscription plans."""

    menu_section = "Subscriptions"
    list_display = ("id", "name", "duration_days", "price", "is_base")
    list_display_links = ("id", "name")
    list_filter = ("is_base",)
    search_fields = ("name",)


@register(Payment)
class PaymentModelAdmin(HeliosTortoiseModelAdmin):
    """Admin interface for payments."""

    menu_section = "Payments"
    relation_sort_fields = {"user": "user__telegram_id", "plan": "plan__name"}
    list_display = ("id", "user", "plan", "amount", "status", "provider", "created_at")
    list_display_links = ("id", "external_id")
    list_filter = ("status", "provider")
    search_fields = (
        "external_id",
        "user__telegram_id",
        "user__username",
        "user__marzban_username",
    )


@register(Code)
class CodeModelAdmin(HeliosTortoiseModelAdmin):
    """Admin interface for promotional codes."""

    menu_section = "Promotions"
    relation_sort_fields = {"owner": "owner__telegram_id"}
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
    search_fields = (
        "code",
        "owner__telegram_id",
        "owner__username",
        "owner__marzban_username",
    )


@register(CodeUsage)
class CodeUsageModelAdmin(HeliosTortoiseModelAdmin):
    """Admin interface for tracking the usage of promotional codes."""

    menu_section = "Promotions"
    relation_sort_fields = {"user": "user__telegram_id", "code": "code__code"}
    list_display = ("id", "user", "code", "created_at")
    list_display_links = ("id",)
    search_fields = (
        "user__telegram_id",
        "user__username",
        "user__marzban_username",
        "code__code",
    )


@register(BasePlanGrant)
class BasePlanGrantModelAdmin(HeliosTortoiseModelAdmin):
    """Admin interface for grants of base subscription plans."""

    menu_section = "Subscriptions"
    relation_sort_fields = {"user": "user__telegram_id"}
    list_display = ("id", "telegram_id", "user", "granted_at")
    list_display_links = ("id", "telegram_id")
    search_fields = (
        "telegram_id",
        "user__telegram_id",
        "user__username",
        "user__marzban_username",
    )


@register(RuntimeSetting)
class RuntimeSettingModelAdmin(HeliosTortoiseModelAdmin):
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
        await AdminAccount.create(username=username, password=hash_password(password))
        logger.info("Bootstrap admin account created for FastAdmin panel")
    elif not verify_password(password, account.password):
        account.password = hash_password(password)
        await account.save(update_fields=["password"])
        logger.info("Bootstrap admin account password synchronized for FastAdmin panel")

    _bootstrap_state["done"] = True
