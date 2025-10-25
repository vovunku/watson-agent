#!/bin/bash

# Quick Start Script for Audit Agent
# This script demonstrates the basic usage of the audit agent API

set -e

BASE_URL="http://localhost:8081"

echo "🚀 Audit Agent Quick Start Demo"
echo "================================"

# Check if service is running
echo "1. Checking service health..."
if ! curl -s -f "$BASE_URL/healthz" > /dev/null; then
    echo "❌ Service is not running. Please start it first:"
    echo "   make run-dry"
    exit 1
fi

HEALTH=$(curl -s "$BASE_URL/healthz" | jq -r '.ok')
if [ "$HEALTH" = "true" ]; then
    echo "✅ Service is healthy"
else
    echo "❌ Service is unhealthy"
    exit 1
fi

echo ""

# Create a sample audit job
echo "2. Creating audit job..."
TIMESTAMP=$(date +%s)

# Create a temporary JSON file to avoid shell escaping issues
cat > /tmp/audit_job.json << EOF
{
  "source": {
    "type": "inline",
    "inline_code": "contract VulnerableToken { mapping(address => uint256) balances; function withdraw(uint256 amount) public { require(balances[msg.sender] >= amount); msg.sender.call{value: amount}(\"\"); balances[msg.sender] -= amount; } }"
  },
  "llm": {
    "model": "anthropic/claude-3.5-sonnet",
    "max_tokens": 8000,
    "temperature": 0.1
  },
  "audit_profile": "erc20_basic_v1",
  "timeout_sec": 900,
  "idempotency_key": "quick-start-$TIMESTAMP",
  "client_meta": {
    "project": "quick-start-demo",
    "contact": "demo@example.com"
  }
}
EOF

JOB_RESPONSE=$(curl -s -X POST "$BASE_URL/jobs" \
  -H "Content-Type: application/json" \
  -d @/tmp/audit_job.json)

echo "Job created:"
echo "$JOB_RESPONSE" | jq .

JOB_ID=$(echo "$JOB_RESPONSE" | jq -r '.job_id')
echo ""

# Monitor job progress
echo "3. Monitoring job progress..."
echo "Job ID: $JOB_ID"
echo ""

while true; do
    STATUS_RESPONSE=$(curl -s "$BASE_URL/jobs/$JOB_ID")
    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
    PHASE=$(echo "$STATUS_RESPONSE" | jq -r '.progress.phase // "unknown"')
    PERCENT=$(echo "$STATUS_RESPONSE" | jq -r '.progress.percent // 0')
    
    printf "\rStatus: %-10s | Phase: %-12s | Progress: %3d%%" "$STATUS" "$PHASE" "$PERCENT"
    
    if [ "$STATUS" = "succeeded" ]; then
        echo ""
        echo "✅ Job completed successfully!"
        break
    elif [ "$STATUS" = "failed" ] || [ "$STATUS" = "canceled" ] || [ "$STATUS" = "expired" ]; then
        echo ""
        echo "❌ Job failed with status: $STATUS"
        ERROR_MSG=$(echo "$STATUS_RESPONSE" | jq -r '.error_message // "No error message"')
        echo "Error: $ERROR_MSG"
        exit 1
    fi
    
    sleep 2
done

echo ""

# Get the audit report
echo "4. Retrieving audit report..."
echo "================================"
curl -s "$BASE_URL/jobs/$JOB_ID/report"
echo ""
echo "================================"

echo ""
echo "🎉 Demo completed successfully!"
echo ""
echo "Next steps:"
echo "- Try different contract code in the source field"
echo "- Experiment with different audit profiles"
echo "- Check the API documentation in README.md"
echo "- Run 'make test-integration' for comprehensive testing"

# Cleanup
rm -f /tmp/audit_job.json
