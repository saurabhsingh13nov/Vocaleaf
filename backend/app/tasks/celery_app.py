"""Celery application configuration for background jobs."""

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown

from app.core.config import settings
from app.db.session import dispose_session_state_sync, reset_session_state

celery_app = Celery(
    "vocaleaf",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_ignore_result=True,
    broker_connection_retry_on_startup=True,
)


@worker_process_init.connect
def on_worker_process_init(**kwargs) -> None:
    """Force each prefork worker to build its own async DB engine lazily."""
    reset_session_state()


@worker_process_shutdown.connect
def on_worker_process_shutdown(**kwargs) -> None:
    """Dispose the process-local async engine before the worker exits."""
    dispose_session_state_sync()


# Import task modules so Celery registers decorators on startup.
import app.workers.audio_worker  # noqa: F401,E402
import app.workers.image_worker  # noqa: F401,E402
import app.workers.text_worker  # noqa: F401,E402
import app.workers.voice_clone_worker  # noqa: F401,E402
