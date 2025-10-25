"""Test LLM client functionality."""

import pytest
from unittest.mock import AsyncMock, patch
from llm_client import LLMClient


class TestLLMClient:
    """Test LLM client."""

    @pytest.fixture
    def llm_client_dry_run(self):
        """Create LLM client in DRY_RUN mode."""
        with patch("llm_client.settings") as mock_settings:
            mock_settings.dry_run = True
            mock_settings.openrouter_api_key = None
            mock_settings.openrouter_model = "test-model"
            mock_settings.openrouter_base_url = "https://test.openrouter.ai/api/v1"

            client = LLMClient()
            yield client

    @pytest.fixture
    def llm_client_real(self):
        """Create LLM client with real API key."""
        with patch("llm_client.settings") as mock_settings:
            mock_settings.dry_run = False
            mock_settings.openrouter_api_key = "test-api-key"
            mock_settings.openrouter_model = "anthropic/claude-3.5-sonnet"
            mock_settings.openrouter_base_url = "https://openrouter.ai/api/v1"

            client = LLMClient()
            yield client

    @pytest.mark.asyncio
    async def test_analyze_code_dry_run(self, llm_client_dry_run):
        """Test code analysis in DRY_RUN mode."""
        code = "contract Test { function test() public {} }"
        audit_profile = "erc20_basic_v1"
        job_id = "test-job-123"
        payload = {
            "source": {"type": "inline", "inline_code": code},
            "audit_profile": audit_profile,
        }

        report, metrics = await llm_client_dry_run.analyze_code(
            code, audit_profile, job_id, payload
        )

        # Should return a report
        assert isinstance(report, str)
        assert len(report) > 0

        # Should contain expected sections
        assert "# Audit Report" in report
        assert job_id in report
        assert "DRY_RUN mode" in report

        # Should return metrics
        assert isinstance(metrics, dict)
        assert "calls" in metrics
        assert "prompt_tokens" in metrics
        assert "completion_tokens" in metrics
        assert "elapsed_sec" in metrics
        assert "model" in metrics
        assert "cost_usd" in metrics

        # DRY_RUN should have specific values
        assert metrics["model"] == "dry_run"
        assert metrics["cost_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_analyze_code_real_api_success(self, llm_client_real):
        """Test code analysis with real API (mocked)."""
        code = "contract Test { function test() public {} }"
        audit_profile = "erc20_basic_v1"
        job_id = "test-job-456"
        payload = {
            "source": {"type": "inline", "inline_code": code},
            "audit_profile": audit_profile,
        }

        # Mock successful API response
        mock_response_data = {
            "choices": [{"message": {"content": "Mock audit report content"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 200},
        }

        with patch.object(llm_client_real.client, "post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            # Mock json() as a synchronous method that returns the data directly
            mock_response.json = lambda: mock_response_data
            mock_post.return_value = mock_response

            report, metrics = await llm_client_real.analyze_code(
                code, audit_profile, job_id, payload
            )

            # Should return the mocked report
            assert report == "Mock audit report content"

            # Should return correct metrics
            assert metrics["calls"] == 1
            assert metrics["prompt_tokens"] == 100
            assert metrics["completion_tokens"] == 200
            assert metrics["model"] == "anthropic/claude-3.5-sonnet"
            assert metrics["cost_usd"] > 0

    @pytest.mark.asyncio
    async def test_analyze_code_api_rate_limit(self, llm_client_real):
        """Test API rate limit handling."""
        code = "contract Test { function test() public {} }"
        audit_profile = "erc20_basic_v1"
        job_id = "test-job-789"
        payload = {
            "source": {"type": "inline", "inline_code": code},
            "audit_profile": audit_profile,
        }

        # Mock rate limit response followed by success
        with patch.object(llm_client_real.client, "post") as mock_post:
            # First call returns 429 (rate limit)
            rate_limit_response = AsyncMock()
            rate_limit_response.status_code = 429

            # Second call returns success
            success_response = AsyncMock()
            success_response.status_code = 200
            success_response_data = {
                "choices": [{"message": {"content": "Success after retry"}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 100},
            }
            # Mock json() as a synchronous method that returns the data directly
            success_response.json = lambda: success_response_data

            mock_post.side_effect = [rate_limit_response, success_response]

            # Should retry and eventually succeed
            report, metrics = await llm_client_real.analyze_code(
                code, audit_profile, job_id, payload
            )

            assert report == "Success after retry"
            assert metrics["calls"] == 1
            assert mock_post.call_count == 2  # Should have retried

    @pytest.mark.asyncio
    async def test_analyze_code_api_error(self, llm_client_real):
        """Test API error handling."""
        code = "contract Test { function test() public {} }"
        audit_profile = "erc20_basic_v1"
        job_id = "test-job-error"
        payload = {
            "source": {"type": "inline", "inline_code": code},
            "audit_profile": audit_profile,
        }

        # Mock API error
        with patch.object(llm_client_real.client, "post") as mock_post:
            error_response = AsyncMock()
            error_response.status_code = 400
            error_response.text = "Bad Request"
            mock_post.return_value = error_response

            # Should raise exception
            with pytest.raises(Exception, match="OpenRouter API error"):
                await llm_client_real.analyze_code(code, audit_profile, job_id, payload)

    def test_build_prompt(self, llm_client_dry_run):
        """Test prompt building."""
        code = "contract Test { function test() public {} }"
        audit_profile = "erc20_basic_v1"

        prompt = llm_client_dry_run._build_prompt(code, audit_profile)

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert code in prompt
        assert "ERC20" in prompt or "security" in prompt.lower()

    def test_calculate_cost(self, llm_client_dry_run):
        """Test cost calculation."""
        usage = {"prompt_tokens": 1000, "completion_tokens": 500}

        cost = llm_client_dry_run._calculate_cost(usage)

        assert isinstance(cost, float)
        assert cost >= 0

    @pytest.mark.asyncio
    async def test_close_client(self, llm_client_dry_run):
        """Test client cleanup."""
        # Should not raise exception
        await llm_client_dry_run.close()
