# Audit Agent

A smart contract audit agent with LLM integration, built with FastAPI and designed to run in a single Docker container.

## Features

- **HTTP API**: RESTful API for creating and managing audit jobs
- **LLM Integration**: OpenRouter API integration with fallback to DRY_RUN mode
- **Job Scheduling**: Built-in scheduler with worker pool for parallel processing
- **Database**: SQLite with SQLAlchemy and Alembic migrations
- **Docker**: Single container deployment with health checks
- **Idempotency**: Support for idempotent job creation
- **Cancellation**: Job cancellation support
- **Progress Tracking**: Real-time job progress and metrics
- **Report Generation**: Detailed audit reports with file storage

## Quick Start

### Using Docker (Recommended)

1. **Build the image:**
   ```bash
   make build
   ```

2. **Run in DRY_RUN mode (no API key required):**
   ```bash
   make run-dry
   ```

3. **Run with OpenRouter API key:**
   ```bash
   OPENROUTER_API_KEY=your_key_here make run
   ```

4. **Run automated tests:**
   ```bash
   make test-integration
   ```

5. **Run all tests (unit + integration):**
   ```bash
   make test-full
   ```

6. **Try the demos:**
   ```bash
   make demo          # Quick start demo
   make demo-python   # Python client demo
   ```

### Using Development Mode

1. **Install dependencies:**
   ```bash
   make install
   ```

2. **Run development server:**
   ```bash
   make dev
   ```

## API Endpoints

### Create Job
**Endpoint:** `POST /jobs`

**Request:**
```bash
curl -X POST http://localhost:8081/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "source": {
      "type": "inline",
      "inline_code": "contract Test { function test() public {} }"
    },
    "llm": {
      "model": "anthropic/claude-3.5-sonnet",
      "max_tokens": 8000,
      "temperature": 0.1
    },
    "audit_profile": "erc20_basic_v1",
    "timeout_sec": 900,
    "idempotency_key": "unique-client-key",
    "client_meta": {
      "project": "my-project",
      "contact": "dev@example.com"
    }
  }'
```

**Response (201 Created):**
```json
{
  "job_id": "a6031a062d244f17",
  "status": "queued",
  "created_at": "2025-10-25T11:19:43.322444+00:00",
  "links": {
    "self": "/jobs/a6031a062d244f17",
    "report": "/jobs/a6031a062d244f17/report"
  }
}
```

### Get Job Status
**Endpoint:** `GET /jobs/{job_id}`

**Request:**
```bash
curl http://localhost:8081/jobs/a6031a062d244f17
```

**Response (200 OK) - Job Running:**
```json
{
  "job_id": "a6031a062d244f17",
  "status": "running",
  "progress": {
    "phase": "analysis",
    "percent": 50
  },
  "metrics": {
    "calls": 1,
    "prompt_tokens": 10,
    "completion_tokens": 166,
    "elapsed_sec": 5.433135675192472
  },
  "error_message": null,
  "links": {
    "self": "/jobs/a6031a062d244f17",
    "report": null
  }
}
```

**Response (200 OK) - Job Completed:**
```json
{
  "job_id": "a6031a062d244f17",
  "status": "succeeded",
  "progress": {
    "phase": "final",
    "percent": 100
  },
  "metrics": {
    "calls": 1,
    "prompt_tokens": 10,
    "completion_tokens": 166,
    "elapsed_sec": 5.433135675192472
  },
  "error_message": null,
  "links": {
    "self": "/jobs/a6031a062d244f17",
    "report": "/jobs/a6031a062d244f17/report"
  }
}
```

**Response (404 Not Found):**
```json
{
  "detail": "Job not found"
}
```

### Get Job Report
**Endpoint:** `GET /jobs/{job_id}/report`

**Request:**
```bash
curl http://localhost:8081/jobs/a6031a062d244f17/report
```

**Response (200 OK):**
```text
# Audit Report - Job a6031a062d244f17
Generated: 2024-01-01T00:00:00Z
Model: anthropic/claude-3.5-sonnet
Source: inline (None)
Profile: erc20_basic_v1
Content Hash: 4d7b57f1

## Summary
This is a synthetic audit report generated in DRY_RUN mode.
Found 1 potential issues in the analyzed code.

## Issues Found
### Issue 1
**Severity:** high
**Location:** contract.sol:42
**Description:** Potential reentrancy vulnerability in withdraw function
**Recommendation:** Use checks-effects-interactions pattern
**Explanation:** The function modifies state after external call, which could lead to reentrancy attacks.

## Checks Performed
- ERC20 compliance check
- Access control analysis
- Reentrancy detection
- Gas optimization review
- Integer overflow/underflow check

## Metrics
Analysis time: 13 seconds
Lines analyzed: 173
Functions reviewed: 18

Report SHA256: f206d3efe006d04fd55eb4fd606c89e8c62942845d3
```

