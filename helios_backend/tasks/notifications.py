from helios_backend.services.notifications.service import TelegramNotifierService
from helios_backend.tkq import broker


@broker.task(schedule=[{"cron": "0 */6 * * *"}])
async def notify_subscription_events() -> dict[str, int]:
    """Periodic task for subscription expiration notifications."""
    notifier = TelegramNotifierService()
    return await notifier.notify_expiring_subscriptions()
