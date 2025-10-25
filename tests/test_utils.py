"""Test utility functions."""

import pytest
from utils import (
    get_current_timestamp,
    generate_job_id,
    ensure_directory,
    write_report_file,
    read_report_file,
    calculate_elapsed_seconds,
    generate_deterministic_report,
)


class TestTimestampUtils:
    """Test timestamp utility functions."""

    def test_get_current_timestamp(self):
        """Test timestamp generation."""
        timestamp = get_current_timestamp()

        # Should be a string
        assert isinstance(timestamp, str)

        # Should contain ISO format indicators
        assert "T" in timestamp
        assert "Z" in timestamp or "+" in timestamp

    def test_calculate_elapsed_seconds(self):
        """Test elapsed time calculation."""
        start_time = "2024-01-01T00:00:00Z"
        end_time = "2024-01-01T00:01:30Z"

        elapsed = calculate_elapsed_seconds(start_time, end_time)
        assert elapsed == 90.0  # 1 minute 30 seconds

    def test_calculate_elapsed_seconds_no_end_time(self):
        """Test elapsed time calculation without end time."""
        start_time = "2024-01-01T00:00:00Z"

        elapsed = calculate_elapsed_seconds(start_time)
        assert elapsed >= 0  # Should be non-negative


class TestJobIdGeneration:
    """Test job ID generation."""

    def test_generate_job_id_with_idempotency_key(self):
        """Test job ID generation with idempotency key."""
        payload = {"source": {"type": "inline"}}
        idempotency_key = "test-key-123"

        job_id = generate_job_id(payload, idempotency_key)

        # Should be deterministic
        job_id2 = generate_job_id(payload, idempotency_key)
        assert job_id == job_id2

        # Should be different for different keys
        job_id3 = generate_job_id(payload, "different-key")
        assert job_id != job_id3

    def test_generate_job_id_without_idempotency_key(self):
        """Test job ID generation without idempotency key."""
        payload = {"source": {"type": "inline", "inline_code": "contract Test {}"}}

        job_id = generate_job_id(payload)

        # Should be deterministic based on payload
        job_id2 = generate_job_id(payload)
        assert job_id == job_id2

        # Should be different for different payloads
        payload2 = {"source": {"type": "inline", "inline_code": "contract Test2 {}"}}
        job_id3 = generate_job_id(payload2)
        assert job_id != job_id3


class TestFileOperations:
    """Test file operation utilities."""

    def test_ensure_directory(self, tmp_path):
        """Test directory creation."""
        test_dir = tmp_path / "test_dir"

        ensure_directory(str(test_dir))
        assert test_dir.exists()
        assert test_dir.is_dir()

        # Should not raise error if directory already exists
        ensure_directory(str(test_dir))
        assert test_dir.exists()

    def test_write_and_read_report_file(self, tmp_path):
        """Test report file writing and reading."""
        job_id = "test-job-123"
        content = "Test audit report content\nWith multiple lines"

        # Write report
        report_path = write_report_file(job_id, content, str(tmp_path))

        # Check file was created
        assert report_path.endswith("report.txt")
        assert "test-job-123" in report_path

        # Read report
        read_content = read_report_file(report_path)
        assert read_content == content

    def test_read_report_file_not_found(self):
        """Test reading non-existent report file."""
        with pytest.raises(FileNotFoundError):
            read_report_file("/non/existent/path/report.txt")


class TestDeterministicReport:
    """Test deterministic report generation."""

    def test_generate_deterministic_report(self):
        """Test deterministic report generation."""
        payload = {
            "source": {
                "type": "inline",
                "inline_code": "contract Test { function test() public {} }",
            },
            "llm": {"model": "anthropic/claude-3.5-sonnet"},
            "audit_profile": "erc20_basic_v1",
        }
        job_id = "test-job-456"

        report = generate_deterministic_report(payload, job_id)

        # Should be a string
        assert isinstance(report, str)

        # Should contain expected sections
        assert "# Audit Report" in report
        assert job_id in report
        assert "DRY_RUN mode" in report
        assert "## Summary" in report
        assert "## Issues Found" in report
        assert "## Checks Performed" in report
        assert "## Metrics" in report
        assert "Report SHA256:" in report

        # Should be deterministic
        report2 = generate_deterministic_report(payload, job_id)
        assert report == report2

    def test_generate_deterministic_report_different_payloads(self):
        """Test that different payloads generate different reports."""
        payload1 = {
            "source": {"type": "inline", "inline_code": "contract Test1 {}"},
            "audit_profile": "erc20_basic_v1",
        }
        payload2 = {
            "source": {"type": "inline", "inline_code": "contract Test2 {}"},
            "audit_profile": "general_v1",
        }

        report1 = generate_deterministic_report(payload1, "job-1")
        report2 = generate_deterministic_report(payload2, "job-2")

        # Should be different
        assert report1 != report2

    def test_generate_deterministic_report_contains_issues(self):
        """Test that deterministic report can contain issues."""
        # Use a payload that will generate issues based on hash
        payload = {
            "source": {"type": "inline", "inline_code": "contract Test {}"},
            "audit_profile": "erc20_basic_v1",
        }
        job_id = "test-job-issues"

        report = generate_deterministic_report(payload, job_id)

        # Check if report contains issues (depends on hash)
        if "### Issue" in report:
            assert "**Severity:**" in report
            assert "**Location:**" in report
            assert "**Description:**" in report
            assert "**Recommendation:**" in report
            assert "**Explanation:**" in report
