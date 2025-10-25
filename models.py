"""SQLAlchemy models for the audit agent."""

from sqlalchemy import Column, Integer, String, Text, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Job(Base):
    """Job model for storing audit job information."""

    __tablename__ = "jobs"

    job_id = Column(String(64), primary_key=True, index=True)
    status = Column(
        String(20), nullable=False, index=True
    )  # queued, running, succeeded, failed, canceled, expired
    queued_at = Column(String(50), nullable=False)  # UTC ISO8601
    started_at = Column(String(50), nullable=True)  # UTC ISO8601
    finished_at = Column(String(50), nullable=True)  # UTC ISO8601
    progress_phase = Column(
        String(20), nullable=False, default="preflight"
    )  # preflight, fetch, analysis, llm, reporting, final
    progress_percent = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    metrics_json = Column(Text, nullable=True)  # JSON string with metrics
    report_path = Column(String(500), nullable=True)
    payload_json = Column(Text, nullable=False)  # Original request JSON
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)
    worker_id = Column(String(50), nullable=True)

    # Indexes for performance
    __table_args__ = (
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_queued_at", "queued_at"),
        Index("idx_jobs_idempotency", "idempotency_key"),
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "progress_phase": self.progress_phase,
            "progress_percent": self.progress_percent,
            "error_message": self.error_message,
            "metrics_json": self.metrics_json,
            "report_path": self.report_path,
            "payload_json": self.payload_json,
            "idempotency_key": self.idempotency_key,
            "worker_id": self.worker_id,
        }
