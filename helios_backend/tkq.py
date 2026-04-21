from typing import Any

import taskiq_fastapi
from fastapi.routing import APIRouter
from taskiq import AsyncBroker, AsyncResultBackend, InMemoryBroker
from taskiq.events import TaskiqEvents
from taskiq.middlewares.smart_retry_middleware import SmartRetryMiddleware
from taskiq.schedule_sources.label_based import LabelScheduleSource, ScheduleSource
from taskiq.scheduler.scheduler import TaskiqScheduler
from taskiq.state import TaskiqState
from taskiq_redis import (
    ListQueueBroker,
    ListRedisScheduleSource,
    RedisAsyncResultBackend,
)

from helios_backend.services.notifications.bot_client import close_shared_bot
from helios_backend.settings import settings

_taskiq_redis_url = str(settings.redis_url.with_path("/1"))

result_backend: AsyncResultBackend[Any] = RedisAsyncResultBackend(
    redis_url=_taskiq_redis_url,
)
broker: AsyncBroker = ListQueueBroker(
    _taskiq_redis_url,
).with_result_backend(result_backend)
dynamic_schedule_source: ListRedisScheduleSource | None = ListRedisScheduleSource(
    url=_taskiq_redis_url,
    prefix="helios:schedule",
)

if settings.environment.lower() == "pytest":
    broker = InMemoryBroker()
    dynamic_schedule_source = None

if dynamic_schedule_source is not None:
    broker = broker.with_middlewares(
        SmartRetryMiddleware(
            default_retry_count=5,
            default_retry_label=False,
            default_delay=10,
            use_delay_exponent=True,
            max_delay_exponent=120,
            schedule_source=dynamic_schedule_source,
        )
    )

scheduler_sources: list[ScheduleSource] = [LabelScheduleSource(broker)]
if dynamic_schedule_source is not None:
    scheduler_sources.append(dynamic_schedule_source)

scheduler = TaskiqScheduler(
    broker=broker,
    sources=scheduler_sources,
)


def get_dynamic_schedule_source() -> ListRedisScheduleSource | None:
    """Return dynamic scheduler source that stores one-shot schedules in Redis."""
    return dynamic_schedule_source


def _patch_fastapi_router_lifecycle_for_taskiq() -> None:
    """Expose startup/shutdown aliases expected by taskiq-fastapi."""
    if hasattr(APIRouter, "startup") and hasattr(APIRouter, "shutdown"):
        return

    if not callable(getattr(APIRouter, "_startup", None)):
        return
    if not callable(getattr(APIRouter, "_shutdown", None)):
        return

    async def _router_startup(self: APIRouter) -> None:
        await self._startup()

    async def _router_shutdown(self: APIRouter) -> None:
        await self._shutdown()

    APIRouter.startup = _router_startup  # type: ignore[attr-defined]
    APIRouter.shutdown = _router_shutdown  # type: ignore[attr-defined]


_patch_fastapi_router_lifecycle_for_taskiq()

taskiq_fastapi.init(
    broker,
    "helios_backend.web.application:get_app",
)


@broker.on_event(TaskiqEvents.CLIENT_STARTUP)
async def schedule_rehydration_on_scheduler_start(_: TaskiqState) -> None:
    """Kick startup rehydration only in scheduler process."""
    if not broker.is_scheduler_process:
        return
    if dynamic_schedule_source is None:
        return

    rehydrate_task = broker.find_task(
        "helios_backend.tasks.notifications:rehydrate_expiry_notifications"
    )
    if rehydrate_task is None:
        return

    await rehydrate_task.kiq()


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN, TaskiqEvents.CLIENT_SHUTDOWN)
async def close_notification_bot_on_shutdown(_: TaskiqState) -> None:
    """Close shared notification bot when taskiq process stops."""
    await close_shared_bot()


# Import tasks to register them in broker decorators.
import helios_backend.tasks.notifications  # noqa: E402,F401