**Response (409 Conflict) - Report Not Ready:**
```json
{
  "detail": "Report not ready. Job status: running"
}
```

**Response (404 Not Found):**
```json
{
  "detail": "Job not found"
}
```

### Cancel Job
**Endpoint:** `POST /jobs/{job_id}/cancel`

**Request:**
```bash
curl -X POST http://localhost:8081/jobs/a6031a062d244f17/cancel
```

**Response (200 OK):**
```json
{
  "job_id": "a6031a062d244f17",
  "status": "canceled",
  "canceled_at": "2025-10-25T11:20:15.123456+00:00"
}
```

**Response (400 Bad Request) - Job Already Finished:**
```json
{
  "detail": "Cannot cancel job with status: succeeded"
}
```

**Response (404 Not Found):**
```json
{
  "detail": "Job not found"
}
```

### Health Check
**Endpoint:** `GET /healthz`

**Request:**
```bash
curl http://localhost:8081/healthz
```

**Response (200 OK) - Healthy:**
```json
{
  "ok": true,
  "db": "ready",
  "version": "1.0.0"
}
```

**Response (200 OK) - Unhealthy:**
```json
{
  "ok": false,
  "db": "error",
  "version": "1.0.0"
}
```

## API Usage Examples

### Complete Workflow Example

Here's a complete example of using the audit agent API:

```bash
#!/bin/bash

# 1. Check service health
echo "Checking service health..."
curl -s http://localhost:8081/healthz | jq .

# 2. Create an audit job
echo "Creating audit job..."
JOB_RESPONSE=$(curl -s -X POST http://localhost:8081/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "source": {
      "type": "inline",
      "inline_code": "contract ERC20Token { mapping(address => uint256) balances; function transfer(address to, uint256 amount) public returns (bool) { balances[msg.sender] -= amount; balances[to] += amount; return true; } }"
    },
    "llm": {
      "model": "anthropic/claude-3.5-sonnet",
      "max_tokens": 8000,
      "temperature": 0.1
    },
    "audit_profile": "erc20_basic_v1",
    "timeout_sec": 900,
    "idempotency_key": "demo-workflow-123",
    "client_meta": {
      "project": "demo-project",
      "contact": "demo@example.com"
    }
  }')

echo "Job created:"
echo $JOB_RESPONSE | jq .

# Extract job ID
JOB_ID=$(echo $JOB_RESPONSE | jq -r '.job_id')

# 3. Monitor job progress
echo "Monitoring job progress..."
while true; do
  STATUS_RESPONSE=$(curl -s http://localhost:8081/jobs/$JOB_ID)
  STATUS=$(echo $STATUS_RESPONSE | jq -r '.status')
  PHASE=$(echo $STATUS_RESPONSE | jq -r '.progress.phase')
  PERCENT=$(echo $STATUS_RESPONSE | jq -r '.progress.percent')
  
  echo "Status: $STATUS, Phase: $PHASE, Progress: $PERCENT%"
  
  if [ "$STATUS" = "succeeded" ]; then
    echo "Job completed successfully!"
    break
  elif [ "$STATUS" = "failed" ] || [ "$STATUS" = "canceled" ] || [ "$STATUS" = "expired" ]; then
    echo "Job failed with status: $STATUS"
    exit 1
  fi
  
  sleep 2
done

# 4. Get the audit report
echo "Retrieving audit report..."
curl -s http://localhost:8081/jobs/$JOB_ID/report
```

### Python Client Example

