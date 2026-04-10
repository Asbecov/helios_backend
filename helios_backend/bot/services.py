"""Service providers for Telegram bot handlers."""

from functools import lru_cache

from helios_backend.services.admin.runtime_settings import RuntimeSettingService
from helios_backend.services.balance.service import BalanceService
from helios_backend.services.codes.service import CodeService
from helios_backend.services.marzban.service import MarzbanService
from helios_backend.services.payments.service import PaymentService
from helios_backend.services.plans.service import PlanService
from helios_backend.services.users.service import UserService


@lru_cache
def get_user_service() -> UserService:
    """Provide user service instance."""
    return UserService()


@lru_cache
def get_balance_service() -> BalanceService:
    """Provide balance service instance."""
    return BalanceService()


@lru_cache
def get_plan_service() -> PlanService:
    """Provide plan service instance."""
    return PlanService()


@lru_cache
def get_payment_service() -> PaymentService:
    """Provide payment service instance."""
    return PaymentService()


@lru_cache
def get_marzban_service() -> MarzbanService:
    """Provide marzban service instance."""
    return MarzbanService()


@lru_cache
def get_runtime_setting_service() -> RuntimeSettingService:
    """Provide runtime setting service instance."""
    return RuntimeSettingService()


@lru_cache
def get_code_service() -> CodeService:
    """Provide code service instance."""
    return CodeService()
