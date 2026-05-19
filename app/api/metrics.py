from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.auth import get_current_user, get_admin_user
from app.core.redis_client import get_redis
from app.core.config import settings
from app.models.job import Job, JobStatus
from app.models.user import User
from app.schemas.schemas import ThroughputMetrics, SurgeMetrics

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/throughput", response_model=ThroughputMetrics)
async def get_throughput(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    redis = await get_redis()

    rps = float(await redis.get("flowengine:rps") or 0)
    total = int(await redis.get("flowengine:total_jobs") or 0)

    # jobs last minute from DB
    from datetime import datetime, timedelta
    one_min_ago = datetime.utcnow() - timedelta(minutes=1)
    one_hr_ago = datetime.utcnow() - timedelta(hours=1)

    result_min = await db.execute(
        select(func.count(Job.id)).where(Job.created_at >= one_min_ago)
    )
    result_hr = await db.execute(
        select(func.count(Job.id)).where(Job.created_at >= one_hr_ago)
    )

    return ThroughputMetrics(
        jobs_per_second=round(rps, 2),
        jobs_last_minute=result_min.scalar() or 0,
        jobs_last_hour=result_hr.scalar() or 0,
        total_jobs=total,
    )


@router.get("/surge", response_model=SurgeMetrics)
async def get_surge(
    current_user: User = Depends(get_current_user),
):
    redis = await get_redis()

    rps = float(await redis.get("flowengine:rps") or 0)
    is_surge_flag = await redis.get("flowengine:is_surge")
    is_surge = is_surge_flag == "1"

    surge_started_raw = await redis.get("flowengine:surge_started_at")
    surge_started = None
    if surge_started_raw:
        from datetime import datetime
        surge_started = datetime.fromisoformat(surge_started_raw)

    return SurgeMetrics(
        is_surge=is_surge,
        current_rps=round(rps, 2),
        threshold_rps=settings.SURGE_THRESHOLD_PER_SECOND,
        surge_started_at=surge_started,
        active_workers=4,
    )


@router.get("/latency")
async def get_latency(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import text
    result = await db.execute(text("""
        SELECT
            job_type,
            COUNT(*) as total,
            AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_seconds,
            MIN(EXTRACT(EPOCH FROM (completed_at - started_at))) as min_seconds,
            MAX(EXTRACT(EPOCH FROM (completed_at - started_at))) as max_seconds
        FROM jobs
        WHERE status = 'completed'
          AND started_at IS NOT NULL
          AND completed_at IS NOT NULL
        GROUP BY job_type
    """))
    rows = result.fetchall()
    return [
        {
            "job_type": row[0],
            "total_completed": row[1],
            "avg_latency_s": round(float(row[2] or 0), 3),
            "min_latency_s": round(float(row[3] or 0), 3),
            "max_latency_s": round(float(row[4] or 0), 3),
        }
        for row in rows
    ]


@router.get("/cache-stats")
async def get_cache_stats(
    current_user: User = Depends(get_current_user),
):
    redis = await get_redis()
    info = await redis.info("stats")
    return {
        "keyspace_hits": info.get("keyspace_hits", 0),
        "keyspace_misses": info.get("keyspace_misses", 0),
        "hit_rate_pct": round(
            info.get("keyspace_hits", 0)
            / max(1, info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0))
            * 100,
            2,
        ),
        "connected_clients": info.get("connected_clients", 0),
        "used_memory_human": (await redis.info("memory")).get("used_memory_human", "N/A"),
    }
