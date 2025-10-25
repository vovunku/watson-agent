"""LLM client for OpenRouter API with DRY_RUN fallback."""

import asyncio
import random
import time
from typing import Dict, Any, Tuple

import httpx
from loguru import logger

from settings import settings
from utils import generate_deterministic_report


class LLMClient:
    """Client for OpenRouter API with retry logic and metrics."""

    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.base_url = settings.openrouter_base_url
        self.dry_run = settings.dry_run or not self.api_key

        # HTTP client with timeout
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0),
            headers={
                "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://audit-agent.local",
                "X-Title": "Audit Agent",
            },
        )

        logger.info(
            f"LLM Client initialized: dry_run={self.dry_run}, model={self.model}"
        )

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def analyze_code(
        self, code: str, audit_profile: str, job_id: str, payload: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Analyze code using LLM or generate deterministic report.

        Returns:
            Tuple of (report_content, metrics)
        """
        if self.dry_run:
            return await self._generate_dry_run_report(
                code, audit_profile, job_id, payload
            )
        else:
            return await self._call_openrouter_api(code, audit_profile, job_id)

    async def _generate_dry_run_report(
        self, code: str, audit_profile: str, job_id: str, payload: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate deterministic report for DRY_RUN mode."""
        logger.info(f"Generating DRY_RUN report for job {job_id}")

        # Simulate processing time
        await asyncio.sleep(random.uniform(2, 5))

        # Generate deterministic report
        report_content = generate_deterministic_report(payload, job_id)

        # Calculate metrics
        metrics = {
            "calls": 1,
            "prompt_tokens": len(code) // 4,  # Rough estimate
            "completion_tokens": len(report_content) // 4,
            "elapsed_sec": random.uniform(3, 6),
            "model": "dry_run",
            "cost_usd": 0.0,
        }

        return report_content, metrics

    async def _call_openrouter_api(
        self, code: str, audit_profile: str, job_id: str
    ) -> Tuple[str, Dict[str, Any]]:
        """Call OpenRouter API with retry logic."""
        logger.info(f"Calling OpenRouter API for job {job_id}")

        # Prepare prompt based on audit profile
        prompt = self._build_prompt(code, audit_profile)

        # Prepare request payload
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert smart contract auditor. Analyze the provided code and generate a comprehensive audit report.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 8000,
            "temperature": 0.1,
        }

        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                start_time = time.time()

                response = await self.client.post(
                    f"{self.base_url}/chat/completions", json=payload
                )

                elapsed = time.time() - start_time

                if response.status_code == 200:
                    data = await response.json()
                    content = data["choices"][0]["message"]["content"]

                    # Extract usage metrics
                    usage = data.get("usage", {})
                    metrics = {
                        "calls": 1,
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "elapsed_sec": elapsed,
                        "model": self.model,
                        "cost_usd": self._calculate_cost(usage),
                    }

                    logger.info(f"OpenRouter API call successful for job {job_id}")
                    return content, metrics

                elif response.status_code == 429:
                    # Rate limit - exponential backoff with jitter
                    delay = base_delay * (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Rate limited, retrying in {delay:.2f}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue

                elif response.status_code >= 500:
                    # Server error - retry with backoff
                    delay = base_delay * (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Server error {response.status_code}, retrying in {delay:.2f}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue

                else:
                    # Client error - don't retry
                    error_msg = f"OpenRouter API error: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

            except httpx.TimeoutException:
                delay = base_delay * (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    f"Timeout, retrying in {delay:.2f}s (attempt {attempt + 1})"
                )
                await asyncio.sleep(delay)
                continue

            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"OpenRouter API call failed after {max_retries} attempts: {e}"
                    )
                    raise
                delay = base_delay * (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    f"API call failed, retrying in {delay:.2f}s (attempt {attempt + 1}): {e}"
                )
                await asyncio.sleep(delay)

        raise Exception("OpenRouter API call failed after all retries")

    def _build_prompt(self, code: str, audit_profile: str) -> str:
        """Build prompt for code analysis."""
        profile_prompts = {
            "erc20_basic_v1": """
Analyze this smart contract code for ERC20 compliance and common vulnerabilities:

1. ERC20 Standard Compliance:
   - Check if all required functions are implemented
   - Verify function signatures and return values
   - Ensure proper event emissions

2. Security Issues:
   - Reentrancy vulnerabilities
   - Integer overflow/underflow
   - Access control issues
   - Front-running vulnerabilities
   - Gas optimization issues

3. Code Quality:
   - Unused variables or functions
   - Missing error handling
   - Inconsistent naming conventions

Please provide a detailed report with:
- Summary of findings
- List of issues with severity levels (high/medium/low)
- Specific locations and descriptions
- Recommendations for fixes
- Gas optimization suggestions

Code to analyze:
```solidity
{code}
```
""",
            "general_v1": """
Perform a comprehensive security audit of this smart contract code:

1. Security Vulnerabilities:
   - Reentrancy attacks
   - Integer overflow/underflow
   - Access control bypass
   - Front-running attacks
   - Denial of service
   - Logic errors

2. Best Practices:
   - Code organization and structure
   - Error handling
   - Gas optimization
   - Documentation and comments

3. Compliance:
   - Standard compliance (ERC20, ERC721, etc.)
   - Regulatory considerations

Please provide a detailed report with:
- Executive summary
- Detailed findings with severity levels
- Code locations and explanations
- Specific recommendations
- Risk assessment

Code to analyze:
```solidity
{code}
```
""",
        }

        base_prompt = profile_prompts.get(audit_profile, profile_prompts["general_v1"])
        return base_prompt.format(code=code)

    def _calculate_cost(self, usage: Dict[str, int]) -> float:
        """Calculate approximate cost based on usage."""
        # Rough cost estimates for common models (per 1M tokens)
        model_costs = {
            "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
            "openai/gpt-4": {"input": 30.0, "output": 60.0},
            "openai/gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        }

        costs = model_costs.get(self.model, {"input": 1.0, "output": 2.0})

        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        input_cost = (input_tokens / 1_000_000) * costs["input"]
        output_cost = (output_tokens / 1_000_000) * costs["output"]

        return input_cost + output_cost


# Global LLM client instance
llm_client = LLMClient()
