import hashlib
import hmac
from datetime import datetime
from uuid import UUID

from helios_backend.db.dao.vpn.code_dao import CodeDao
from helios_backend.db.models.vpn.code import Code
from helios_backend.db.models.vpn.code_usage import CodeUsage
from helios_backend.db.models.vpn.user import User
from helios_backend.settings import settings


class CodeService:
    """Code validation and usage service."""

    def __init__(self, code_dao: CodeDao | None = None) -> None:
        """Initialize code service."""
        self._code_dao = code_dao or CodeDao()

    async def resolve_valid_code(self, code: str | None, user_id: UUID) -> Code | None:
        """Handle resolve valid code."""
        if not code:
            return None
        return await self._code_dao.get_valid_code(code, user_id=user_id)

    async def consume(self, code: Code | None, user_id: UUID) -> None:
        """Handle consume."""
        if code is None:
            return
        await self._code_dao.create_usage(code=code, user_id=user_id)

    async def delete_user_referral_codes(self, user_id: UUID) -> None:
        """Handle delete user referral codes."""
        await self._code_dao.delete_referrals_by_owner(user_id)

    async def get_referral_usages_by_user(self, owner_user_id: UUID) -> list[CodeUsage]:
        """Handle get referral usages by user."""
        return await self._code_dao.get_referral_usages_by_owner(owner_user_id)

    async def get_or_create_user_referral_code(
        self,
        user: User,
        discount_percent: int = 10,
        reward_days_percent: int = 10,
        expires_at: datetime | None = None,
    ) -> Code:
        """Handle get or create user referral code."""
        if discount_percent < 0 or discount_percent > 100:
            msg = "discount_percent must be between 0 and 100"
            raise ValueError(msg)
        if reward_days_percent < 0 or reward_days_percent > 100:
            msg = "reward_days_percent must be between 0 and 100"
            raise ValueError(msg)

        existing = await self._code_dao.get_referral_by_owner(user.id)
        if existing is not None:
            return existing

        for attempt in range(100):
            candidate = self._generate_referral_candidate(user.id, attempt)
            try:
                return await self._code_dao.create_referral_code(
                    owner=user,
                    raw_code=candidate,
                    discount_percent=discount_percent,
                    reward_days_percent=reward_days_percent,
                    expires_at=expires_at,
                )
            except ValueError:
                # If code exists due to race, check owner code and return it.
                existing_after_conflict = await self._code_dao.get_referral_by_owner(
                    user.id
                )
                if existing_after_conflict is not None:
                    return existing_after_conflict
                continue

        msg = "failed to create referral code"
        raise ValueError(msg)

    def _generate_referral_candidate(self, user_id: UUID, attempt: int) -> str:
        """Handle generate referral candidate."""
        digest = hmac.new(
            key=settings.jwt_secret.encode("utf-8"),
            msg=f"{user_id.hex}:{attempt}".encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()
        numeric = int(digest[:12], 16) % 1_000_000
        return f"{numeric:06d}"
