import json
from uuid import UUID
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.redis_client import get_redis
from app.models.job import Job, JobStatus, JobPriority
from app.models.user import User
from app.schemas.schemas import JobSubmit, JobResponse
from app.workers.tasks import process_job

router = APIRouter(prefix="/jobs", tags=["jobs"])

PRIORITY_QUEUE_MAP = {
    JobPriority.CRITICAL: "critical",
    JobPriority.HIGH: "high",
    JobPriority.NORMAL: "normal",
    JobPriority.LOW: "low",
}


@router.post("/submit", response_model=JobResponse, status_code=202)
async def submit_job(
    payload: JobSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = Job(
        name=payload.name,
        job_type=payload.job_type,
        priority=payload.priority,
        payload=json.dumps(payload.payload or {}),
        scheduled_for=payload.scheduled_for,
        created_by=current_user.username,
        status=JobStatus.QUEUED,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # cache initial state in Redis
    redis = await get_redis()
    await redis.hset(f"job:{job.id}", mapping={
        "status": JobStatus.QUEUED,
        "created_at": job.created_at.isoformat(),
        "job_type": job.job_type,
        "priority": job.priority,
        "created_by": current_user.username,
    })

    # track metrics
    await redis.incr("flowengine:total_jobs")
    await redis.incr("flowengine:rps")
    await redis.expire("flowengine:rps", 1)

    # dispatch to Celery queue based on priority
    queue = PRIORITY_QUEUE_MAP[payload.priority]
    process_job.apply_async(
        args=[str(job.id), job.job_type, payload.payload or {}],
        queue=queue,
        task_id=str(job.id),
    )

    return job


@router.get("/submit", response_model=List[JobResponse])
async def list_jobs(
    status: Optional[JobStatus] = Query(None),
    priority: Optional[JobPriority] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Job).where(Job.created_by == current_user.username)
    if status:
        query = query.where(Job.status == status)
    if priority:
        query = query.where(Job.priority == priority)
    query = query.order_by(Job.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{job_id}/status", response_model=JobResponse)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # try Redis cache first
    redis = await get_redis()
    cached = await redis.hgetall(f"job:{job_id}")

    if cached:
        # sync Redis state back to DB if completed/failed
        if cached.get("status") in ("completed", "failed"):
            await db.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status=cached["status"],
                    completed_at=datetime.fromisoformat(cached["completed_at"])
                    if "completed_at" in cached else None,
                    result=cached.get("result"),
                    error=cached.get("error"),
                )
            )
            await db.commit()

    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.created_by == current_user.username)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=204)
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.created_by == current_user.username)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in (JobStatus.QUEUED,):
        raise HTTPException(status_code=400, detail=f"Cannot cancel job in status: {job.status}")

    job.status = JobStatus.FAILED
    job.error = "Cancelled by user"
    await db.commit()

    # remove from Redis
    redis = await get_redis()
    await redis.delete(f"job:{job_id}")
    return
