import time
import json
import random
from datetime import datetime
from celery import shared_task
from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app
from app.core.config import settings

logger = get_task_logger(__name__)

SIMULATED_WORK = {
    "report": (3, 8),
    "image_resize": (1, 4),
    "aggregation": (5, 10),
    "csv_export": (0.5, 2),
    "data_sync": (2, 6),
    "default": (1, 5),
}


def _simulate_work(job_type: str) -> dict:
    lo, hi = SIMULATED_WORK.get(job_type, SIMULATED_WORK["default"])
    duration = random.uniform(lo, hi)
    time.sleep(duration)
    return {
        "processed_at": datetime.utcnow().isoformat(),
        "duration_seconds": round(duration, 3),
        "job_type": job_type,
        "rows_processed": random.randint(100, 50000),
    }


def _update_job_redis(redis_url: str, job_id: str, status: str, extra: dict = None):
    import redis as sync_redis
    r = sync_redis.from_url(redis_url, decode_responses=True)
    data = {"status": status, "updated_at": datetime.utcnow().isoformat()}
    if extra:
        data.update(extra)
    r.hset(f"job:{job_id}", mapping=data)
    r.publish("job_updates", json.dumps({"job_id": job_id, **data}))
    r.close()


@celery_app.task(bind=True, max_retries=3, name="app.workers.tasks.process_job")
def process_job(self, job_id: str, job_type: str, payload: dict = None):
    redis_url = settings.REDIS_URL.replace("redis://redis", "redis://localhost")

    try:
        logger.info(f"Starting job {job_id} type={job_type}")
        _update_job_redis(redis_url, job_id, "processing", {"started_at": datetime.utcnow().isoformat()})

        result = _simulate_work(job_type)

        _update_job_redis(redis_url, job_id, "completed", {
            "completed_at": datetime.utcnow().isoformat(),
            "result": json.dumps(result),
        })
        logger.info(f"Completed job {job_id} in {result['duration_seconds']}s")
        return result

    except Exception as exc:
        logger.error(f"Job {job_id} failed: {exc}")
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            _update_job_redis(redis_url, job_id, "retrying", {"retry_count": str(retry_count + 1)})
            raise self.retry(exc=exc, countdown=2 ** retry_count)
        else:
            _update_job_redis(redis_url, job_id, "failed", {"error": str(exc)})
            raise


@celery_app.task(name="app.workers.tasks.check_surge")
def check_surge():
    import redis as sync_redis
    r = sync_redis.from_url(settings.REDIS_URL.replace("redis://redis", "redis://localhost"), decode_responses=True)
    rps = r.get("flowengine:rps") or 0
    threshold = settings.SURGE_THRESHOLD_PER_SECOND
    is_surge = float(rps) >= threshold
    r.set("flowengine:is_surge", "1" if is_surge else "0")
    r.close()
    logger.info(f"Surge check: rps={rps} surge={is_surge}")
