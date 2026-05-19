from pydantic import BaseModel, EmailStr
from typing import Optional, Any
from datetime import datetime
from uuid import UUID

from app.models.job import JobStatus, JobPriority


# ── Job Schemas ──────────────────────────────────────────────

class JobSubmit(BaseModel):
    name: str
    job_type: str
    priority: JobPriority = JobPriority.NORMAL
    payload: Optional[dict] = None
    scheduled_for: Optional[datetime] = None


class JobResponse(BaseModel):
    id: UUID
    name: str
    job_type: str
    status: JobStatus
    priority: JobPriority
    retry_count: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    created_by: Optional[str] = None

    class Config:
        from_attributes = True


# ── Auth Schemas ─────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# ── Metrics Schemas ──────────────────────────────────────────

class ThroughputMetrics(BaseModel):
    jobs_per_second: float
    jobs_last_minute: int
    jobs_last_hour: int
    total_jobs: int


class SurgeMetrics(BaseModel):
    is_surge: bool
    current_rps: float
    threshold_rps: int
    surge_started_at: Optional[datetime] = None
    active_workers: int
