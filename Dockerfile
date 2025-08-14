FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r autouam && useradd -r -g autouam autouam

# Create necessary directories
RUN mkdir -p /etc/autouam /var/log/autouam /var/run/autouam /var/lib/autouam

# Install AutoUAM
RUN pip install --no-cache-dir autouam

# Copy default configuration
COPY docker/config.yaml /etc/autouam/config.yaml

# Set ownership
RUN chown -R autouam:autouam /etc/autouam /var/log/autouam /var/run/autouam /var/lib/autouam

# Switch to non-root user
USER autouam

# Expose health check port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command
CMD ["autouam", "--config", "/etc/autouam/config.yaml", "daemon"]