```python
import requests
import time
import json

class AuditAgentClient:
    def __init__(self, base_url="http://localhost:8081"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def health_check(self):
        """Check service health."""
        response = self.session.get(f"{self.base_url}/healthz")
        return response.json()
    
    def create_job(self, source_code, audit_profile="erc20_basic_v1", **kwargs):
        """Create an audit job."""
        payload = {
            "source": {
                "type": "inline",
                "inline_code": source_code
            },
            "audit_profile": audit_profile,
            **kwargs
        }
        response = self.session.post(f"{self.base_url}/jobs", json=payload)
        return response.json()
    
    def get_job_status(self, job_id):
        """Get job status."""
        response = self.session.get(f"{self.base_url}/jobs/{job_id}")
        return response.json()
    
    def wait_for_completion(self, job_id, timeout=300):
        """Wait for job to complete."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.get_job_status(job_id)
            if status["status"] in ["succeeded", "failed", "canceled", "expired"]:
                return status
            time.sleep(2)
        raise TimeoutError("Job did not complete within timeout")
    
    def get_report(self, job_id):
        """Get audit report."""
        response = self.session.get(f"{self.base_url}/jobs/{job_id}/report")
        return response.text

# Usage example
if __name__ == "__main__":
    client = AuditAgentClient()
    
    # Check health
    health = client.health_check()
    print(f"Service health: {health}")
    
    # Create job
    source_code = """
    contract VulnerableContract {
        mapping(address => uint256) balances;
        
        function withdraw(uint256 amount) public {
            require(balances[msg.sender] >= amount);
            msg.sender.call{value: amount}("");
            balances[msg.sender] -= amount;  // Reentrancy vulnerability!
        }
    }
    """
    
    job = client.create_job(
        source_code=source_code,
        audit_profile="erc20_basic_v1",
        idempotency_key="python-demo-123"
    )
    
    job_id = job["job_id"]
    print(f"Created job: {job_id}")
    
    # Wait for completion
    final_status = client.wait_for_completion(job_id)
    print(f"Job completed with status: {final_status['status']}")
    
    # Get report
    if final_status["status"] == "succeeded":
        report = client.get_report(job_id)
        print("Audit Report:")
        print(report)
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

class AuditAgentClient {
    constructor(baseUrl = 'http://localhost:8081') {
        this.client = axios.create({
            baseURL: baseUrl,
            headers: { 'Content-Type': 'application/json' }
        });
    }
    
    async healthCheck() {
        const response = await this.client.get('/healthz');
        return response.data;
    }
    
    async createJob(sourceCode, auditProfile = 'erc20_basic_v1', options = {}) {
        const payload = {
            source: {
                type: 'inline',
                inline_code: sourceCode
            },
            audit_profile: auditProfile,
            ...options
        };
        const response = await this.client.post('/jobs', payload);
        return response.data;
    }
    
    async getJobStatus(jobId) {
        const response = await this.client.get(`/jobs/${jobId}`);
        return response.data;
    }
    
    async waitForCompletion(jobId, timeout = 300000) {
        const startTime = Date.now();
        while (Date.now() - startTime < timeout) {
            const status = await this.getJobStatus(jobId);
            if (['succeeded', 'failed', 'canceled', 'expired'].includes(status.status)) {
                return status;
            }
            await new Promise(resolve => setTimeout(resolve, 2000));
        }
        throw new Error('Job did not complete within timeout');
    }
    
    async getReport(jobId) {
        const response = await this.client.get(`/jobs/${jobId}/report`);
        return response.data;
    }
}

// Usage example
async function main() {
    const client = new AuditAgentClient();
    
    try {
        // Check health
        const health = await client.healthCheck();
        console.log('Service health:', health);
        
        // Create job
        const sourceCode = `
        contract ERC20Token {
            mapping(address => uint256) public balances;
            
            function transfer(address to, uint256 amount) public returns (bool) {
                require(balances[msg.sender] >= amount);
                balances[msg.sender] -= amount;
                balances[to] += amount;
                return true;
            }
        }
        `;
        
        const job = await client.createJob(
            sourceCode,
            'erc20_basic_v1',
            { idempotency_key: 'js-demo-123' }
        );
        
        console.log('Created job:', job.job_id);
        
        // Wait for completion
        const finalStatus = await client.waitForCompletion(job.job_id);
        console.log('Job completed with status:', finalStatus.status);
        
        // Get report
        if (finalStatus.status === 'succeeded') {
            const report = await client.getReport(job.job_id);
            console.log('Audit Report:');
            console.log(report);
        }
    } catch (error) {
        console.error('Error:', error.message);
    }
}

main();
```

### Error Handling Examples

#### Common Error Responses

**400 Bad Request - Invalid JSON:**
```json
{
  "detail": [
    {
      "type": "json_invalid",
      "loc": ["body"],
      "msg": "Invalid JSON",
      "input": null
    }
  ]
}
```

