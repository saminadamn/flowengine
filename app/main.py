from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.core.rate_limiter import RateLimiterMiddleware
from app.core.redis_client import close_redis

from app.api import auth, jobs, metrics, admin, websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup — create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created")
    yield
    # shutdown
    await close_redis()
    print("✅ Redis connection closed")


app = FastAPI(
    title="FlowEngine",
    description="""
## Distributed Job Queue & Scheduler

A production-grade async job processing system with:
- **Priority queues** (critical / high / normal / low)
- **Token-bucket rate limiting** per IP
- **Surge detection** via Celery Beat
- **WebSocket live feed** for real-time job updates
- **JWT authentication** with role-based access
- **Metrics endpoints** for latency, throughput, cache stats

Built with FastAPI · Celery · Redis · PostgreSQL
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimiterMiddleware)

# ── Routers ───────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(metrics.router)
app.include_router(admin.router)
app.include_router(websocket.router)


# ── Health ────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health():
    from app.core.redis_client import get_redis
    redis = await get_redis()
    await redis.ping()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "services": {
            "redis": "ok",
            "api": "ok",
        }
    }


@app.get("/", tags=["system"])
async def root():
    return {
        "app": "FlowEngine",
        "docs": "/docs",
        "health": "/health",
        "websocket": "ws://localhost:8000/ws/feed?token=<jwt>",
    }
