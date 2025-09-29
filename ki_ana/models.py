from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Float, DateTime, Index, ForeignKey
)
from sqlalchemy.orm import relationship
from .db import Base

class Node(Base):
    __tablename__ = "nodes"
    id = Column(String, primary_key=True)  # WORKER_ID
    caps = Column(Text, nullable=True)
    last_seen = Column(Float, index=True)  # epoch seconds

class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    cid = Column(String, nullable=False)  # sha256 hex or external cid
    params_json = Column(Text, nullable=True)
    status = Column(String, nullable=False, index=True)  # pending|assigned|done|failed
    assigned_node = Column(String, ForeignKey("nodes.id"), nullable=True, index=True)
    retries = Column(Integer, default=0, nullable=False)
    lease_until = Column(Float, nullable=True, index=True)  # epoch seconds
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    artifacts = relationship("Artifact", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_jobs_status_created", "status", "created_at"),
    )

class Artifact(Base):
    __tablename__ = "artifacts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False, index=True)
    cid = Column(String, nullable=False, index=True)
    kind = Column(String, nullable=False)  # input|result|log
    storage_backend = Column(String, nullable=False, default="minio")  # minio|ipfs
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    job = relationship("Job", back_populates="artifacts")
