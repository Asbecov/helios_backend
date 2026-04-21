"""Text and formatting helpers for bot responses."""

from datetime import UTC, datetime

from helios_backend.db.models.vpn.code import Code
from helios_backend.db.models.vpn.user import User
from helios_backend.settings import settings


def format_date_label(iso_value: str) -> str:
    """Format ISO datetime into compact date string."""
    try:
        parsed = datetime.fromisoformat(iso_value)
    except ValueError:
        return iso_value
    return parsed.astimezone(UTC).strftime("%d.%m.%Y")


def days_since_joined(user: User) -> int:
    """Return number of full days since user registration."""
    delta = datetime.now(tz=UTC) - user.created_at.astimezone(UTC)
    return max(delta.days, 0)


def format_tags(tags: dict[str, str]) -> str:
    """Format plan tags for card text."""
    if not tags:
        return ""
    chunks: list[str] = []
    for key, value in sorted(tags.items()):
        chunks.append(f"{key}: {value}")
    return f" ({', '.join(chunks)})"


def build_offer_text() -> str:
    """Return marketing offer copy for buy route."""
    return (
        "☀️ HeliosVPN — работает там, где другие VPN не работают\n\n"
        "Смотрите YouTube, Instagram и звоните в Telegram без блокировок.\n\n"
        "Безлимитный трафик и устройства.\n\n"
        "Покупка без риска. Если VPN не заработает — вернем деньги без лишних "
        "вопросов.\n\n"
        "Чем дольше подписка — тем больше выгода. Выберите подписку ниже."
    )


def build_help_text(username: str | None) -> str:
    """Build welcome/help text in requested bot style."""
    display_name = username or "друг"
    lines = [
        f"🏙️ Добрый день, {display_name}!",
        "",
        "💳 Мой аккаунт: /my",
        "💠 Купить подписку: /buy",
        "🚀 Подключиться: /connect",
        "🆘 Поддержка: /support",
        "",
        "Используйте кнопки меню для быстрого доступа.",
        "",
    ]

    if settings.telegram_terms_url:
        lines.append(f"Публичная оферта: {settings.telegram_terms_url}")
    if settings.telegram_privacy_url:
        lines.append(f"Политика конфиденциальности: {settings.telegram_privacy_url}")
    return "\n".join(lines)


def build_support_text() -> str:
    """Build support contacts response text."""
    contacts = settings.telegram_support_contacts.strip()
    if not contacts:
        contacts = "@support"

    lines = ["🆘 Поддержка", contacts]
    support_url = settings.telegram_support_url.strip()
    if support_url:
        lines.append(f"Ссылка: {support_url}")
    return "\n\n".join(lines)


def account_status_line(status: dict[str, int | bool | str | None] | None) -> str:
    """Build account subscription status line."""
    if status is None:
        return "❌ Нет активной подписки"

    is_frozen = status.get("is_frozen")
    expires_at = status.get("active_expires_at")
    frozen_days = status.get("remaining_frozen_days")

    if is_frozen is False and isinstance(expires_at, str):
        expires_at_date = datetime.fromisoformat(expires_at)
        now = datetime.now()

        if expires_at_date.timestamp() < now.timestamp():
            return f"❌ Просроченная подписка до {format_date_label(expires_at)}"

        return f"✅ Активная подписка до {format_date_label(expires_at)}"

    days = frozen_days if isinstance(frozen_days, int) else 0
    if days > 0:
        return f"⏸️ Подписка не активна, доступно дней: {days}"
    return "❌ Нет активной подписки"


def format_referral_block(referral_code: Code) -> str:
    """Format referral code and terms for account screen."""
    discount = referral_code.discount_percent or 0
    reward = referral_code.reward_days_percent or 0
    expires = (
        format_date_label(referral_code.expires_at.isoformat())
        if referral_code.expires_at is not None
        else "без срока"
    )
    status_label = "активен" if referral_code.is_active else "неактивен"

    return (
        "🎁 Ваш реферальный код:\n"
        f"<code>{referral_code.code}</code>\n\n"
        "Делитесь им c друзьями и получайте бонусы за каждую покупку по вашему коду!\n\n"  # noqa: E501
        "Условия:\n"
        f"• Скидка приглашенному: {discount}%\n"
        f"• Ваш бонус: +{reward}% дней\n"
        f"• Срок действия: {expires}\n"
        f"• Статус: {status_label}"
    )


def format_user_profile(
    user: User,
    status: dict[str, int | bool | str | None] | None,
    referral_code: Code,
) -> str:
    """Render account payload for my route."""
    joined_days = days_since_joined(user)
    status_text = account_status_line(status)
    referral_block = format_referral_block(referral_code)
    return (
        "💳 Мой аккаунт, подписка\n"
        f"📅 Вы зашли в бота {joined_days} дней назад\n\n"
        f"{status_text}\n\n"
        f"{referral_block}"
    )
