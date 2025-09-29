from __future__ import annotations
from backend.workers.celery_app import celery

@celery.task(name="ingest.parse_file")
def task_parse_file(obj_key: str) -> dict:
    # Scaffold implementation
    return {"ok": True, "object": obj_key, "parsed": True}

@celery.task(name="embed.text")
def task_embed_text(text: str) -> dict:
    # Scaffold embedding (returns dummy vector)
    return {"ok": True, "vector": [0.1, 0.2, 0.3]}
