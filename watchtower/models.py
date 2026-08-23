import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class MonitorType(enum.StrEnum):
    TEXT = "text"
    HTML = "html"
    ELEMENT = "element"
    VISUAL = "visual"
    PRICE = "price"
    AVAILABILITY = "availability"
    STATUS = "status"


class CheckStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Monitor(Base):
    __tablename__ = "monitors"
    __table_args__ = (Index("ix_monitors_due", "enabled", "next_check_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    monitor_type: Mapped[MonitorType] = mapped_column(Enum(MonitorType, name="monitor_type"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    browser_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    selector: Mapped[str | None] = mapped_column(Text)
    ignore_selectors: Mapped[list[str]] = mapped_column(JSON, default=list)
    ignore_regexes: Mapped[list[str]] = mapped_column(JSON, default=list)
    custom_headers_encrypted: Mapped[str | None] = mapped_column(Text)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    change_threshold: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0)
    baseline_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    checks: Mapped[list["Check"]] = relationship(back_populates="monitor", cascade="all, delete-orphan")


class Check(Base):
    __tablename__ = "checks"
    __table_args__ = (
        Index("ix_checks_monitor_created", "monitor_id", "created_at"),
        Index("ix_checks_status", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monitor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitors.id", ondelete="CASCADE"))
    status: Mapped[CheckStatus] = mapped_column(Enum(CheckStatus, name="check_status"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(200))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    content_size: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    changed: Mapped[bool] = mapped_column(Boolean, default=False)
    change_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    monitor: Mapped[Monitor] = relationship(back_populates="checks")


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (Index("ix_snapshots_monitor_created", "monitor_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monitor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitors.id", ondelete="CASCADE"))
    check_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("checks.id", ondelete="CASCADE"), unique=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    text_content: Mapped[str | None] = mapped_column(Text)
    html_content: Mapped[str | None] = mapped_column(Text)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    availability_state: Mapped[str | None] = mapped_column(String(32))
    screenshot_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChangeEvent(Base):
    __tablename__ = "change_events"
    __table_args__ = (Index("ix_changes_monitor_created", "monitor_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monitor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitors.id", ondelete="CASCADE"))
    previous_snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("snapshots.id"))
    current_snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("snapshots.id"), unique=True)
    change_type: Mapped[str] = mapped_column(String(64))
    change_score: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    summary: Mapped[str] = mapped_column(Text)
    diff: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
