"""Job workers for processing audit tasks."""

import asyncio
import json
from typing import Dict, Any

from loguru import logger
from sqlalchemy.orm import Session

from db import SessionLocal, JobRepository
from llm_client import llm_client
from models import Job
from settings import settings
from utils import write_report_file


class JobWorker:
    """Worker for processing individual audit jobs."""

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.cancel_flag = False

    async def process_job(self, job: Job):
        """Process a single audit job."""
        logger.info(f"Worker {self.worker_id} processing job {job.job_id}")

        db = SessionLocal()
        try:
            repo = JobRepository(db)

            # Parse job payload
            payload = json.loads(job.payload_json)

            # Process job phases
            await self._process_preflight(job, repo, payload)
            if self.cancel_flag:
                return

            await self._process_fetch(job, repo, payload)
            if self.cancel_flag:
                return

            await self._process_analysis(job, repo, payload)
            if self.cancel_flag:
                return

            await self._process_llm(job, repo, payload)
            if self.cancel_flag:
                return

            await self._process_reporting(job, repo, payload)
            if self.cancel_flag:
                return

            await self._process_final(job, repo, payload)

        except Exception as e:
            logger.error(f"Worker {self.worker_id} error for job {job.job_id}: {e}")
            self._mark_job_failed(db, job.job_id, str(e))
        finally:
            db.close()

    async def _process_preflight(
        self, job: Job, repo: JobRepository, payload: Dict[str, Any]
    ):
        """Process preflight phase."""
        logger.info(f"Job {job.job_id}: Starting preflight phase")

        repo.update_job_progress(job.job_id, "preflight", 10)

        # Validate payload
        if not self._validate_payload(payload):
            raise ValueError("Invalid job payload")

        # Check for cancellation
        if self._check_cancel_flag(job.job_id, repo):
            return

        # Simulate preflight work
        await asyncio.sleep(1)

        logger.info(f"Job {job.job_id}: Preflight phase completed")

    async def _process_fetch(
        self, job: Job, repo: JobRepository, payload: Dict[str, Any]
    ):
        """Process fetch phase."""
        logger.info(f"Job {job.job_id}: Starting fetch phase")

        repo.update_job_progress(job.job_id, "fetch", 25)

        # Check for cancellation
        if self._check_cancel_flag(job.job_id, repo):
            return

        # Fetch source code
        source_code = await self._fetch_source_code(payload["source"])

        # Check for cancellation
        if self._check_cancel_flag(job.job_id, repo):
            return

        # Store source code in job context (in real implementation, this would be stored)
        # job_context = {"source_code": source_code}

        logger.info(
            f"Job {job.job_id}: Fetch phase completed, {len(source_code)} characters fetched"
        )

    async def _process_analysis(
        self, job: Job, repo: JobRepository, payload: Dict[str, Any]
    ):
        """Process analysis phase."""
        logger.info(f"Job {job.job_id}: Starting analysis phase")

        repo.update_job_progress(job.job_id, "analysis", 50)

        # Check for cancellation
        if self._check_cancel_flag(job.job_id, repo):
            return

        # Simulate code analysis
        await asyncio.sleep(2)

        # Check for cancellation
        if self._check_cancel_flag(job.job_id, repo):
            return

        logger.info(f"Job {job.job_id}: Analysis phase completed")

    async def _process_llm(
        self, job: Job, repo: JobRepository, payload: Dict[str, Any]
    ):
        """Process LLM phase."""
        logger.info(f"Job {job.job_id}: Starting LLM phase")

        repo.update_job_progress(job.job_id, "llm", 75)

        # Check for cancellation
        if self._check_cancel_flag(job.job_id, repo):
            return

        # Get source code (in real implementation, this would be retrieved from storage)
        source_code = await self._fetch_source_code(payload["source"])

        # Check for cancellation
        if self._check_cancel_flag(job.job_id, repo):
            return

        # Call LLM for analysis
        audit_profile = payload.get("audit_profile", "general_v1")
        report_content, metrics = await llm_client.analyze_code(
            source_code, audit_profile, job.job_id, payload
        )

        # Check for cancellation
        if self._check_cancel_flag(job.job_id, repo):
            return

        # Update metrics
        repo.update_job_metrics(job.job_id, metrics)

        logger.info(f"Job {job.job_id}: LLM phase completed")

    async def _process_reporting(
        self, job: Job, repo: JobRepository, payload: Dict[str, Any]
    ):
        """Process reporting phase."""
        logger.info(f"Job {job.job_id}: Starting reporting phase")

        repo.update_job_progress(job.job_id, "reporting", 90)

        # Check for cancellation
        if self._check_cancel_flag(job.job_id, repo):
            return

        # Generate final report
        source_code = await self._fetch_source_code(payload["source"])
        audit_profile = payload.get("audit_profile", "general_v1")
        report_content, metrics = await llm_client.analyze_code(
            source_code, audit_profile, job.job_id, payload
        )

        # Check for cancellation
        if self._check_cancel_flag(job.job_id, repo):
            return

        # Write report to file
        report_path = write_report_file(job.job_id, report_content, settings.data_dir)

        # Update job with report path and metrics
        repo.update_job_status(job.job_id, "running", report_path=report_path)
        repo.update_job_metrics(job.job_id, metrics)

        logger.info(f"Job {job.job_id}: Reporting phase completed")

    async def _process_final(
        self, job: Job, repo: JobRepository, payload: Dict[str, Any]
    ):
        """Process final phase."""
        logger.info(f"Job {job.job_id}: Starting final phase")

        repo.update_job_progress(job.job_id, "final", 100)

        # Check for cancellation
        if self._check_cancel_flag(job.job_id, repo):
            return

        # Get current job to preserve report_path
        current_job = repo.get_job(job.job_id)
        report_path = current_job.report_path if current_job else None

        # Mark job as succeeded, preserving report_path
        repo.mark_job_finished(job.job_id, "succeeded", report_path=report_path)

        logger.info(f"Job {job.job_id}: Final phase completed - job succeeded")

    def _validate_payload(self, payload: Dict[str, Any]) -> bool:
        """Validate job payload."""
        required_fields = ["source", "audit_profile"]

        for field in required_fields:
            if field not in payload:
                logger.error(f"Missing required field: {field}")
                return False

        source = payload["source"]
        if "type" not in source:
            logger.error("Missing source type")
            return False

        return True

    async def _fetch_source_code(self, source_config: Dict[str, Any]) -> str:
        """Fetch source code from various sources."""
        source_type = source_config["type"]

        if source_type == "inline":
            return source_config.get("inline_code", "")

        elif source_type == "url":
            # In real implementation, this would fetch from URL
            return f"// Source code from URL: {source_config.get('url', '')}\n// This is a placeholder for fetched code"

        elif source_type == "github":
            # In real implementation, this would fetch from GitHub
            url = source_config.get("url", "")
            ref = source_config.get("ref", "main")
            return f"// Source code from GitHub: {url} (ref: {ref})\n// This is a placeholder for fetched code"

        else:
            raise ValueError(f"Unsupported source type: {source_type}")

    def _check_cancel_flag(self, job_id: str, repo: JobRepository) -> bool:
        """Check if job should be cancelled."""
        # Check local cancel flag
        if self.cancel_flag:
            logger.info(f"Job {job_id}: Cancelled by local flag")
            return True

        # Check database for cancellation
        job = repo.get_job(job_id)
        if job and job.status == "canceled":
            logger.info(f"Job {job_id}: Cancelled in database")
            self.cancel_flag = True
            return True

        return False

    def _mark_job_failed(self, db: Session, job_id: str, error_message: str):
        """Mark job as failed."""
        try:
            repo = JobRepository(db)
            repo.mark_job_finished(job_id, "failed", error_message=error_message)
            logger.error(f"Job {job_id} marked as failed: {error_message}")
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as failed: {e}")

    def cancel(self):
        """Cancel the worker."""
        self.cancel_flag = True
        logger.info(f"Worker {self.worker_id} cancellation requested")
