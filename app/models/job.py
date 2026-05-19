import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.core.database import Base


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class JobPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    job_type = Column(String(100), nullable=False)
    status = Column(SAEnum(JobStatus), default=JobStatus.QUEUED, nullable=False)
    priority = Column(SAEnum(JobPriority), default=JobPriority.NORMAL, nullable=False)
    payload = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    scheduled_for = Column(DateTime, nullable=True)
    created_by = Column(String(255), nullable=True)
