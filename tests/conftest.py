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


@pytest.fixture(scope="session")
def test_db_url():
    """Create temporary database URL for testing."""
    # Use in-memory SQLite database for better reliability in CI
    # This avoids file permission issues in GitHub Actions
    db_url = "sqlite:///:memory:"
    
    yield db_url


@pytest.fixture(scope="session")
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
    
    # Create a test app without lifespan to avoid database initialization
    test_app = FastAPI(
        title="Audit Agent Test",
        description="Test version of audit agent",
        version="1.0.0"
    )
    
    # Copy all routes from original app
    for route in original_app.routes:
        test_app.routes.append(route)
    
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass
    
    test_app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(test_app) as client:
        yield client
    
    test_app.dependency_overrides.clear()


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
