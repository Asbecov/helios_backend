from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from helios_backend.settings import settings


def rate_limit(
    limit: int,
    window_seconds: int,
    prefix: str,
) -> Callable[[Request], Awaitable[None]]:
    """Create Redis-based fixed-window limiter dependency."""

    async def limiter(request: Request) -> None:
        if settings.environment.lower() == "pytest":
            return
        redis: Redis = request.app.state.redis
        key_part = request.client.host if request.client else "unknown"

        redis_key = f"rl:{prefix}:{key_part}"
        count = await redis.incr(redis_key)
        if count == 1:
            await redis.expire(redis_key, window_seconds)
        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )

    return limiter
