#!/usr/bin/env python3
"""
Python client example for Audit Agent API.
This script demonstrates how to use the audit agent from Python.
"""

import requests
import time
from typing import Dict, Any


class AuditAgentClient:
    """Simple client for the Audit Agent API."""

    def __init__(self, base_url: str = "http://localhost:8081"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        response = self.session.get(f"{self.base_url}/healthz")
        response.raise_for_status()
        return response.json()

    def create_job(
        self, source_code: str, audit_profile: str = "erc20_basic_v1", **kwargs
    ) -> Dict[str, Any]:
        """Create an audit job."""
        payload = {
            "source": {"type": "inline", "inline_code": source_code},
            "audit_profile": audit_profile,
            **kwargs,
        }
        response = self.session.post(f"{self.base_url}/jobs", json=payload)
        response.raise_for_status()
        return response.json()

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status."""
        response = self.session.get(f"{self.base_url}/jobs/{job_id}")
        response.raise_for_status()
        return response.json()

    def wait_for_completion(
        self, job_id: str, timeout: int = 300, poll_interval: int = 2
    ) -> Dict[str, Any]:
        """Wait for job to complete."""
        start_time = time.time()
        print(f"Waiting for job {job_id} to complete...")

        while time.time() - start_time < timeout:
            status = self.get_job_status(job_id)
            job_status = status["status"]
            progress = status.get("progress", {})
            phase = progress.get("phase", "unknown")
            percent = progress.get("percent", 0)

            print(
                f"\rStatus: {job_status:<10} | Phase: {phase:<12} | Progress: {percent:3d}%",
                end="",
                flush=True,
            )

            if job_status in ["succeeded", "failed", "canceled", "expired"]:
                print()  # New line
                return status

            time.sleep(poll_interval)

        print()  # New line
        raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")

    def get_report(self, job_id: str) -> str:
        """Get audit report."""
        response = self.session.get(f"{self.base_url}/jobs/{job_id}/report")
        response.raise_for_status()
        return response.text

    def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a job."""
        response = self.session.post(f"{self.base_url}/jobs/{job_id}/cancel")
        response.raise_for_status()
        return response.json()


def main():
    """Main function demonstrating the client usage."""
    print("🐍 Python Audit Agent Client Demo")
    print("=" * 40)

    # Initialize client
    client = AuditAgentClient()

    try:
        # Check health
        print("1. Checking service health...")
        health = client.health_check()
        if health.get("ok"):
            print("✅ Service is healthy")
        else:
            print("❌ Service is unhealthy")
            return
        print()

        # Example 1: Simple contract audit
        print("2. Auditing a simple ERC20 contract...")
        simple_contract = """
        contract SimpleToken {
            mapping(address => uint256) public balances;
            
            function transfer(address to, uint256 amount) public returns (bool) {
                require(balances[msg.sender] >= amount);
                balances[msg.sender] -= amount;
                balances[to] += amount;
                return true;
            }
        }
        """

        job = client.create_job(
            source_code=simple_contract,
            audit_profile="erc20_basic_v1",
            idempotency_key=f"python-demo-simple-{int(time.time())}",
        )

        job_id = job["job_id"]
        print(f"Created job: {job_id}")

        # Wait for completion
        final_status = client.wait_for_completion(job_id)
        print(f"Job completed with status: {final_status['status']}")

        if final_status["status"] == "succeeded":
            print("\n3. Retrieving audit report...")
            report = client.get_report(job_id)
            print("=" * 50)
            print(report)
            print("=" * 50)

        print()

        # Example 2: Vulnerable contract audit
        print("4. Auditing a vulnerable contract...")
        vulnerable_contract = """
        contract VulnerableBank {
            mapping(address => uint256) balances;
            
            function deposit() public payable {
                balances[msg.sender] += msg.value;
            }
            
            function withdraw(uint256 amount) public {
                require(balances[msg.sender] >= amount);
                msg.sender.call{value: amount}("");  // Reentrancy vulnerability!
                balances[msg.sender] -= amount;
            }
        }
        """

        job2 = client.create_job(
            source_code=vulnerable_contract,
            audit_profile="erc20_basic_v1",
            idempotency_key=f"python-demo-vulnerable-{int(time.time())}",
        )

        job_id2 = job2["job_id"]
        print(f"Created job: {job_id2}")

        # Wait for completion
        final_status2 = client.wait_for_completion(job_id2)
        print(f"Job completed with status: {final_status2['status']}")

        if final_status2["status"] == "succeeded":
            print("\n5. Retrieving audit report...")
            report2 = client.get_report(job_id2)
            print("=" * 50)
            print(report2)
            print("=" * 50)

        print()
        print("🎉 Demo completed successfully!")
        print("\nNext steps:")
        print("- Try different contract code")
        print("- Experiment with different audit profiles")
        print("- Check the full API documentation in README.md")

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
