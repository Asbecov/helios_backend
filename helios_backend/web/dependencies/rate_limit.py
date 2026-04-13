from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from helios_backend.settings import settings


def resolve_client_ip(request: Request) -> str | None:
    """Resolve effective client IP according to proxy trust policy."""
    if settings.rate_limit_trust_forwarded_ip:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            first_hop = forwarded_for.split(",", maxsplit=1)[0].strip()
            if first_hop:
                return first_hop

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            real_ip = real_ip.strip()
            if real_ip:
                return real_ip

    if request.client:
        return request.client.host

    return None


def _resolve_client_identity(request: Request) -> str:
    """Resolve client identity for rate limiting keys."""
    client_ip = resolve_client_ip(request)
    if client_ip:
        return client_ip
    return "unknown"


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
        key_part = _resolve_client_identity(request)

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
