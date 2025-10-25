"""Test database operations."""

import json
import pytest
from sqlalchemy.orm import Session

from db import JobRepository, check_db_health
from models import Job
from utils import get_current_timestamp


class TestJobRepository:
    """Test job repository operations."""
    
    def test_create_job(self, test_db_session: Session):
        """Test job creation."""
        repo = JobRepository(test_db_session)
        
        job_data = {
            "job_id": "test-job-123",
            "status": "queued",
            "queued_at": get_current_timestamp(),
            "progress_phase": "preflight",
            "progress_percent": 0,
            "payload_json": json.dumps({"source": {"type": "inline"}}),
            "idempotency_key": "test-key-123"
        }
        
        job = repo.create_job(job_data)
        
        assert job.job_id == "test-job-123"
        assert job.status == "queued"
        assert job.idempotency_key == "test-key-123"
    
    def test_get_job(self, test_db_session: Session, sample_job: Job):
        """Test getting job by ID."""
        repo = JobRepository(test_db_session)
        
        job = repo.get_job(sample_job.job_id)
        
        assert job is not None
        assert job.job_id == sample_job.job_id
        assert job.status == sample_job.status
    
    def test_get_job_not_found(self, test_db_session: Session):
        """Test getting non-existent job."""
        repo = JobRepository(test_db_session)
        
        job = repo.get_job("non-existent-job")
        
        assert job is None
    
    def test_get_job_by_idempotency_key(self, test_db_session: Session, sample_job: Job):
        """Test getting job by idempotency key."""
        repo = JobRepository(test_db_session)
        
        job = repo.get_job_by_idempotency_key(sample_job.idempotency_key)
        
        assert job is not None
        assert job.job_id == sample_job.job_id
        assert job.idempotency_key == sample_job.idempotency_key
    
    def test_update_job_status(self, test_db_session: Session, sample_job: Job):
        """Test updating job status."""
        repo = JobRepository(test_db_session)
        
        updated_job = repo.update_job_status(
            sample_job.job_id,
            "running",
            started_at=get_current_timestamp(),
            worker_id="worker-123"
        )
        
        assert updated_job is not None
        assert updated_job.status == "running"
        assert updated_job.started_at is not None
        assert updated_job.worker_id == "worker-123"
    
    def test_update_job_progress(self, test_db_session: Session, sample_job: Job):
        """Test updating job progress."""
        repo = JobRepository(test_db_session)
        
        updated_job = repo.update_job_progress(sample_job.job_id, "analysis", 50)
        
        assert updated_job is not None
        assert updated_job.progress_phase == "analysis"
        assert updated_job.progress_percent == 50
        assert updated_job.status == "running"
    
    def test_update_job_metrics(self, test_db_session: Session, sample_job: Job):
        """Test updating job metrics."""
        repo = JobRepository(test_db_session)
        
        metrics = {
            "calls": 1,
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "elapsed_sec": 30.5
        }
        
        updated_job = repo.update_job_metrics(sample_job.job_id, metrics)
        
        assert updated_job is not None
        assert updated_job.metrics_json is not None
        
        # Parse and verify metrics
        parsed_metrics = json.loads(updated_job.metrics_json)
        assert parsed_metrics["calls"] == 1
        assert parsed_metrics["prompt_tokens"] == 1000
        assert parsed_metrics["completion_tokens"] == 500
        assert parsed_metrics["elapsed_sec"] == 30.5
    
    def test_set_job_worker(self, test_db_session: Session, sample_job: Job):
        """Test setting worker ID for job."""
        repo = JobRepository(test_db_session)
        
        updated_job = repo.set_job_worker(sample_job.job_id, "worker-456")
        
        assert updated_job is not None
        assert updated_job.worker_id == "worker-456"
        assert updated_job.status == "running"
    
    def test_get_queued_jobs(self, test_db_session: Session):
        """Test getting queued jobs."""
        repo = JobRepository(test_db_session)
        
        # Create multiple queued jobs
        for i in range(3):
            job_data = {
                "job_id": f"queued-job-{i}",
                "status": "queued",
                "queued_at": get_current_timestamp(),
                "progress_phase": "preflight",
                "progress_percent": 0,
                "payload_json": json.dumps({"source": {"type": "inline"}})
            }
            repo.create_job(job_data)
        
        queued_jobs = repo.get_queued_jobs(limit=5)
        
        assert len(queued_jobs) == 3
        for job in queued_jobs:
            assert job.status == "queued"
    
    def test_get_running_jobs(self, test_db_session: Session):
        """Test getting running jobs."""
        repo = JobRepository(test_db_session)
        
        # Create a running job
        job_data = {
            "job_id": "running-job-123",
            "status": "running",
            "queued_at": get_current_timestamp(),
            "started_at": get_current_timestamp(),
            "progress_phase": "analysis",
            "progress_percent": 50,
            "payload_json": json.dumps({"source": {"type": "inline"}}),
            "worker_id": "worker-123"
        }
        repo.create_job(job_data)
        
        running_jobs = repo.get_running_jobs()
        
        assert len(running_jobs) == 1
        assert running_jobs[0].status == "running"
        assert running_jobs[0].worker_id == "worker-123"
    
    def test_mark_job_finished(self, test_db_session: Session, sample_job: Job):
        """Test marking job as finished."""
        repo = JobRepository(test_db_session)
        
        updated_job = repo.mark_job_finished(
            sample_job.job_id,
            "succeeded",
            report_path="/tmp/report.txt"
        )
        
        assert updated_job is not None
        assert updated_job.status == "succeeded"
        assert updated_job.finished_at is not None
        assert updated_job.report_path == "/tmp/report.txt"
    
    def test_mark_job_finished_with_error(self, test_db_session: Session, sample_job: Job):
        """Test marking job as finished with error."""
        repo = JobRepository(test_db_session)
        
        error_message = "Test error message"
        updated_job = repo.mark_job_finished(
            sample_job.job_id,
            "failed",
            error_message=error_message
        )
        
        assert updated_job is not None
        assert updated_job.status == "failed"
        assert updated_job.finished_at is not None
        assert updated_job.error_message == error_message
    
    def test_cancel_job(self, test_db_session: Session, sample_job: Job):
        """Test cancelling a job."""
        repo = JobRepository(test_db_session)
        
        canceled_job = repo.cancel_job(sample_job.job_id)
        
        assert canceled_job is not None
        assert canceled_job.status == "canceled"
        assert canceled_job.finished_at is not None
    
    def test_cancel_job_already_finished(self, test_db_session: Session):
        """Test cancelling an already finished job."""
        repo = JobRepository(test_db_session)
        
        # Create a finished job
        job_data = {
            "job_id": "finished-job-123",
            "status": "succeeded",
            "queued_at": get_current_timestamp(),
            "finished_at": get_current_timestamp(),
            "progress_phase": "final",
            "progress_percent": 100,
            "payload_json": json.dumps({"source": {"type": "inline"}})
        }
        repo.create_job(job_data)
        
        canceled_job = repo.cancel_job("finished-job-123")
        
        assert canceled_job is None  # Should not be able to cancel finished job
    
    def test_expire_stale_jobs(self, test_db_session: Session):
        """Test expiring stale jobs."""
        repo = JobRepository(test_db_session)
        
        # Create a stale running job (started 2 hours ago)
        from datetime import datetime, timezone, timedelta
        stale_time = datetime.now(timezone.utc) - timedelta(hours=2)
        stale_time_str = stale_time.isoformat()
        
        job_data = {
            "job_id": "stale-job-123",
            "status": "running",
            "queued_at": get_current_timestamp(),
            "started_at": stale_time_str,
            "progress_phase": "analysis",
            "progress_percent": 50,
            "payload_json": json.dumps({"source": {"type": "inline"}}),
            "worker_id": "worker-123"
        }
        repo.create_job(job_data)
        
        # Expire jobs older than 1 hour
        expired_count = repo.expire_stale_jobs(3600)  # 1 hour in seconds
        
        assert expired_count == 1
        
        # Check that job was expired
        expired_job = repo.get_job("stale-job-123")
        assert expired_job.status == "expired"
        assert expired_job.error_message == "Job expired due to timeout"


class TestDatabaseHealth:
    """Test database health checks."""
    
    def test_check_db_health(self, test_db_session: Session):
        """Test database health check."""
        # Should return True for healthy database
        assert check_db_health() is True
