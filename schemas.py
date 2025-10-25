"""Pydantic schemas for request/response validation."""

from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class SourceConfig(BaseModel):
    """Source configuration for audit."""

    type: str = Field(..., description="Source type: github, url, or inline")
    url: Optional[HttpUrl] = Field(None, description="Source URL")
    ref: Optional[str] = Field(None, description="Git reference (branch, tag, commit)")
    inline_code: Optional[str] = Field(None, description="Inline code content")


class LLMConfig(BaseModel):
    """LLM configuration."""

    model: str = Field(default="anthropic/claude-3.5-sonnet", description="Model name")
    max_tokens: int = Field(default=8000, description="Maximum tokens")
    temperature: float = Field(default=0.1, description="Temperature setting")


class ClientMeta(BaseModel):
    """Client metadata."""

    project: Optional[str] = Field(None, description="Project name")
    contact: Optional[str] = Field(None, description="Contact email")


class CreateJobRequest(BaseModel):
    """Request schema for creating a new audit job."""

    source: SourceConfig = Field(..., description="Source configuration")
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM configuration")
    audit_profile: str = Field(..., description="Audit profile to use")
    timeout_sec: int = Field(default=900, description="Job timeout in seconds")
    idempotency_key: Optional[str] = Field(
        None, description="Idempotency key for duplicate prevention"
    )
    client_meta: Optional[ClientMeta] = Field(None, description="Client metadata")


class JobLinks(BaseModel):
    """Job links for HATEOAS."""

    self: str = Field(..., description="Link to job details")
    report: Optional[str] = Field(None, description="Link to job report")


class CreateJobResponse(BaseModel):
    """Response schema for job creation."""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status")
    created_at: str = Field(..., description="Creation timestamp")
    links: JobLinks = Field(..., description="Job links")


class ProgressInfo(BaseModel):
    """Job progress information."""

    phase: str = Field(..., description="Current phase")
    percent: int = Field(..., description="Progress percentage")


class MetricsInfo(BaseModel):
    """Job metrics information."""

    calls: int = Field(default=0, description="Number of LLM calls")
    prompt_tokens: int = Field(default=0, description="Prompt tokens used")
    completion_tokens: int = Field(default=0, description="Completion tokens used")
    elapsed_sec: float = Field(default=0.0, description="Elapsed time in seconds")


class JobStatusResponse(BaseModel):
    """Response schema for job status."""

    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status")
    progress: Optional[ProgressInfo] = Field(None, description="Progress information")
    metrics: Optional[MetricsInfo] = Field(None, description="Metrics information")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    links: JobLinks = Field(..., description="Job links")


class HealthResponse(BaseModel):
    """Health check response."""

    ok: bool = Field(..., description="Service health status")
    db: str = Field(..., description="Database status")
    version: str = Field(..., description="Application version")


class CancelJobResponse(BaseModel):
    """Response schema for job cancellation."""

    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="New job status")
    canceled_at: str = Field(..., description="Cancellation timestamp")
