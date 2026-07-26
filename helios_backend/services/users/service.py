import secrets
import string
from uuid import UUID

from tortoise.transactions import in_transaction

from helios_backend.db.dao.vpn.base_plan_grant_dao import BasePlanGrantDao
from helios_backend.db.dao.vpn.user_dao import UserDao
from helios_backend.db.models.vpn.balance import Balance
from helios_backend.db.models.vpn.base_plan_grant import BasePlanGrant
from helios_backend.db.models.vpn.code import Code
from helios_backend.db.models.vpn.code_usage import CodeUsage
from helios_backend.db.models.vpn.payment import Payment
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
            user_id=created.id,
            telegram_id=telegram_id,
        )
        if is_first_grant:
            base_plan: SubscriptionPlan = await self._plan_service.get_base_plan()
            await self._balance_service.apply_plan(created, base_plan)

        await self._code_service.get_or_create_user_referral_code(created)

        return created

    async def get_or_create_google_user(
        self,
        google_sub: str,
        google_email: str | None,
        username: str | None = None,
    ) -> User:
        """Handle get or create google user."""
        user = await self._user_dao.get_by_google_sub(google_sub)
        if user:
            updates = []
            if google_email is not None and user.google_email != google_email:
                user.google_email = google_email
                updates.append("google_email")
            if username is not None and user.username != username and not user.username:
                user.username = username
                updates.append("username")
            if updates:
                await user.save(update_fields=updates)
            return user

        created = await self._user_dao.create(
            google_sub=google_sub,
            google_email=google_email,
            username=username,
        )

        is_first_grant = await self._base_plan_grant_dao.record_if_absent(
            user_id=created.id,
            google_sub=google_sub,
        )
        if is_first_grant:
            base_plan: SubscriptionPlan = await self._plan_service.get_base_plan()
            await self._balance_service.apply_plan(created, base_plan)

        await self._code_service.get_or_create_user_referral_code(created)

        return created

    async def link_or_merge_telegram(
        self,
        current_user: User,
        telegram_id: int,
        username: str | None = None,
    ) -> tuple[str, User]:
        """Link Telegram identity to current_user or merge existing account."""
        if current_user.telegram_id == telegram_id:
            if username and current_user.username != username:
                current_user.username = username
                await current_user.save(update_fields=["username"])
            return "already_linked", current_user

        existing = await self._user_dao.get_by_telegram_id(telegram_id)
        if existing is None:
            current_user.telegram_id = telegram_id
            updates = ["telegram_id"]
            if username and not current_user.username:
                current_user.username = username
                updates.append("username")
            await current_user.save(update_fields=updates)
            return "linked", current_user

        if existing.id == current_user.id:
            return "already_linked", current_user

        merged = await self.merge_users(target_user=current_user, source_user=existing)
        return "merged", merged

    async def link_or_merge_google(
        self,
        current_user: User,
        google_sub: str,
        google_email: str | None = None,
    ) -> tuple[str, User]:
        """Link Google identity to current_user or merge existing account."""
        if current_user.google_sub == google_sub:
            if google_email and current_user.google_email != google_email:
                current_user.google_email = google_email
                await current_user.save(update_fields=["google_email"])
            return "already_linked", current_user

        existing = await self._user_dao.get_by_google_sub(google_sub)
        if existing is None:
            current_user.google_sub = google_sub
            updates = ["google_sub"]
            if google_email:
                current_user.google_email = google_email
                updates.append("google_email")
            await current_user.save(update_fields=updates)
            return "linked", current_user

        if existing.id == current_user.id:
            return "already_linked", current_user

        merged = await self.merge_users(target_user=current_user, source_user=existing)
        return "merged", merged

    async def merge_users(self, target_user: User, source_user: User) -> User:
        """Merge source_user into target_user, consolidating balances and resources atomically."""
        if target_user.id == source_user.id:
            return target_user

        async with in_transaction():
            # First, detach unique identity constraints from source_user to prevent DB unique constraint violations
            source_updates = []
            target_updates = []
            if source_user.telegram_id and not target_user.telegram_id:
                target_user.telegram_id = source_user.telegram_id
                source_user.telegram_id = None
                source_updates.append("telegram_id")
                target_updates.append("telegram_id")

            if source_user.google_sub and not target_user.google_sub:
                target_user.google_sub = source_user.google_sub
                source_user.google_sub = None
                source_updates.append("google_sub")
                target_updates.append("google_sub")

            if source_user.google_email and not target_user.google_email:
                target_user.google_email = source_user.google_email
                target_updates.append("google_email")

            if source_user.username and not target_user.username:
                target_user.username = source_user.username
                target_updates.append("username")

            if source_updates:
                await source_user.save(update_fields=source_updates)
            if target_updates:
                await target_user.save(update_fields=target_updates)

            # Merge balances
            source_balance = await Balance.filter(user=source_user).first()
            target_balance = await Balance.filter(user=target_user).first()
            if source_balance:
                if not target_balance:
                    source_balance.user = target_user
                    await source_balance.save(update_fields=["user_id"])
                else:
                    target_balance.remaining_frozen_days += source_balance.remaining_frozen_days
                    if source_balance.expires_at:
                        if target_balance.expires_at:
                            if source_balance.expires_at > target_balance.expires_at:
                                target_balance.expires_at = source_balance.expires_at
                        else:
                            target_balance.expires_at = source_balance.expires_at
                    await target_balance.save()
                    await source_balance.delete()

            # Reassign related models
            await Payment.filter(user=source_user).update(user=target_user)
            await Code.filter(owner=source_user).update(owner=target_user)
            await BasePlanGrant.filter(user=source_user).update(user=target_user)

            # Code usage records: only reassign if target hasn't used the same code
            source_usages = await CodeUsage.filter(user=source_user)
            for usage in source_usages:
                already_exists = await CodeUsage.filter(
                    user=target_user,
                    code_id=usage.code_id,
                ).exists()
                if not already_exists:
                    usage.user = target_user
                    await usage.save(update_fields=["user_id"])
                else:
                    await usage.delete()

            # Clean up source user referral codes and marzban if unused
            await self._code_service.delete_user_referral_codes(source_user.id)
            if source_user.marzban_username and source_user.marzban_username != target_user.marzban_username:
                await self._marzban_service.delete_user(source_user.marzban_username)

            await source_user.delete()

        return target_user

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Handle get user by id."""
        return await self._user_dao.get_by_id(user_id)

    async def get_or_create_marzban_username(self, user: User) -> str:
        """Handle get or create marzban username."""
        if user.marzban_username:
            return user.marzban_username

        stem = (
            (user.username or "").strip().replace("-", "")
            or (str(user.telegram_id) if user.telegram_id else None)
            or (user.google_sub[:12] if user.google_sub else str(user.id)[:8])
        )
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
