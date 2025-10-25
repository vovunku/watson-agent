# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8080
ENV DB_URL=sqlite:////app/state/agent.db
ENV DATA_DIR=/app/data
ENV WORKER_POOL_SIZE=4
ENV JOB_HARD_TIMEOUT_SEC=1200
ENV OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
ENV OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
ENV LOG_LEVEL=info
ENV DRY_RUN=true

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set work directory
WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/state /app/data && \
    chown -R appuser:appuser /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Change ownership to appuser
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/healthz || exit 1

# Run the application
CMD ["python", "app.py"]