**422 Unprocessable Entity - Validation Error:**
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "source"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

**409 Conflict - Duplicate Idempotency Key:**
```json
{
  "detail": "Job with this idempotency key already exists",
  "existing_job_id": "a6031a062d244f17"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Internal server error"
}
```

#### Error Handling in Python

```python
import requests
from requests.exceptions import RequestException

def create_job_safely(client, source_code, **kwargs):
    """Create job with proper error handling."""
    try:
        response = client.create_job(source_code, **kwargs)
        return response
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 409:
            # Handle duplicate idempotency key
            error_data = e.response.json()
            existing_job_id = error_data.get('existing_job_id')
            print(f"Job already exists: {existing_job_id}")
            return {"job_id": existing_job_id, "status": "existing"}
        elif e.response.status_code == 422:
            # Handle validation errors
            error_data = e.response.json()
            print("Validation errors:")
            for error in error_data.get('detail', []):
                print(f"  - {error['loc']}: {error['msg']}")
        else:
            print(f"HTTP error {e.response.status_code}: {e.response.text}")
        raise
    except RequestException as e:
        print(f"Request failed: {e}")
        raise

# Usage with error handling
try:
    job = create_job_safely(
        client,
        "contract Test {}",
        idempotency_key="safe-demo-123"
    )
    print(f"Job created: {job['job_id']}")
except Exception as e:
    print(f"Failed to create job: {e}")
```

#### Error Handling in JavaScript

```javascript
async function createJobSafely(client, sourceCode, options = {}) {
    try {
        const job = await client.createJob(sourceCode, 'erc20_basic_v1', options);
        return job;
    } catch (error) {
        if (error.response) {
            const status = error.response.status;
            const data = error.response.data;
            
            switch (status) {
                case 409:
                    // Handle duplicate idempotency key
                    console.log(`Job already exists: ${data.existing_job_id}`);
                    return { job_id: data.existing_job_id, status: 'existing' };
                    
                case 422:
                    // Handle validation errors
                    console.log('Validation errors:');
                    data.detail.forEach(error => {
                        console.log(`  - ${error.loc.join('.')}: ${error.msg}`);
                    });
                    break;
                    
                default:
                    console.log(`HTTP error ${status}: ${JSON.stringify(data)}`);
            }
        } else {
            console.log(`Request failed: ${error.message}`);
        }
        throw error;
    }
}

// Usage with error handling
async function main() {
    try {
        const job = await createJobSafely(
            client,
            'contract Test {}',
            { idempotency_key: 'safe-demo-123' }
        );
        console.log(`Job created: ${job.job_id}`);
    } catch (error) {
        console.log(`Failed to create job: ${error.message}`);
    }
}
```

## Configuration

The application is configured through environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8080 | Server port |
| `DB_URL` | `sqlite:////app/state/agent.db` | Database URL |
| `DATA_DIR` | `/app/data` | Data directory for reports |
| `WORKER_POOL_SIZE` | 4 | Number of worker processes |
| `JOB_HARD_TIMEOUT_SEC` | 1200 | Job timeout in seconds |
| `OPENROUTER_API_KEY` | - | OpenRouter API key (optional) |
| `OPENROUTER_MODEL` | `anthropic/claude-3.5-sonnet` | LLM model |
| `LOG_LEVEL` | `info` | Log level |
| `DRY_RUN` | `true` | Enable DRY_RUN mode |

## Job Lifecycle

1. **queued** → Job created and waiting for worker
2. **running** → Job assigned to worker and processing
3. **succeeded** → Job completed successfully
4. **failed** → Job failed with error
5. **canceled** → Job was cancelled
6. **expired** → Job timed out

## Progress Phases

- **preflight** → Validation and setup
- **fetch** → Source code retrieval
- **analysis** → Code analysis
- **llm** → LLM processing
- **reporting** → Report generation
- **final** → Completion

## DRY_RUN Mode

When `OPENROUTER_API_KEY` is not provided, the application runs in DRY_RUN mode:
- Generates deterministic synthetic reports
- No external API calls
- Useful for testing and development
- Reports are based on input content hash

## Testing

The project includes comprehensive testing:

### Unit Tests
- Test individual components (utils, LLM client, database operations)
- Use pytest with SQLite in-memory database
- Mock external dependencies

