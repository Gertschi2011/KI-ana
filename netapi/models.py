# models.py – SQLAlchemy Modelle
from datetime import datetime
import uuid

from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint, ForeignKey, Index, JSON
from .db import Base
from sqlalchemy.orm import relationship
from sqlalchemy import Boolean

# Bestehendes User-Modell (so lassen; nur Beispiel-Felder)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    email = Column(String, unique=True)
    password_hash = Column(Text)
    birthdate = Column(String)
    address = Column(Text)
    role = Column("role", String, default="user", quote=True)  # Escape reserved word
    tier = Column(String, default="user")
    # New: per-user Papa flag (nullable for backward compatibility)
    is_papa = Column(Boolean, default=False)
    daily_quota = Column(Integer, default=20)
    quota_reset_at = Column(Integer, default=0)
    plan = Column(String, default="free")
    plan_until = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    # Account lifecycle / moderation (compose uses Postgres where these names exist)
    account_status = Column(Text, default="active")
    deleted_at = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    locked_until = Column(Integer, default=0)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_hash = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(Integer, default=0, index=True)
    last_seen_at = Column(Integer, default=0, index=True)
    expires_at = Column(Integer, default=0, index=True)
    revoked_at = Column(Integer, default=0, index=True)

# Key/Value Settings (global)
class SettingsKV(Base):
    __tablename__ = "settings"
    key = Column(String(64), primary_key=True)
    value = Column(Text, default="")


# Planner: Plans and Steps
class Plan(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), default="", index=True)
    user_id = Column(Integer, default=0, index=True)
    status = Column(String(16), default="queued", index=True)  # queued|running|done|failed|canceled
    meta = Column(Text, default="{}")
    created_at = Column(Integer, default=0)
    updated_at = Column(Integer, default=0)
    started_at = Column(Integer, default=0)
    finished_at = Column(Integer, default=0)


class PlanStep(Base):
    __tablename__ = "plan_steps"
    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, index=True, nullable=False)
    idx = Column(Integer, default=0, index=True)
    type = Column(String(64), default="task", index=True)
    payload = Column(Text, default="{}")
    status = Column(String(16), default="queued", index=True)  # queued|running|done|failed|canceled
    result = Column(Text, default="")
    error = Column(Text, default="")
    created_at = Column(Integer, default=0)
    updated_at = Column(Integer, default=0)
    started_at = Column(Integer, default=0)
    finished_at = Column(Integer, default=0)

# Admin Audit Log
class AdminAudit(Base):
    __tablename__ = "admin_audit"
    id = Column(Integer, primary_key=True)
    ts = Column(Integer, default=0, index=True)
    actor_user_id = Column(Integer, default=0, index=True)
    action = Column(String(64), default="")
    target_type = Column(String(64), default="")
    target_id = Column(Integer, default=0, index=True)
    meta = Column(Text, default="{}")


# Phase D3: Append-only Audit Events (separate from legacy AdminAudit)
class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ts = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    actor_type = Column(String(16), default="system")  # user|system|admin
    actor_id = Column(Integer, nullable=True, index=True)

    action = Column(String(64), default="", index=True)
    subject_type = Column(String(64), default="")
    subject_id = Column(String(128), nullable=True)

    result = Column(String(16), default="success")  # success|denied|error
    meta = Column(JSON, default=dict)

    __table_args__ = (
        Index("ix_audit_events_action_ts", "action", "ts"),
        Index("ix_audit_events_actor_id_ts", "actor_id", "ts"),
    )

# Gespräche (serverseitig)
class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), default="Neue Unterhaltung")
    folder_id = Column(Integer, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True, index=True)
    # last_save_at removed - not in DB schema
    created_at = Column(Integer, default=0)
    updated_at = Column(Integer, default=0)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    conv_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(12), nullable=False)  # 'user' | 'ai' | 'system'
    text = Column(Text, nullable=False)
    created_at = Column(Integer, default=0)

class TimeflowEvent(Base):
    __tablename__ = "timeflow_events"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    event_type = Column(String(64), default="generic", index=True)
    meta = Column(Text, default="{}")
    created_at = Column(Integer, default=0, index=True)

# Jobs (lightweight queue)
class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    type = Column(String(64), index=True, nullable=False)
    payload = Column(Text, default="{}")
    status = Column(String(16), index=True, default="queued")  # queued|leased|done|failed
    attempts = Column(Integer, default=0)
    lease_until = Column(Integer, default=0)  # epoch seconds
    idempotency_key = Column(String(128), unique=True, nullable=True)
    priority = Column(Integer, default=0)
    error = Column(Text, default="")
    created_at = Column(Integer, default=0)
    updated_at = Column(Integer, default=0)

# NEU: Password-/Email-Token
class EmailToken(Base):
    __tablename__ = "email_tokens"
    # passt auf deine existierende Tabelle (token als PK)
    token = Column(String(128), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    purpose = Column(String(20), nullable=False)         # z.B. "reset"
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("token", name="uq_email_tokens_token"),
    )

# Browser Error Telemetry
class BrowserError(Base):
    __tablename__ = "browser_errors"
    id = Column(Integer, primary_key=True)
    ts = Column(Integer, default=0, index=True)
    level = Column(String(12), default="error")  # error|warn|info
    message = Column(Text, default="")
    url = Column(Text, default="")
    stack = Column(Text, default="")
    user_id = Column(Integer, default=0, index=True)
    user_agent = Column(Text, default="")
    ip = Column(String(64), default="", index=True)
    count = Column(Integer, default=1)

# Devices (Papa OS / Admin managed)
class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), default="")
    os = Column(String(60), default="")  # e.g. linux, windows, android
    owner_id = Column(Integer, default=0, index=True)
    status = Column(String(20), default="unknown")  # ok|warn|offline|unknown
    last_seen = Column(Integer, default=0, index=True)
    created_at = Column(Integer, default=0)
    updated_at = Column(Integer, default=0)
    # Device token auth (stored as hash only)
    token_hash = Column(String(128), default="")
    token_hint = Column(String(16), default="")   # e.g. first 8 chars for display
    issued_at = Column(Integer, default=0)
    last_auth_at = Column(Integer, default=0)
    revoked_at = Column(Integer, default=0)
    # Queue retention metrics
    events_pruned_total = Column(Integer, default=0)
    # Last ack from device (Phase 3D)
    last_ack_ts = Column(Integer, default=0)
    last_ack_type = Column(String(40), default="")
    last_ack_status = Column(String(20), default="")

class DeviceEvent(Base):
    __tablename__ = "device_events"
    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, index=True, nullable=False)
    ts = Column(Integer, default=0, index=True)
    type = Column(String(40), default="message")
    payload = Column(Text, default="{}")
    delivered_at = Column(Integer, default=0, index=True)


# Knowledge Blocks
class KnowledgeBlock(Base):
    __tablename__ = "knowledge_blocks"
    id = Column(Integer, primary_key=True)
    ts = Column(Integer, default=0, index=True)
    source = Column(String(120), default="", index=True)
    type = Column(String(60), default="text", index=True)
    tags = Column(String(400), default="", index=True)  # comma-separated
    content = Column(Text, default="")
    hash = Column(String(64), unique=True, index=True)
    created_at = Column(Integer, default=0)
    updated_at = Column(Integer, default=0)
