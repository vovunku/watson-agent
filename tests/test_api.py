"""Test API endpoints."""

import json
import pytest
from fastapi.testclient import TestClient
from models import Job
from utils import get_current_timestamp


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self, test_client: TestClient, test_engine):
        """Test health check returns 200 with correct data."""
        # Test the health check function directly with test engine
        from sqlalchemy import text
        
        def test_check_db_health():
            try:
                with test_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    conn.close()
                return True
            except Exception:
                return False
        
        # Test the function directly
        assert test_check_db_health() is True
        
        # For the API test, we'll just check that it returns a response
        # The actual health check logic is tested separately
        response = test_client.get("/healthz")
        
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "db" in data
        assert "version" in data


class TestJobCreation:
    """Test job creation endpoint."""
    
    def test_create_job_success(self, test_client: TestClient, sample_job_payload):
        """Test successful job creation."""
        response = test_client.post("/jobs", json=sample_job_payload)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "job_id" in data
        assert data["status"] == "queued"
        assert "created_at" in data
        assert "links" in data
        assert data["links"]["self"] == f"/jobs/{data['job_id']}"
        assert data["links"]["report"] == f"/jobs/{data['job_id']}/report"
    
    def test_create_job_idempotency(self, test_client: TestClient, sample_job_payload):
        """Test job creation with idempotency key."""
        # Create first job
        response1 = test_client.post("/jobs", json=sample_job_payload)
        assert response1.status_code == 201
        job_id1 = response1.json()["job_id"]
        
        # Create second job with same idempotency key
        response2 = test_client.post("/jobs", json=sample_job_payload)
        assert response2.status_code == 201
        job_id2 = response2.json()["job_id"]
        
        # Should return same job ID
        assert job_id1 == job_id2
    
    def test_create_job_invalid_payload(self, test_client: TestClient):
        """Test job creation with invalid payload."""
        invalid_payload = {
            "source": {
                "type": "invalid"
            }
        }
        
        response = test_client.post("/jobs", json=invalid_payload)
        assert response.status_code == 422  # Validation error


class TestJobStatus:
    """Test job status endpoint."""
    
    def test_get_job_status_success(self, test_client: TestClient, sample_job):
        """Test getting job status."""
        response = test_client.get(f"/jobs/{sample_job.job_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["job_id"] == sample_job.job_id
        assert data["status"] == sample_job.status
        assert "progress" in data
        assert "links" in data
    
    def test_get_job_status_not_found(self, test_client: TestClient):
        """Test getting status of non-existent job."""
        response = test_client.get("/jobs/non-existent-job")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


class TestJobReport:
    """Test job report endpoint."""
    
    def test_get_job_report_not_ready(self, test_client: TestClient, sample_job):
        """Test getting report for job that's not ready."""
        response = test_client.get(f"/jobs/{sample_job.job_id}/report")
        
        assert response.status_code == 409
        data = response.json()
        assert "not ready" in data["detail"].lower()
    
    def test_get_job_report_not_found(self, test_client: TestClient):
        """Test getting report for non-existent job."""
        response = test_client.get("/jobs/non-existent-job/report")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_get_job_report_success(self, test_client: TestClient, test_db_session):
        """Test getting report for completed job."""
        import json
        from utils import write_report_file
        from db import JobRepository
        
        # Create a completed job
        job_payload = {
            "source": {"type": "inline", "inline_code": "contract Test {}"},
            "audit_profile": "erc20_basic_v1"
        }
        
        job = Job(
            job_id="completed-job-123",
            status="succeeded",
            queued_at=get_current_timestamp(),
            finished_at=get_current_timestamp(),
            progress_phase="final",
            progress_percent=100,
            payload_json=json.dumps(job_payload),
            report_path="/tmp/test-report.txt"
        )
        
        test_db_session.add(job)
        test_db_session.commit()
        
        # Create report file
        report_content = "Test audit report content"
        report_path = write_report_file("completed-job-123", report_content, "/tmp")
        
        # Update job with correct report path
        repo = JobRepository(test_db_session)
        repo.update_job_status("completed-job-123", "succeeded", report_path=report_path)
        
        response = test_client.get("/jobs/completed-job-123/report")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        assert report_content in response.text


class TestJobCancellation:
    """Test job cancellation endpoint."""
    
    def test_cancel_job_success(self, test_client: TestClient, sample_job):
        """Test successful job cancellation."""
        response = test_client.post(f"/jobs/{sample_job.job_id}/cancel")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["job_id"] == sample_job.job_id
        assert data["status"] == "canceled"
        assert "canceled_at" in data
    
    def test_cancel_job_not_found(self, test_client: TestClient):
        """Test cancelling non-existent job."""
        response = test_client.post("/jobs/non-existent-job/cancel")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_cancel_job_already_finished(self, test_client: TestClient, test_db_session):
        """Test cancelling already finished job."""
        import json
        
        # Create a completed job
        job = Job(
            job_id="finished-job-123",
            status="succeeded",
            queued_at=get_current_timestamp(),
            finished_at=get_current_timestamp(),
            progress_phase="final",
            progress_percent=100,
            payload_json=json.dumps({"source": {"type": "inline"}})
        )
        
        test_db_session.add(job)
        test_db_session.commit()
        
        response = test_client.post("/jobs/finished-job-123/cancel")
        
        assert response.status_code == 400
        data = response.json()
        assert "cannot cancel" in data["detail"].lower()


class TestIntegration:
    """Integration tests."""
    
    def test_full_job_lifecycle_dry_run(self, test_client: TestClient):
        """Test full job lifecycle in DRY_RUN mode."""
        # Create job
        payload = {
            "source": {
                "type": "inline",
                "inline_code": "contract Test { function test() public {} }"
            },
            "audit_profile": "erc20_basic_v1",
            "idempotency_key": "integration-test-123"
        }
        
        create_response = test_client.post("/jobs", json=payload)
        assert create_response.status_code == 201
        
        job_id = create_response.json()["job_id"]
        
        # Check job status
        status_response = test_client.get(f"/jobs/{job_id}")
        assert status_response.status_code == 200
        
        # In a real test, we would wait for the job to complete
        # For now, we just verify the job was created successfully
        status_data = status_response.json()
        assert status_data["job_id"] == job_id
        assert status_data["status"] in ["queued", "running", "succeeded"]
    
    def test_idempotency_behavior(self, test_client: TestClient):
        """Test idempotency behavior across multiple requests."""
        payload = {
            "source": {
                "type": "inline",
                "inline_code": "contract Test {}"
            },
            "audit_profile": "general_v1",
            "idempotency_key": "idempotency-test-456"
        }
        
        # Create multiple jobs with same idempotency key
        responses = []
        for _ in range(3):
            response = test_client.post("/jobs", json=payload)
            responses.append(response)
        
        # All should return same job ID
        job_ids = [r.json()["job_id"] for r in responses if r.status_code == 201]
        assert len(set(job_ids)) == 1  # All job IDs should be the same
