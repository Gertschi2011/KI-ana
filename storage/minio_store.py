import os
from datetime import timedelta
from typing import Optional

_MINIO_AVAILABLE = True
try:
    from minio import Minio
except Exception:  # pragma: no cover - optional dependency
    _MINIO_AVAILABLE = False
    Minio = None  # type: ignore


MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "artifacts")

_client: Optional["Minio"] = None


def _ensure_client():
    global _client
    if not _MINIO_AVAILABLE:
        raise RuntimeError("minio package not installed. Install 'minio' or set presigned URLs externally.")
    if _client is None:
        _client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
        # Ensure bucket exists
        if not _client.bucket_exists(MINIO_BUCKET):
            _client.make_bucket(MINIO_BUCKET)
    return _client


def put_artifact(local_path: str, cid_hex: str) -> None:
    client = _ensure_client()
    key = f"artifacts/{cid_hex}"
    client.fput_object(MINIO_BUCKET, key, local_path)


def presigned_get(cid_hex: str, ttl_seconds: int = 600) -> str:
    client = _ensure_client()
    key = f"artifacts/{cid_hex}"
    return client.get_presigned_url("GET", MINIO_BUCKET, key, expires=timedelta(seconds=ttl_seconds))
