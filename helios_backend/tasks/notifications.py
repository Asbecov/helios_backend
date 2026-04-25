from contextlib import suppress
from datetime import UTC, datetime

from helios_backend.services.notifications.service import TelegramNotifierService
from helios_backend.tkq import broker, get_dynamic_schedule_source


@broker.task(schedule=[{"cron": "30 17 * * *", "cron_offset": "Europe/Moscow"}])
async def notify_subscription_events() -> dict[str, int]:
    """Periodic task for subscription expiration notifications."""
    notifier = TelegramNotifierService()
    return await notifier.notify_expiring_subscriptions()


@broker.task(schedule=[{"cron": "0 13 * * *"}])
async def notify_unactivated_subscriptions_daily() -> dict[str, int]:
    """Daily reminder for users who still have frozen subscription days."""
    notifier = TelegramNotifierService()
    return await notifier.notify_unactivated_balances()


@broker.task(
    retry_on_error=True,
    max_retries=5,
    delay=10,
)
async def notify_subscription_expired_once(
    balance_id: str,
    expected_expires_at: str,
) -> dict[str, str]:
    """Send one-shot expiration message for a specific balance."""
    notifier = TelegramNotifierService()
    sent = await notifier.notify_subscription_expired_once(
        balance_id=balance_id,
        expected_expires_at=expected_expires_at,
    )
    return {
        "balance_id": balance_id,
        "status": "sent" if sent else "skipped",
    }


@broker.task
async def rehydrate_expiry_notifications() -> dict[str, int]:
    """Recreate one-shot expiry schedules for already active subscriptions."""
    notifier = TelegramNotifierService(
        schedule_expiry_notification=schedule_expiry_notification,
    )
    return await notifier.schedule_expiry_notifications_for_existing_balances()


def _to_utc(value: datetime) -> datetime:
    """Normalize datetime to UTC-aware representation."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _build_expiry_schedule_id(balance_id: str, expected_expires_at: datetime) -> str:
    """Build deterministic schedule id for per-balance expiry notification."""
    expires_ts = int(_to_utc(expected_expires_at).timestamp())
    return f"subscription-expired:{balance_id}:{expires_ts}"


async def schedule_expiry_notification(
    balance_id: str,
    expected_expires_at: datetime,
    run_at: datetime | None = None,
) -> str | None:
    """Schedule one-shot notification at exact expiry (or immediate catch-up)."""
    dynamic_source = get_dynamic_schedule_source()
    if dynamic_source is None:
        return None

    normalized_expected = _to_utc(expected_expires_at)
    normalized_run_at = _to_utc(run_at or normalized_expected)
    schedule_id = _build_expiry_schedule_id(balance_id, normalized_expected)

    with suppress(NotImplementedError):
        # Some schedule sources are append-only; safe to continue.
        await dynamic_source.delete_schedule(schedule_id)

    await (
        notify_subscription_expired_once.kicker()
        .with_schedule_id(schedule_id)
        .schedule_by_time(
            dynamic_source,
            normalized_run_at,
            balance_id,
            normalized_expected.isoformat(),
        )
    )
    return schedule_id
