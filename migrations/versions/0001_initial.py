"""Initial durable monitoring schema."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    monitor_type = sa.Enum("TEXT", "HTML", "ELEMENT", "VISUAL", "PRICE", "AVAILABILITY", "STATUS", name="monitor_type")
    check_status = sa.Enum("QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", name="check_status")
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "monitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("monitor_type", monitor_type, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("browser_enabled", sa.Boolean(), nullable=False),
        sa.Column("selector", sa.Text()),
        sa.Column("ignore_selectors", sa.JSON(), nullable=False),
        sa.Column("ignore_regexes", sa.JSON(), nullable=False),
        sa.Column("custom_headers_encrypted", sa.Text()),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("change_threshold", sa.Numeric(8, 4), nullable=False),
        sa.Column("baseline_snapshot_id", postgresql.UUID(as_uuid=True)),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("next_check_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_monitors_due", "monitors", ["enabled", "next_check_at"])
    op.create_table(
        "checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "monitor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("monitors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", check_status, nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("worker_id", sa.String(200)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("http_status", sa.Integer()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("content_size", sa.Integer()),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.Text()),
        sa.Column("changed", sa.Boolean(), nullable=False),
        sa.Column("change_score", sa.Numeric(8, 4)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_checks_monitor_created", "checks", ["monitor_id", "created_at"])
    op.create_index("ix_checks_status", "checks", ["status"])
    op.create_table(
        "snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "monitor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("monitors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "check_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("checks.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("text_content", sa.Text()),
        sa.Column("html_content", sa.Text()),
        sa.Column("numeric_value", sa.Numeric(20, 6)),
        sa.Column("availability_state", sa.String(32)),
        sa.Column("screenshot_key", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_snapshots_monitor_created", "snapshots", ["monitor_id", "created_at"])
    op.create_foreign_key(
        "fk_monitor_baseline", "monitors", "snapshots", ["baseline_snapshot_id"], ["id"], ondelete="SET NULL"
    )
    op.create_table(
        "change_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "monitor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("monitors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("previous_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("snapshots.id"), nullable=False),
        sa.Column(
            "current_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("snapshots.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("change_type", sa.String(64), nullable=False),
        sa.Column("change_score", sa.Numeric(8, 4), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("diff", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_changes_monitor_created", "change_events", ["monitor_id", "created_at"])


def downgrade() -> None:
    op.drop_table("change_events")
    op.drop_constraint("fk_monitor_baseline", "monitors", type_="foreignkey")
    op.drop_table("snapshots")
    op.drop_table("checks")
    op.drop_table("monitors")
    op.drop_table("projects")
    sa.Enum(name="check_status").drop(op.get_bind())
    sa.Enum(name="monitor_type").drop(op.get_bind())
