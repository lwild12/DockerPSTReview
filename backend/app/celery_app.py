from celery import Celery

from app.config import get_settings

settings = get_settings()

# Task modules are added here as each phase lands (Phase 2: ingest_tasks/render_tasks,
# Phase 5: export_tasks) — an empty list keeps `celery -A app.celery_app worker` importable
# before those modules exist.
celery_app = Celery(
    "pstreview",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    worker_max_tasks_per_child=50,
)
