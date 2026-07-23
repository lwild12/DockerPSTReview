from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "pstreview",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.ingest_tasks", "app.tasks.render_tasks", "app.tasks.export_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    worker_max_tasks_per_child=50,
)
