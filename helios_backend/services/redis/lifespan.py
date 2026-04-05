from fastapi import FastAPI
from redis.asyncio import ConnectionPool, Redis

from helios_backend.settings import settings


def init_redis(app: FastAPI) -> None:  # pragma: no cover
    """
    Creates connection pool for redis.

    :param app: current fastapi application.
    """
    app.state.redis_pool = ConnectionPool.from_url(
        str(settings.redis_url),
    )
    app.state.redis = Redis(connection_pool=app.state.redis_pool)


async def shutdown_redis(app: FastAPI) -> None:  # pragma: no cover
    """
    Closes redis connection pool.

    :param app: current FastAPI app.
    """
    await app.state.redis.aclose()
    await app.state.redis_pool.disconnect()
