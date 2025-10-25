#!/usr/bin/env python3
"""
Integration tests for audit agent.
Automated tests that verify the full functionality of the audit agent.
"""

import time
import requests
import sys
from typing import Optional


class AuditAgentTester:
    """Integration tester for audit agent."""

    def __init__(self, base_url: str = "http://localhost:8081"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def test_health_check(self) -> bool:
        """Test health check endpoint."""
        print("🔍 Testing health check...")
        try:
            response = self.session.get(f"{self.base_url}/healthz")
            if response.status_code == 200:
                data = response.json()
                if data.get("ok") and data.get("db") == "ready":
                    print("✅ Health check passed")
                    return True
                else:
                    print(f"❌ Health check failed: {data}")
                    return False
            else:
                print(f"❌ Health check failed with status {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check failed with error: {e}")
            return False

    def test_job_creation(self) -> Optional[str]:
        """Test job creation and return job_id."""
        print("🔍 Testing job creation...")
        try:
            import time

            # Use timestamp to ensure unique idempotency key
            timestamp = str(int(time.time() * 1000))
            payload = {
                "source": {
                    "type": "inline",
                    "inline_code": "contract Test { function test() public {} }",
                },
                "audit_profile": "erc20_basic_v1",
                "idempotency_key": f"integration-test-{timestamp}",
            }

            response = self.session.post(f"{self.base_url}/jobs", json=payload)
            if response.status_code == 201:
                data = response.json()
                job_id = data.get("job_id")
                if job_id and data.get("status") in ["queued", "succeeded"]:
                    print(
                        f"✅ Job created successfully: {job_id} (status: {data.get('status')})"
                    )
                    return job_id
                else:
                    print(f"❌ Job creation failed: {data}")
                    return None
            else:
                print(
                    f"❌ Job creation failed with status {response.status_code}: {response.text}"
                )
                return None
        except Exception as e:
            print(f"❌ Job creation failed with error: {e}")
            return None

    def test_job_status(self, job_id: str) -> bool:
        """Test job status endpoint."""
        print(f"🔍 Testing job status for {job_id}...")
        try:
            response = self.session.get(f"{self.base_url}/jobs/{job_id}")
            if response.status_code == 200:
                data = response.json()
                if data.get("job_id") == job_id and "status" in data:
                    print(f"✅ Job status retrieved: {data['status']}")
                    return True
                else:
                    print(f"❌ Job status failed: {data}")
                    return False
            else:
                print(f"❌ Job status failed with status {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Job status failed with error: {e}")
            return False

    def wait_for_job_completion(self, job_id: str, timeout: int = 60) -> bool:
        """Wait for job to complete and return success status."""
        print(f"⏳ Waiting for job {job_id} to complete...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.session.get(f"{self.base_url}/jobs/{job_id}")
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")

                    if status == "succeeded":
                        print(f"✅ Job {job_id} completed successfully")
                        return True
                    elif status in ["failed", "canceled", "expired"]:
                        print(f"❌ Job {job_id} failed with status: {status}")
                        return False
                    else:
                        # Still running, check progress
                        progress = data.get("progress", {})
                        phase = progress.get("phase", "unknown")
                        percent = progress.get("percent", 0)
                        print(f"⏳ Job {job_id} running: {phase} ({percent}%)")
                        time.sleep(2)
                else:
                    print(f"❌ Failed to check job status: {response.status_code}")
                    return False
            except Exception as e:
                print(f"❌ Error checking job status: {e}")
                return False

        print(f"❌ Job {job_id} timed out after {timeout} seconds")
        return False

    def test_job_report(self, job_id: str) -> bool:
        """Test job report endpoint."""
        print(f"🔍 Testing job report for {job_id}...")
        try:
            response = self.session.get(f"{self.base_url}/jobs/{job_id}/report")
            if response.status_code == 200:
                content = response.text
                if (
                    content
                    and ("audit" in content.lower() or "analysis" in content.lower())
                    and len(content) > 100
                ):
                    print(
                        f"✅ Job report retrieved successfully ({len(content)} characters)"
                    )
                    return True
                else:
                    print("❌ Job report content invalid")
                    return False
            else:
                print(f"❌ Job report failed with status {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Job report failed with error: {e}")
            return False

    def test_idempotency(self) -> bool:
        """Test job creation idempotency."""
        print("🔍 Testing idempotency...")
        try:
            import time

            # Use timestamp to ensure unique idempotency key for this test
            timestamp = str(int(time.time() * 1000))
            payload = {
                "source": {
                    "type": "inline",
                    "inline_code": "contract Test { function test() public {} }",
                },
                "audit_profile": "erc20_basic_v1",
                "idempotency_key": f"idempotency-test-{timestamp}",
            }

            # Create first job
            response1 = self.session.post(f"{self.base_url}/jobs", json=payload)
            if response1.status_code != 201:
                print(f"❌ First job creation failed: {response1.status_code}")
                return False

            job_id1 = response1.json().get("job_id")

            # Create second job with same idempotency key
            response2 = self.session.post(f"{self.base_url}/jobs", json=payload)
            if response2.status_code != 201:
                print(f"❌ Second job creation failed: {response2.status_code}")
                return False

            job_id2 = response2.json().get("job_id")

            if job_id1 == job_id2:
                print("✅ Idempotency test passed")
                return True
            else:
                print(f"❌ Idempotency test failed: {job_id1} != {job_id2}")
                return False
        except Exception as e:
            print(f"❌ Idempotency test failed with error: {e}")
            return False

    def test_job_cancellation(self) -> bool:
        """Test job cancellation."""
        print("🔍 Testing job cancellation...")
        try:
            import time

            # Use timestamp to ensure unique idempotency key
            timestamp = str(int(time.time() * 1000))
            # Create a job
            payload = {
                "source": {
                    "type": "inline",
                    "inline_code": "contract Test { function test() public {} }",
                },
                "audit_profile": "erc20_basic_v1",
                "idempotency_key": f"cancel-test-{timestamp}",
            }

            response = self.session.post(f"{self.base_url}/jobs", json=payload)
            if response.status_code != 201:
                print(
                    f"❌ Job creation for cancellation test failed: {response.status_code}"
                )
                return False

            job_id = response.json().get("job_id")

            # Cancel the job immediately
            cancel_response = self.session.post(f"{self.base_url}/jobs/{job_id}/cancel")
            if cancel_response.status_code == 200:
                data = cancel_response.json()
                if data.get("status") == "canceled":
                    print("✅ Job cancellation test passed")
                    return True
                else:
                    print(f"❌ Job cancellation failed: {data}")
                    return False
            else:
                print(
                    f"❌ Job cancellation failed with status {cancel_response.status_code}: {cancel_response.text}"
                )
                return False
        except Exception as e:
            print(f"❌ Job cancellation test failed with error: {e}")
            return False

    def run_all_tests(self) -> bool:
        """Run all integration tests."""
        print("🚀 Starting integration tests for audit agent...")
        print("=" * 60)

        tests_passed = 0
        total_tests = 6

        # Test 1: Health check
        if self.test_health_check():
            tests_passed += 1
        print()

        # Test 2: Job creation
        job_id = self.test_job_creation()
        if job_id:
            tests_passed += 1
        print()

        # Test 3: Job status
        if job_id and self.test_job_status(job_id):
            tests_passed += 1
        print()

        # Test 4: Wait for completion and test report
        if job_id and self.wait_for_job_completion(job_id):
            if self.test_job_report(job_id):
                tests_passed += 1
        print()

        # Test 5: Idempotency
        if self.test_idempotency():
            tests_passed += 1
        print()

        # Test 6: Job cancellation
        if self.test_job_cancellation():
            tests_passed += 1
        print()

        # Results
        print("=" * 60)
        print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")

        if tests_passed == total_tests:
            print("🎉 All tests passed! Audit agent is working correctly.")
            return True
        else:
            print("❌ Some tests failed. Please check the output above.")
            return False


def main():
    """Main function to run integration tests."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run integration tests for audit agent"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8081",
        help="Base URL for the audit agent API",
    )
    parser.add_argument(
        "--timeout", type=int, default=60, help="Timeout for job completion in seconds"
    )

    args = parser.parse_args()

    tester = AuditAgentTester(args.url)
    success = tester.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
