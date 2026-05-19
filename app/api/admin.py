from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession  # type: ignore[import]
from sqlalchemy import select, update, func  # type: ignore[import]
from typing import List

from app.core.database import get_db
from app.core.auth import get_admin_user
from app.core.redis_client import get_redis
from app.models.job import Job, JobStatus
from app.models.user import User
from app.schemas.schemas import JobResponse, UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/jobs", response_model=List[JobResponse])
async def list_all_jobs(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(Job).order_by(Job.created_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.post("/flush")
async def flush_queue(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Drain all queued jobs — admin only."""
    result = await db.execute(
        select(func.count(Job.id)).where(Job.status == JobStatus.QUEUED)
    )
    count = result.scalar()

    await db.execute(
        update(Job)
        .where(Job.status == JobStatus.QUEUED)
        .values(status=JobStatus.FAILED, error="Flushed by admin")
    )
    await db.commit()

    # clear Celery queues via Redis
    redis = await get_redis()
    for queue in ("critical", "high", "normal", "low", "celery"):
        await redis.delete(queue)

    return {"flushed_jobs": count, "flushed_by": admin.username}


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.get("/audit-logs")
async def get_audit_logs(
    admin: User = Depends(get_admin_user),
):
    """Returns recent job state changes from Redis pub/sub log."""
    redis = await get_redis()
    logs = await redis.lrange("flowengine:audit_log", 0, 99)
    return {"logs": logs, "count": len(logs)}


@router.get("/stats")
async def system_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    redis = await get_redis()
    results = {}
    for status in JobStatus:
        r = await db.execute(
            select(func.count(Job.id)).where(Job.status == status)
        )
        results[status.value] = r.scalar()

    total = int(await redis.get("flowengine:total_jobs") or 0)
    return {"job_counts": results, "redis_total_counter": total}