### Integration Tests
- Test full API workflow
- Verify job lifecycle (creation → processing → completion)
- Test report generation and retrieval
- Verify idempotency and cancellation
- Automated end-to-end testing

### Test Coverage
- API endpoints
- Job processing pipeline
- Database operations
- LLM client functionality
- Error handling
- Edge cases

### Running Tests
```bash
# Unit tests only
make test

# Integration tests only (requires running service)
make test-integration

# All tests
make test-full
```

## Examples

The project includes several example scripts to help you get started:

### Quick Start Demo (Bash)
```bash
make demo
```
This runs a complete workflow demonstration showing:
- Health check
- Job creation
- Progress monitoring
- Report retrieval

### Python Client Demo
```bash
make demo-python
```
This demonstrates the Python client with:
- Simple contract audit
- Vulnerable contract audit
- Error handling
- Progress monitoring

### Manual Examples

**Basic curl example:**
```bash
# Create job
curl -X POST http://localhost:8081/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "source": {
      "type": "inline",
      "inline_code": "contract Test { function test() public {} }"
    },
    "audit_profile": "erc20_basic_v1",
    "idempotency_key": "manual-test-123"
  }'

# Check status
curl http://localhost:8081/jobs/{job_id}

# Get report
curl http://localhost:8081/jobs/{job_id}/report
```

**Python script example:**
```python
import requests
import time

# Create job
response = requests.post("http://localhost:8081/jobs", json={
    "source": {
        "type": "inline",
        "inline_code": "contract Test { function test() public {} }"
    },
    "audit_profile": "erc20_basic_v1",
    "idempotency_key": "python-test-123"
})

job_id = response.json()["job_id"]

# Wait for completion and get report
while True:
    status = requests.get(f"http://localhost:8081/jobs/{job_id}").json()
    if status["status"] == "succeeded":
        report = requests.get(f"http://localhost:8081/jobs/{job_id}/report").text
        print(report)
        break
    time.sleep(2)
```

## Development

### Running Tests

**Unit Tests:**
```bash
make test
```

**Integration Tests:**
```bash
make test-integration
```

**All Tests:**
```bash
make test-full
```

**Custom Integration Test URL:**
```bash
make test-integration-custom URL=http://your-server:8080
```

**Demos:**
```bash
make demo          # Quick start bash demo
make demo-python   # Python client demo
```

### Code Formatting
```bash
make fmt
```

### Linting
```bash
make lint
```

### Database Migrations
```bash
make db-migrate
```

## Docker Commands

```bash
# Build image
make build

# Run container
make run

# Run in DRY_RUN mode
make run-dry

# Stop container
make stop

# View logs
make logs

# Shell into container
make shell
```

## Project Structure

```
/app
├── app.py              # FastAPI application
├── scheduler.py        # Job scheduler
├── workers.py          # Worker processes
├── db.py              # Database operations
├── models.py          # SQLAlchemy models
├── schemas.py         # Pydantic schemas
├── llm_client.py      # LLM client
├── settings.py        # Configuration
├── utils.py           # Utilities
├── migrations/        # Alembic migrations
├── tests/             # Test suite
├── Dockerfile         # Docker configuration
├── Makefile           # Build automation
└── requirements.txt   # Python dependencies
```

## CI/CD and Automation

### GitHub Actions (Optional)
Create `.github/workflows/ci.yml`:
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: make install
      - name: Run unit tests
        run: make test
      - name: Build Docker image
        run: make build
      - name: Run integration tests
        run: |
          make run-dry &
          sleep 10
          make test-integration
          make stop
```

### Pre-commit Hooks
```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.0.270
    hooks:
      - id: ruff
        args: [--fix]
EOF

# Install hooks
pre-commit install
```

## Troubleshooting

### Common Issues

**Port already in use:**
```bash
# Check what's using port 8080/8081
lsof -i :8080
lsof -i :8081

# Kill process or use different port
make stop
```

**Database connection issues:**
```bash
# Check database file permissions
ls -la /app/state/agent.db

# Recreate database
make db-init
```

**Integration tests failing:**
```bash
# Ensure service is running
make run-dry

# Check service health
curl http://localhost:8081/healthz

# Run tests with verbose output
python test_integration.py --url http://localhost:8081
```

**Docker build issues:**
```bash
# Clean Docker cache
docker system prune -a

# Rebuild from scratch
make clean
make build
```

## License

MIT License
