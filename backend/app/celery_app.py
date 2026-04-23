"""Celery app for async consensus / aggregation (optional worker)."""

import os

from celery import Celery

_redis = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "audit_nigeria",
    broker=_redis,
    backend=_redis,
    include=["app.tasks.consensus_tasks"],
)

celery_app.conf.update(task_track_started=True)
