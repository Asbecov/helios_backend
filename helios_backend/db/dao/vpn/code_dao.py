from datetime import UTC, datetime
from uuid import UUID

from tortoise.exceptions import IntegrityError

from helios_backend.db.models.vpn.code import Code, CodeType
from helios_backend.db.models.vpn.code_usage import CodeUsage
from helios_backend.db.models.vpn.user import User


class CodeDao:
    """DB access for codes table."""

    async def _get_by_raw_code(self, raw_code: str) -> Code | None:
        """Handle get by raw code."""
        return await Code.filter(code=raw_code.upper()).first()

    async def _check_code_usage(self, code: Code, user_id: UUID) -> bool:
        """Handle check code usage."""
        return await CodeUsage.filter(code_id=code.id, user_id=user_id).exists()

    async def _code_exists(self, raw_code: str) -> bool:
        """Handle code exists."""
        return await Code.filter(code=raw_code.upper()).exists()

    async def get_valid_code(self, raw_code: str, user_id: UUID) -> Code | None:
        """Handle get valid code."""
        code: Code | None = await self._get_by_raw_code(raw_code)
        if not code:
            return None

        now: datetime = datetime.now(tz=UTC)
        if code.expires_at and code.expires_at < now:
            return None

        active: bool = code.is_active
        if not active:
            return None

        already_used: bool = await self._check_code_usage(code, user_id)
        if already_used:
            return None

        return code

    async def get_referral_by_owner(self, owner_id: UUID) -> Code | None:
        """Handle get referral by owner."""
        return await Code.filter(owner_id=owner_id, type=CodeType.REFERRAL).first()

    async def delete_referrals_by_owner(self, owner_id: UUID) -> None:
        """Handle delete referrals by owner."""
        await Code.filter(owner_id=owner_id, type=CodeType.REFERRAL).delete()

    async def get_referral_usages_by_owner(self, owner_id: UUID) -> list[CodeUsage]:
        """Handle get referral usages by owner."""
        return (
            await CodeUsage.filter(
                code__owner_id=owner_id,
                code__type=CodeType.REFERRAL,
            )
            .select_related("user", "code")
            .order_by("-created_at")
        )

    async def create_referral_code(
        self,
        owner: User,
        raw_code: str,
        discount_percent: int,
        reward_days_percent: int,
        expires_at: datetime | None = None,
    ) -> Code:
        """Handle create referral code."""
        normalized = raw_code.upper()
        if await self._code_exists(normalized):
            msg = "code already exists"
            raise ValueError(msg)

        return await Code.create(
            code=normalized,
            type=CodeType.REFERRAL,
            owner=owner,
            discount_percent=discount_percent,
            reward_days_percent=reward_days_percent,
            expires_at=expires_at,
            is_active=True,
        )

    async def create_usage(self, code: Code, user_id: UUID) -> None:
        """Handle create usage."""
        if await self._check_code_usage(code, user_id):
            return

        try:
            await CodeUsage.create(user_id=user_id, code=code)
        except IntegrityError:
            # Another concurrent request has already persisted usage.
            return
