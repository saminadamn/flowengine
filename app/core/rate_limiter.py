import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter.
    Tracks requests per IP per minute in Redis.
    Also increments RPS counter for surge detection.
    """

    EXEMPT_PATHS = {"/docs", "/redoc", "/openapi.json", "/health"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        from app.core.redis_client import get_redis
        redis = await get_redis()

        client_ip = request.client.host
        now = time.time()
        window = 60
        key = f"ratelimit:{client_ip}"

        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window)
        results = await pipe.execute()

        request_count = results[2]
        limit = settings.RATE_LIMIT_PER_MINUTE

        await redis.incr("flowengine:req_count")
        await redis.expire("flowengine:req_count", 1)

        if request_count > limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "limit": limit,
                    "window": "60s",
                    "retry_after": "60s",
                }
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - request_count))
        return response
