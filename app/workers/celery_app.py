from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "flowengine",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.tasks.process_job_critical": {"queue": "critical"},
        "app.workers.tasks.process_job_high": {"queue": "high"},
        "app.workers.tasks.process_job_normal": {"queue": "normal"},
        "app.workers.tasks.process_job_low": {"queue": "low"},
    },
    beat_schedule={
        "surge-check-every-5s": {
            "task": "app.workers.tasks.check_surge",
            "schedule": 5.0,
        },
    },
)
