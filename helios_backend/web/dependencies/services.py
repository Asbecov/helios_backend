"""Service dependency providers for API handlers."""

from helios_backend.services.auth.jwt import JwtService
from helios_backend.services.auth.telegram import TelegramAuthService
from helios_backend.services.balance.service import BalanceService
from helios_backend.services.codes.service import CodeService
from helios_backend.services.marzban.service import MarzbanService
from helios_backend.services.payments.service import PaymentService
from helios_backend.services.plans.service import PlanService
from helios_backend.services.users.service import UserService


def get_jwt_service() -> JwtService:
    """Provide JWT service instance."""
    return JwtService()


def get_telegram_auth_service() -> TelegramAuthService:
    """Provide Telegram auth service instance."""
    return TelegramAuthService()


def get_user_service() -> UserService:
    """Provide user service instance."""
    return UserService()


def get_plan_service() -> PlanService:
    """Provide plan service instance."""
    return PlanService()


def get_payment_service() -> PaymentService:
    """Provide payment service instance."""
    return PaymentService()


def get_balance_service() -> BalanceService:
    """Provide balance service instance."""
    return BalanceService()


def get_marzban_service() -> MarzbanService:
    """Provide Marzban service instance."""
    return MarzbanService()


def get_code_service() -> CodeService:
    """Provide code service instance."""
    return CodeService()
