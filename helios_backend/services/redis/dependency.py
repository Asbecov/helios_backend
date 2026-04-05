from redis.asyncio import Redis
from starlette.requests import Request
from taskiq import TaskiqDepends


async def get_redis_pool(
    request: Request = TaskiqDepends(),
) -> Redis:  # pragma: no cover
    """
    Returns connection pool.

    You can use it like this:

    >>> from redis.asyncio import Redis
    >>>
    >>> async def handler(redis: Redis = Depends(get_redis_pool)):
    >>>     await redis.get('key')

    Returns already configured app-level Redis client.

    :param request: current request.
    :returns: redis client.
    """
    return request.app.state.redis
