from __future__ import annotations
import os
from celery import Celery

REDIS_URL = f"redis://{os.getenv('REDIS_HOST','redis')}:{os.getenv('REDIS_PORT','6379')}/0"

celery = Celery(
    "kiana",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.workers.tasks"],
)

celery.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"]) 
