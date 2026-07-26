from uuid import UUID

from helios_backend.db.models.vpn.user import User


class UserDao:
    """DB access for users table."""

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Handle get by id."""
        return await User.filter(id=user_id).first()

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Handle get by telegram id."""
        return await User.filter(telegram_id=telegram_id).first()

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        """Handle get by google sub."""
        return await User.filter(google_sub=google_sub).first()

    async def create(
        self,
        telegram_id: int | None = None,
        google_sub: str | None = None,
        google_email: str | None = None,
        username: str | None = None,
        marzban_username: str | None = None,
    ) -> User:
        """Handle create."""
        return await User.create(
            telegram_id=telegram_id,
            google_sub=google_sub,
            google_email=google_email,
            username=username,
            marzban_username=marzban_username,
        )

    async def marzban_username_exists(self, value: str) -> bool:
        """Handle marzban username exists."""
        return await User.filter(marzban_username=value).exists()

    async def delete(self, user: User) -> None:
        """Handle delete."""
        await user.delete()
