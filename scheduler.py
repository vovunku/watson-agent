"""Job scheduler for managing audit jobs."""

import asyncio
import json
import time
from typing import List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from db import SessionLocal, JobRepository
from models import Job
from settings import settings
from utils import get_current_timestamp


class JobScheduler:
    """Scheduler for managing job lifecycle."""
    
    def __init__(self):
        self.running = False
        self.worker_pool_size = settings.worker_pool_size
        self.job_timeout = settings.job_hard_timeout_sec
        self.heartbeat_interval = 30  # seconds
        self.last_heartbeat = time.time()
        
    async def start(self):
        """Start the scheduler."""
        logger.info("Starting job scheduler")
        self.running = True
        
        # Start background tasks
        asyncio.create_task(self._watchdog_loop())
        asyncio.create_task(self._job_dispatcher_loop())
        
        logger.info("Job scheduler started")
    
    async def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping job scheduler")
        self.running = False
    
    async def _watchdog_loop(self):
        """Watchdog loop to expire stale jobs."""
        while self.running:
            try:
                await self._expire_stale_jobs()
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.error(f"Error in watchdog loop: {e}")
                await asyncio.sleep(5)
    
    async def _job_dispatcher_loop(self):
        """Job dispatcher loop to assign queued jobs to workers."""
        while self.running:
            try:
                await self._dispatch_jobs()
                await asyncio.sleep(2)  # Check every 2 seconds
            except Exception as e:
                logger.error(f"Error in job dispatcher loop: {e}")
                await asyncio.sleep(5)
    
    async def _expire_stale_jobs(self):
        """Expire stale running jobs."""
        db = SessionLocal()
        try:
            repo = JobRepository(db)
            expired_count = repo.expire_stale_jobs(self.job_timeout)
            
            if expired_count > 0:
                logger.warning(f"Expired {expired_count} stale jobs")
            
            self.last_heartbeat = time.time()
        except Exception as e:
            logger.error(f"Error expiring stale jobs: {e}")
        finally:
            db.close()
    
    async def _dispatch_jobs(self):
        """Dispatch queued jobs to available workers."""
        db = SessionLocal()
        try:
            repo = JobRepository(db)
            
            # Get queued jobs
            queued_jobs = repo.get_queued_jobs(limit=self.worker_pool_size)
            
            # Get running jobs count
            running_jobs = repo.get_running_jobs()
            available_workers = self.worker_pool_size - len(running_jobs)
            
            if available_workers <= 0:
                return
            
            # Dispatch jobs to available workers
            for job in queued_jobs[:available_workers]:
                await self._assign_job_to_worker(job, repo)
                
        except Exception as e:
            logger.error(f"Error dispatching jobs: {e}")
        finally:
            db.close()
    
    async def _assign_job_to_worker(self, job: Job, repo: JobRepository):
        """Assign a job to a worker."""
        try:
            # Generate worker ID
            worker_id = f"worker-{int(time.time() * 1000)}"
            
            # Update job status atomically
            updated_job = repo.update_job_status(
                job.job_id,
                "running",
                started_at=get_current_timestamp(),
                worker_id=worker_id
            )
            
            if updated_job:
                logger.info(f"Assigned job {job.job_id} to worker {worker_id}")
                
                # Start worker task
                asyncio.create_task(self._run_job_worker(updated_job, worker_id))
            else:
                logger.warning(f"Failed to assign job {job.job_id} to worker")
                
        except Exception as e:
            logger.error(f"Error assigning job {job.job_id}: {e}")
            # Mark job as failed
            repo.update_job_status(
                job.job_id,
                "failed",
                error_message=f"Failed to assign to worker: {str(e)}",
                finished_at=get_current_timestamp()
            )
    
    async def _run_job_worker(self, job: Job, worker_id: str):
        """Run a job worker."""
        from workers import JobWorker
        
        worker = JobWorker(worker_id)
        try:
            await worker.process_job(job)
        except Exception as e:
            logger.error(f"Worker {worker_id} failed for job {job.job_id}: {e}")
            
            # Mark job as failed
            db = SessionLocal()
            try:
                repo = JobRepository(db)
                repo.update_job_status(
                    job.job_id,
                    "failed",
                    error_message=f"Worker error: {str(e)}",
                    finished_at=get_current_timestamp()
                )
            finally:
                db.close()


# Global scheduler instance
scheduler = JobScheduler()
