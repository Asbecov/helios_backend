from helios_backend.services.notifications.service import TelegramNotifierService
from helios_backend.tkq import broker


@broker.task(schedule=[{"cron": "0 */6 * * *"}])
async def notify_subscription_events() -> dict[str, int]:
    """Periodic task for subscription expiration notifications."""
    notifier = TelegramNotifierService()
    return await notifier.notify_expiring_subscriptions()


@broker.task(schedule=[{"cron": "0 13 * * *"}])
async def notify_unactivated_subscriptions_daily() -> dict[str, int]:
    """Daily reminder for users who still have frozen subscription days."""
    notifier = TelegramNotifierService()
    return await notifier.notify_unactivated_balances()
