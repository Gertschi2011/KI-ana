import os
from datetime import timedelta
from typing import Optional

try:
    from minio import Minio
except Exception as e:  # pragma: no cover
    Minio = None  # type: ignore

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minio123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "artifacts")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

_client: Optional["Minio"] = None

def _client_or_raise() -> "Minio":
    global _client
    if Minio is None:
        raise RuntimeError("minio package not installed")
    if _client is None:
        _client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
        if not _client.bucket_exists(MINIO_BUCKET):
            _client.make_bucket(MINIO_BUCKET)
    return _client


def presign_get(cid: str, ttl_seconds: int = 600) -> str:
    c = _client_or_raise()
    key = f"artifacts/{cid}"
    return c.get_presigned_url("GET", MINIO_BUCKET, key, expires=timedelta(seconds=ttl_seconds))


def presign_put(cid: str, ttl_seconds: int = 600) -> str:
    c = _client_or_raise()
    key = f"artifacts/{cid}"
    return c.get_presigned_url("PUT", MINIO_BUCKET, key, expires=timedelta(seconds=ttl_seconds))
