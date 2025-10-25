"""Test LLM client functionality."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
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
        with patch("llm_client.settings") as mock_settings, \
             patch("llm_client.load_mcp_config") as mock_load_config, \
             patch("llm_client.initialize_mcp_manager") as mock_init_mcp, \
             patch("llm_client.initialize_audit_agent") as mock_init_agent:
            
            mock_settings.dry_run = False
            mock_settings.openrouter_api_key = "test-api-key"
            mock_settings.openrouter_model = "anthropic/claude-3.5-sonnet"
            mock_settings.openrouter_base_url = "https://openrouter.ai/api/v1"

            # Mock MCP config
            mock_mcp_config = MagicMock()
            mock_mcp_config.enable_mcp = True
            mock_mcp_config.fallback_to_direct = True
            mock_load_config.return_value = mock_mcp_config

            # Mock MCP manager
            mock_mcp_manager = MagicMock()
            mock_init_mcp.return_value = mock_mcp_manager

            # Mock audit agent
            mock_audit_agent = MagicMock()
            mock_init_agent.return_value = mock_audit_agent

            client = LLMClient()
            yield client

    @pytest.fixture
    def llm_client_no_mcp(self):
        """Create LLM client with MCP disabled."""
        with patch("llm_client.settings") as mock_settings, \
             patch("llm_client.load_mcp_config") as mock_load_config:
            
            mock_settings.dry_run = False
            mock_settings.openrouter_api_key = "test-api-key"
            mock_settings.openrouter_model = "anthropic/claude-3.5-sonnet"
            mock_settings.openrouter_base_url = "https://openrouter.ai/api/v1"

            # Mock MCP config with MCP disabled
            mock_mcp_config = MagicMock()
            mock_mcp_config.enable_mcp = False
            mock_mcp_config.fallback_to_direct = True
            mock_load_config.return_value = mock_mcp_config

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
        """Test code analysis with MCP agent (mocked)."""
        code = "contract Test { function test() public {} }"
        audit_profile = "erc20_basic_v1"
        job_id = "test-job-456"
        payload = {
            "source": {"type": "inline", "inline_code": code},
            "audit_profile": audit_profile,
        }

        # Mock agent response
        mock_agent_result = {
            "report": "Mock audit report content",
            "metrics": {
                "calls": 1,
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "elapsed_sec": 1.5,
                "model": "anthropic/claude-3.5-sonnet",
                "cost_usd": 0.01
            },
            "error": None
        }

        # Mock the audit agent's audit_contract method
        mock_audit_agent = AsyncMock()
        mock_audit_agent.audit_contract = AsyncMock(return_value=mock_agent_result)
        
        # Mock _ensure_agent_initialized to set our mock agent
        async def mock_ensure_agent_initialized():
            llm_client_real.audit_agent = mock_audit_agent
            llm_client_real.agent_initialized = True
        
        llm_client_real._ensure_agent_initialized = mock_ensure_agent_initialized

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
        assert metrics["cost_usd"] == 0.01

    @pytest.mark.asyncio
    async def test_analyze_code_agent_fallback(self, llm_client_real):
        """Test agent fallback to direct LLM when agent fails."""
        code = "contract Test { function test() public {} }"
        audit_profile = "erc20_basic_v1"
        job_id = "test-job-789"
        payload = {
            "source": {"type": "inline", "inline_code": code},
            "audit_profile": audit_profile,
        }

        # Mock agent failure
        mock_agent_result = {
            "report": "Agent failed",
            "metrics": {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "elapsed_sec": 0.0, "model": "test", "cost_usd": 0.0},
            "error": "Agent authentication failed"
        }

        # Mock the audit agent to fail
        mock_audit_agent = AsyncMock()
        mock_audit_agent.audit_contract = AsyncMock(return_value=mock_agent_result)
        
        # Mock _ensure_agent_initialized to set our mock agent
        async def mock_ensure_agent_initialized():
            llm_client_real.audit_agent = mock_audit_agent
            llm_client_real.agent_initialized = True
        
        llm_client_real._ensure_agent_initialized = mock_ensure_agent_initialized

        # Mock direct LLM fallback
        mock_response_data = {
            "choices": [{"message": {"content": "Success after fallback"}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 100},
        }

        with patch.object(llm_client_real.client, "post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = lambda: mock_response_data
            mock_post.return_value = mock_response

            # Should fallback to direct LLM
            report, metrics = await llm_client_real.analyze_code(
                code, audit_profile, job_id, payload
            )

            assert report == "Success after fallback"
            assert metrics["calls"] == 1
            assert metrics["prompt_tokens"] == 50
            assert metrics["completion_tokens"] == 100

    @pytest.mark.asyncio
    async def test_analyze_code_agent_error(self, llm_client_real):
        """Test agent error handling."""
        code = "contract Test { function test() public {} }"
        audit_profile = "erc20_basic_v1"
        job_id = "test-job-error"
        payload = {
            "source": {"type": "inline", "inline_code": code},
            "audit_profile": audit_profile,
        }

        # Mock agent to raise exception
        mock_audit_agent = AsyncMock()
        mock_audit_agent.audit_contract = AsyncMock(side_effect=Exception("Agent failed"))
        
        # Mock _ensure_agent_initialized to set our mock agent
        async def mock_ensure_agent_initialized():
            llm_client_real.audit_agent = mock_audit_agent
            llm_client_real.agent_initialized = True
        
        llm_client_real._ensure_agent_initialized = mock_ensure_agent_initialized

        # Mock direct LLM fallback to also fail
        with patch.object(llm_client_real.client, "post") as mock_post:
            error_response = AsyncMock()
            error_response.status_code = 400
            error_response.text = "Bad Request"
            mock_post.return_value = error_response

            # Should raise exception after both agent and fallback fail
            with pytest.raises(Exception, match="OpenRouter API error"):
                await llm_client_real.analyze_code(code, audit_profile, job_id, payload)

    @pytest.mark.asyncio
    async def test_analyze_code_direct_llm(self, llm_client_no_mcp):
        """Test direct LLM call when MCP is disabled."""
        code = "contract Test { function test() public {} }"
        audit_profile = "erc20_basic_v1"
        job_id = "test-job-direct"
        payload = {
            "source": {"type": "inline", "inline_code": code},
            "audit_profile": audit_profile,
        }

        # Mock direct LLM response
        mock_response_data = {
            "choices": [{"message": {"content": "Direct LLM response"}}],
            "usage": {"prompt_tokens": 75, "completion_tokens": 150},
        }

        with patch.object(llm_client_no_mcp.client, "post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = lambda: mock_response_data
            mock_post.return_value = mock_response

            # Should use direct LLM call
            report, metrics = await llm_client_no_mcp.analyze_code(
                code, audit_profile, job_id, payload
            )

            assert report == "Direct LLM response"
            assert metrics["calls"] == 1
            assert metrics["prompt_tokens"] == 75
            assert metrics["completion_tokens"] == 150
            assert metrics["model"] == "anthropic/claude-3.5-sonnet"

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
