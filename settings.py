"""Application settings loaded from environment variables."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration."""

    # Server settings
    port: int = Field(default=8080, description="Server port")
    host: str = Field(default="0.0.0.0", description="Server host")

    # Database settings
    db_url: str = Field(
        default="sqlite:////app/state/agent.db", description="Database URL"
    )

    # Data storage
    data_dir: str = Field(default="/app/data", description="Data directory for reports")

    # Worker settings
    worker_pool_size: int = Field(default=4, description="Number of worker processes")
    job_hard_timeout_sec: int = Field(
        default=1200, description="Hard timeout for jobs in seconds"
    )

    # OpenRouter settings
    openrouter_api_key: Optional[str] = Field(
        default=None, description="OpenRouter API key"
    )
    openrouter_model: str = Field(
        default="anthropic/claude-3.5-sonnet", description="OpenRouter model"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", description="OpenRouter base URL"
    )

    # Logging
    log_level: str = Field(default="info", description="Log level")

    # Dry run mode
    dry_run: bool = Field(
        default=True, description="Enable dry run mode when no API key"
    )

    # Application version
    version: str = Field(default="1.0.0", description="Application version")

    model_config = {"env_file": ".env", "case_sensitive": False}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-enable dry run if no API key
        if not self.openrouter_api_key:
            self.dry_run = True


# Global settings instance
settings = Settings()
