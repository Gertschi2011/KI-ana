from __future__ import annotations
import os
from dataclasses import dataclass
from typing import List


def _split_csv(v: str | None) -> List[str]:
    if not v:
        return []
    return [s.strip() for s in v.split(",") if s.strip()]


@dataclass
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://ki:change_me@postgres:5432/kiana")
    redis_host: str = os.getenv("REDIS_HOST", "redis")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    qdrant_host: str = os.getenv("QDRANT_HOST", "qdrant")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    minio_root_user: str = os.getenv("MINIO_ROOT_USER", "minioadmin")
    minio_root_password: str = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    jwt_secret: str = os.getenv("JWT_SECRET", "CHANGE_ME")
    cors_origins: list[str] = None  # type: ignore
    feature_voice: bool = os.getenv("FEATURE_VOICE", "0") in {"1", "true", "True"}
    feature_p2p: bool = os.getenv("FEATURE_P2P", "0") in {"1", "true", "True"}
    emergency_hash: str = os.getenv("EMERGENCY_OVERRIDE_SHA256", "")

    def __post_init__(self):
        self.cors_origins = _split_csv(os.getenv("CORS_ORIGINS", "http://localhost:3000"))
