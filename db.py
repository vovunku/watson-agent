"""Database configuration and session management."""

import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from models import Base, Job
from settings import settings
from utils import get_current_timestamp


# Create synchronous engine for SQLite
engine = create_engine(
    settings.db_url,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
    echo=False
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class JobRepository:
    """Repository for job operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_job(self, job_data: dict) -> Job:
        """Create a new job."""
        job = Job(**job_data)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return self.db.query(Job).filter(Job.job_id == job_id).first()
    
    def get_job_by_idempotency_key(self, idempotency_key: str) -> Optional[Job]:
        """Get job by idempotency key."""
        return self.db.query(Job).filter(Job.idempotency_key == idempotency_key).first()
    
    def update_job_status(self, job_id: str, status: str, **kwargs) -> Optional[Job]:
        """Update job status and other fields."""
        job = self.get_job(job_id)
        if not job:
            return None
        
        job.status = status
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)
        
        self.db.commit()
        self.db.refresh(job)
        return job
    
    def update_job_progress(self, job_id: str, phase: str, percent: int) -> Optional[Job]:
        """Update job progress."""
        return self.update_job_status(job_id, "running", progress_phase=phase, progress_percent=percent)
    
    def update_job_metrics(self, job_id: str, metrics: dict) -> Optional[Job]:
        """Update job metrics."""
        return self.update_job_status(job_id, "running", metrics_json=json.dumps(metrics))
    
    def set_job_worker(self, job_id: str, worker_id: str) -> Optional[Job]:
        """Set worker ID for job."""
        return self.update_job_status(job_id, "running", worker_id=worker_id)
    
    def get_queued_jobs(self, limit: int = 10) -> list[Job]:
        """Get queued jobs for processing."""
        return self.db.query(Job).filter(Job.status == "queued").order_by(Job.queued_at).limit(limit).all()
    
    def get_running_jobs(self) -> list[Job]:
        """Get all running jobs."""
        return self.db.query(Job).filter(Job.status == "running").all()
    
    def mark_job_finished(self, job_id: str, status: str, report_path: Optional[str] = None, error_message: Optional[str] = None) -> Optional[Job]:
        """Mark job as finished."""
        return self.update_job_status(
            job_id, 
            status, 
            finished_at=get_current_timestamp(),
            report_path=report_path,
            error_message=error_message
        )
    
    def cancel_job(self, job_id: str) -> Optional[Job]:
        """Cancel a job."""
        job = self.get_job(job_id)
        if not job or job.status in ["succeeded", "failed", "canceled", "expired"]:
            return None
        
        return self.update_job_status(job_id, "canceled", finished_at=get_current_timestamp())
    
    def expire_stale_jobs(self, timeout_seconds: int) -> int:
        """Expire stale running jobs."""
        from datetime import datetime, timezone, timedelta
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
        cutoff_str = cutoff_time.isoformat()
        
        # Find stale running jobs
        stale_jobs = self.db.query(Job).filter(
            Job.status == "running",
            Job.started_at < cutoff_str
        ).all()
        
        count = 0
        for job in stale_jobs:
            job.status = "expired"
            job.finished_at = get_current_timestamp()
            job.error_message = "Job expired due to timeout"
            count += 1
        
        if count > 0:
            self.db.commit()
        
        return count


def check_db_health() -> bool:
    """Check database health."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.close()
        return True
    except Exception:
        return False
