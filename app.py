"""Main FastAPI application for the audit agent."""

import json
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import PlainTextResponse
from loguru import logger
from sqlalchemy.orm import Session

from db import get_db, JobRepository, init_db, check_db_health
from llm_client import llm_client
from schemas import (
    CreateJobRequest,
    CreateJobResponse,
    JobStatusResponse,
    HealthResponse,
    CancelJobResponse,
    ProgressInfo,
    MetricsInfo,
    JobLinks,
)
from scheduler import scheduler
from settings import settings
from utils import generate_job_id, get_current_timestamp, read_report_file


# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    level=settings.log_level.upper(),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting audit agent application")

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Start scheduler
    await scheduler.start()
    logger.info("Scheduler started")

    yield

    # Cleanup
    logger.info("Shutting down audit agent application")
    await scheduler.stop()
    await llm_client.close()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Audit Agent",
    description="Smart contract audit agent with LLM integration",
    version=settings.version,
    lifespan=lifespan,
)


@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    db_healthy = check_db_health()

    return HealthResponse(
        ok=db_healthy, db="ready" if db_healthy else "error", version=settings.version
    )


@app.post(
    "/jobs", response_model=CreateJobResponse, status_code=status.HTTP_201_CREATED
)
async def create_job(request: CreateJobRequest, db: Session = Depends(get_db)):
    """Create a new audit job."""
    try:
        repo = JobRepository(db)

        # Check for idempotency
        if request.idempotency_key:
            existing_job = repo.get_job_by_idempotency_key(request.idempotency_key)
            if existing_job:
                logger.info(
                    f"Returning existing job for idempotency key: {request.idempotency_key}"
                )
                return CreateJobResponse(
                    job_id=existing_job.job_id,
                    status=existing_job.status,
                    created_at=existing_job.queued_at,
                    links=JobLinks(
                        self=f"/jobs/{existing_job.job_id}",
                        report=(
                            f"/jobs/{existing_job.job_id}/report"
                            if existing_job.status == "succeeded"
                            else None
                        ),
                    ),
                )

        # Generate job ID
        job_id = generate_job_id(request.dict(), request.idempotency_key)

        # Create job record
        job_data = {
            "job_id": job_id,
            "status": "queued",
            "queued_at": get_current_timestamp(),
            "progress_phase": "preflight",
            "progress_percent": 0,
            "payload_json": json.dumps(request.dict()),
            "idempotency_key": request.idempotency_key,
        }

        job = repo.create_job(job_data)

        logger.info(f"Created job {job_id} with status {job.status}")

        return CreateJobResponse(
            job_id=job.job_id,
            status=job.status,
            created_at=job.queued_at,
            links=JobLinks(
                self=f"/jobs/{job.job_id}", report=f"/jobs/{job.job_id}/report"
            ),
        )

    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}",
        )


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Get job status and progress."""
    try:
        repo = JobRepository(db)
        job = repo.get_job(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
            )

        # Parse metrics if available
        metrics = None
        if job.metrics_json:
            try:
                metrics_data = json.loads(job.metrics_json)
                metrics = MetricsInfo(**metrics_data)
            except Exception as e:
                logger.warning(f"Failed to parse metrics for job {job_id}: {e}")

        # Create progress info
        progress = ProgressInfo(phase=job.progress_phase, percent=job.progress_percent)

        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status,
            progress=progress,
            metrics=metrics,
            error_message=job.error_message,
            links=JobLinks(
                self=f"/jobs/{job.job_id}",
                report=(
                    f"/jobs/{job.job_id}/report" if job.status == "succeeded" else None
                ),
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}",
        )


@app.get("/jobs/{job_id}/report", response_class=PlainTextResponse)
async def get_job_report(job_id: str, db: Session = Depends(get_db)):
    """Get job report."""
    try:
        repo = JobRepository(db)
        job = repo.get_job(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
            )

        if job.status != "succeeded":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Report not ready. Job status: {job.status}",
            )

        if not job.report_path:
            logger.error(f"Job {job_id} has no report_path")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Report path not found",
            )

        logger.info(f"Reading report from path: {job.report_path}")
        try:
            report_content = read_report_file(job.report_path)
            return PlainTextResponse(content=report_content)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job report: {str(e)}",
        )


@app.post("/jobs/{job_id}/cancel", response_model=CancelJobResponse)
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """Cancel a job."""
    try:
        repo = JobRepository(db)
        job = repo.get_job(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
            )

        if job.status in ["succeeded", "failed", "canceled", "expired"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel job with status: {job.status}",
            )

        canceled_job = repo.cancel_job(job_id)

        if not canceled_job:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel job",
            )

        logger.info(f"Job {job_id} cancelled")

        return CancelJobResponse(
            job_id=canceled_job.job_id,
            status=canceled_job.status,
            canceled_at=canceled_job.finished_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel job: {str(e)}",
        )


# Signal handlers for graceful shutdown
def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {settings.host}:{settings.port}")
    uvicorn.run(
        "app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )
