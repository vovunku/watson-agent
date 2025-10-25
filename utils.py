"""Utility functions for the audit agent."""

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def get_current_timestamp() -> str:
    """Get current UTC timestamp in ISO8601 format."""
    return datetime.now(timezone.utc).isoformat()


def generate_job_id(payload: Dict[str, Any], idempotency_key: Optional[str] = None) -> str:
    """Generate deterministic job ID from payload and idempotency key."""
    if idempotency_key:
        return hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]
    
    # Generate from payload content
    content = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def ensure_directory(path: str) -> None:
    """Ensure directory exists, create if not."""
    Path(path).mkdir(parents=True, exist_ok=True)


def write_report_file(job_id: str, content: str, data_dir: str) -> str:
    """Write report content to file and return the path."""
    try:
        ensure_directory(data_dir)
        report_dir = os.path.join(data_dir, job_id)
        ensure_directory(report_dir)
        
        report_path = os.path.join(report_dir, "report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return report_path
    except Exception as e:
        # Fallback to temp directory if data_dir fails
        import tempfile
        temp_dir = tempfile.mkdtemp()
        report_path = os.path.join(temp_dir, f"{job_id}_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)
        return report_path


def read_report_file(report_path: str) -> str:
    """Read report content from file."""
    with open(report_path, "r", encoding="utf-8") as f:
        return f.read()


def calculate_elapsed_seconds(start_time: str, end_time: Optional[str] = None) -> float:
    """Calculate elapsed seconds between timestamps."""
    start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_time.replace("Z", "+00:00")) if end_time else datetime.now(timezone.utc)
    return (end - start).total_seconds()


def generate_deterministic_report(payload: Dict[str, Any], job_id: str) -> str:
    """Generate deterministic report for DRY_RUN mode."""
    content_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:8]
    
    # Extract source info
    source = payload.get("source", {})
    source_type = source.get("type", "unknown")
    source_url = source.get("url", "N/A")
    
    # Extract LLM info
    llm = payload.get("llm", {})
    model = llm.get("model", "unknown")
    
    # Extract audit profile
    audit_profile = payload.get("audit_profile", "unknown")
    
    # Generate deterministic issues based on content hash
    issues = []
    hash_int = int(content_hash, 16)
    
    if hash_int % 3 == 0:
        issues.append({
            "severity": "high",
            "location": "contract.sol:42",
            "description": "Potential reentrancy vulnerability in withdraw function",
            "recommendation": "Use checks-effects-interactions pattern",
            "explanation": "The function modifies state after external call, which could lead to reentrancy attacks."
        })
    
    if hash_int % 5 == 0:
        issues.append({
            "severity": "medium",
            "location": "contract.sol:15",
            "description": "Missing access control modifier",
            "recommendation": "Add onlyOwner or similar access control",
            "explanation": "Function lacks proper access control, allowing unauthorized execution."
        })
    
    if hash_int % 7 == 0:
        issues.append({
            "severity": "low",
            "location": "contract.sol:89",
            "description": "Unused variable declaration",
            "recommendation": "Remove unused variable or use it",
            "explanation": "Variable is declared but never used, increasing gas costs."
        })
    
    # Use fixed timestamp for deterministic reports
    fixed_timestamp = "2024-01-01T00:00:00Z"
    
    # Generate report content
    report_lines = [
        f"# Audit Report - Job {job_id}",
        f"Generated: {fixed_timestamp}",
        f"Model: {model}",
        f"Source: {source_type} ({source_url})",
        f"Profile: {audit_profile}",
        f"Content Hash: {content_hash}",
        "",
        "## Summary",
        f"This is a synthetic audit report generated in DRY_RUN mode.",
        f"Found {len(issues)} potential issues in the analyzed code.",
        "",
        "## Issues Found",
    ]
    
    if not issues:
        report_lines.append("No issues detected in the analyzed code.")
    else:
        for i, issue in enumerate(issues, 1):
            report_lines.extend([
                f"### Issue {i}",
                f"**Severity:** {issue['severity']}",
                f"**Location:** {issue['location']}",
                f"**Description:** {issue['description']}",
                f"**Recommendation:** {issue['recommendation']}",
                f"**Explanation:** {issue['explanation']}",
                ""
            ])
    
    report_lines.extend([
        "## Checks Performed",
        "- ERC20 compliance check",
        "- Access control analysis",
        "- Reentrancy detection",
        "- Gas optimization review",
        "- Integer overflow/underflow check",
        "",
        "## Metrics",
        f"Analysis time: {hash_int % 30 + 10} seconds",
        f"Lines analyzed: {hash_int % 1000 + 100}",
        f"Functions reviewed: {hash_int % 20 + 5}",
        ""
    ])
    
    # Calculate SHA256 hash
    report_content = "\n".join(report_lines)
    report_hash = hashlib.sha256(report_content.encode()).hexdigest()
    report_lines.append(f"Report SHA256: {report_hash}")
    
    return "\n".join(report_lines)


def sleep_with_cancel_check(cancel_flag: bool, duration: float = 1.0) -> bool:
    """Sleep for duration while checking cancel flag every 0.1 seconds."""
    start_time = time.time()
    while time.time() - start_time < duration:
        if cancel_flag:
            return True
        time.sleep(0.1)
    return False
