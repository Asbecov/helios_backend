from typing import Any

import taskiq_fastapi
from taskiq import AsyncBroker, AsyncResultBackend, InMemoryBroker
from taskiq.events import TaskiqEvents
from taskiq.state import TaskiqState
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from helios_backend.services.notifications.bot_client import close_shared_bot
from helios_backend.settings import settings

result_backend: AsyncResultBackend[Any] = RedisAsyncResultBackend(
    redis_url=str(settings.redis_url.with_path("/1")),
)
broker: AsyncBroker = ListQueueBroker(
    str(settings.redis_url.with_path("/1")),
).with_result_backend(result_backend)

if settings.environment.lower() == "pytest":
    broker = InMemoryBroker()

taskiq_fastapi.init(
    broker,
    "helios_backend.web.application:get_app",
)


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN, TaskiqEvents.CLIENT_SHUTDOWN)
async def close_notification_bot_on_shutdown(_: TaskiqState) -> None:
    """Close shared notification bot when taskiq process stops."""
    await close_shared_bot()


# Import tasks to register them in broker decorators.
import helios_backend.tasks.notifications  # noqa: E402,F401
