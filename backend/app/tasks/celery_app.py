"""Celery application configuration for background jobs."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "vocaleaf",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_ignore_result=True,
    broker_connection_retry_on_startup=True,
)

# Import task modules so Celery registers decorators on startup.
import app.workers.voice_clone_worker  # noqa: F401,E402
