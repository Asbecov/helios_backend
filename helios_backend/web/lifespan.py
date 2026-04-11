import importlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from helios_backend.services.notifications.bot_client import close_shared_bot
from helios_backend.services.redis.lifespan import init_redis, shutdown_redis
from helios_backend.settings import settings
from helios_backend.tkq import broker


@asynccontextmanager
async def lifespan_setup(
    app: FastAPI,
) -> AsyncGenerator[None]:  # pragma: no cover
    """
    Actions to run on application startup.

    This function uses fastAPI app to store data
    in the state, such as db_engine.

    :param app: the fastAPI application.
    :return: function that actually performs actions.
    """

    app.middleware_stack = None
    if not broker.is_worker_process:
        await broker.startup()
    init_redis(app)
    if settings.environment.lower() != "pytest":
        admin_module = importlib.import_module("helios_backend.web.admin")
        configure_admin_panel = admin_module.configure_admin_panel

        await configure_admin_panel(app)

    app.middleware_stack = app.build_middleware_stack()

    yield
    if not broker.is_worker_process:
        await broker.shutdown()
    await close_shared_bot()
    await shutdown_redis(app)
