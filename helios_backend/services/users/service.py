import secrets
import string
from uuid import UUID

from helios_backend.db.dao.vpn.base_plan_grant_dao import BasePlanGrantDao
from helios_backend.db.dao.vpn.user_dao import UserDao
from helios_backend.db.models.vpn.subscription_plan import SubscriptionPlan
from helios_backend.db.models.vpn.user import User
from helios_backend.services.balance.service import BalanceService
from helios_backend.services.codes.service import CodeService
from helios_backend.services.marzban.service import MarzbanService
from helios_backend.services.plans.service import PlanService


class UserService:
    """User data operations."""

    def __init__(
        self,
        user_dao: UserDao | None = None,
        base_plan_grant_dao: BasePlanGrantDao | None = None,
        balance_service: BalanceService | None = None,
        plan_service: PlanService | None = None,
        code_service: CodeService | None = None,
        marzban_service: MarzbanService | None = None,
    ) -> None:
        """Initialize user service."""
        self._user_dao = user_dao or UserDao()
        self._base_plan_grant_dao = base_plan_grant_dao or BasePlanGrantDao()
        self._balance_service = balance_service or BalanceService()
        self._plan_service = plan_service or PlanService()
        self._code_service = code_service or CodeService()
        self._marzban_service = marzban_service or MarzbanService()

    async def _generate_unique_marzban_username(self, stem: str) -> str:
        """Handle generate unique marzban username."""
        base = f"u_{stem}"
        if not await self._user_dao.marzban_username_exists(base):
            return base

        for _ in range(10):
            suffix = "".join(
                secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6)
            )
            candidate = f"{base}_{suffix}"
            if not await self._user_dao.marzban_username_exists(candidate):
                return candidate

        msg = "failed to allocate marzban username"
        raise ValueError(msg)

    async def get_or_create_telegram_user(
        self,
        telegram_id: int,
        username: str | None,
    ) -> User:
        """Handle get or create telegram user."""
        user = await self._user_dao.get_by_telegram_id(telegram_id)
        if user:
            if username is not None and user.username != username:
                user.username = username
                await user.save(update_fields=["username"])
            return user

        created = await self._user_dao.create(
            telegram_id=telegram_id,
            username=username,
        )

        is_first_grant = await self._base_plan_grant_dao.record_if_absent(
            telegram_id=telegram_id,
            user_id=created.id,
        )
        if is_first_grant:
            base_plan: SubscriptionPlan = await self._plan_service.get_base_plan()
            await self._balance_service.apply_plan(created, base_plan)

        await self._code_service.get_or_create_user_referral_code(created)

        return created

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Handle get user by id."""
        return await self._user_dao.get_by_id(user_id)

    async def get_or_create_marzban_username(self, user: User) -> str:
        """Handle get or create marzban username."""
        if user.marzban_username:
            return user.marzban_username

        stem = str(user.username).replace("-", "")
        allocated = await self._generate_unique_marzban_username(stem)
        user.marzban_username = allocated
        await user.save(update_fields=["marzban_username"])
        return allocated

    async def delete_user(self, user: User) -> None:
        """Handle delete user."""
        await self._code_service.delete_user_referral_codes(user.id)
        await self._marzban_service.delete_user(
            user.marzban_username
        )  # Does nothing if marzban_username is None.
        await self._balance_service.delete_user_balance(user)
        await self._user_dao.delete(user)
