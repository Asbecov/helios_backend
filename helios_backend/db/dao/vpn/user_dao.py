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

    async def create(
        self,
        telegram_id: int,
        username: str | None,
        marzban_username: str | None = None,
    ) -> User:
        """Handle create."""
        return await User.create(
            telegram_id=telegram_id,
            username=username,
            marzban_username=marzban_username,
        )

    async def marzban_username_exists(self, value: str) -> bool:
        """Handle marzban username exists."""
        return await User.filter(marzban_username=value).exists()

    async def delete(self, user: User) -> None:
        """Handle delete."""
        await user.delete()
