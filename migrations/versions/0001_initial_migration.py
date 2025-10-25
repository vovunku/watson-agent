"""Initial migration

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create jobs table
    op.create_table(
        "jobs",
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("queued_at", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.String(length=50), nullable=True),
        sa.Column("finished_at", sa.String(length=50), nullable=True),
        sa.Column("progress_phase", sa.String(length=20), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("report_path", sa.String(length=500), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("worker_id", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("job_id"),
    )

    # Create indexes
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("idx_jobs_queued_at", "jobs", ["queued_at"])
    op.create_index("idx_jobs_idempotency", "jobs", ["idempotency_key"])

    # Create unique constraint for idempotency_key
    op.create_unique_constraint("uq_jobs_idempotency_key", "jobs", ["idempotency_key"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_jobs_idempotency", table_name="jobs")
    op.drop_index("idx_jobs_queued_at", table_name="jobs")
    op.drop_index("idx_jobs_status", table_name="jobs")

    # Drop table
    op.drop_table("jobs")
