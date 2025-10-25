"""Pytest configuration and fixtures."""

import os
import tempfile
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import app
from db import get_db, Base
from models import Job


@pytest.fixture(scope="function")
def test_db_url():
    """Create temporary database URL for testing."""
    import tempfile
    import os
    
    # Create a temporary file for SQLite database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()
    
    db_url = f"sqlite:///{temp_db.name}"
    
    yield db_url
    
    # Cleanup
    try:
        os.unlink(temp_db.name)
    except OSError:
        pass


@pytest.fixture(scope="function")
def test_engine(test_db_url):
    """Create test database engine."""
    engine = create_engine(
        test_db_url,
        connect_args={"check_same_thread": False}
    )
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db_session(test_engine):
    """Create test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    session = TestingSessionLocal()
    
    # Clear all data before each test
    session.query(Job).delete()
    session.commit()
    
    yield session
    
    session.close()


@pytest.fixture(scope="function")
def test_client(test_db_session, test_engine):
    """Create test client with database override."""
    from fastapi import FastAPI
    from app import app as original_app
    import db
    
    # Override the global engine and session factory for tests
    original_engine = db.engine
    original_session_local = db.SessionLocal
    
    db.engine = test_engine
    db.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    # Ensure tables are created in the test engine
    Base.metadata.create_all(bind=test_engine)
    
    # Create a test app without lifespan to avoid database initialization
    test_app = FastAPI(
        title="Audit Agent Test",
        description="Test version of audit agent",
        version="1.0.0"
    )
    
    # Copy all routes from original app
    for route in original_app.routes:
        test_app.routes.append(route)
    
    # Don't override get_db - let it use the overridden SessionLocal
    
    try:
        with TestClient(test_app) as client:
            yield client
    finally:
        # Restore original engine and session factory
        db.engine = original_engine
        db.SessionLocal = original_session_local


@pytest.fixture
def sample_job_payload():
    """Sample job payload for testing."""
    return {
        "source": {
            "type": "inline",
            "inline_code": "contract Test { function test() public {} }"
        },
        "llm": {
            "model": "anthropic/claude-3.5-sonnet",
            "max_tokens": 8000,
            "temperature": 0.1
        },
        "audit_profile": "erc20_basic_v1",
        "timeout_sec": 900,
        "idempotency_key": "test-123",
        "client_meta": {
            "project": "test-project",
            "contact": "test@example.com"
        }
    }


@pytest.fixture
def sample_job(test_db_session, sample_job_payload):
    """Create sample job in database."""
    import json
    from utils import get_current_timestamp
    
    job = Job(
        job_id="test-job-123",
        status="queued",
        queued_at=get_current_timestamp(),
        progress_phase="preflight",
        progress_percent=0,
        payload_json=json.dumps(sample_job_payload),
        idempotency_key="test-123"
    )
    
    test_db_session.add(job)
    test_db_session.commit()
    test_db_session.refresh(job)
    
    return job
