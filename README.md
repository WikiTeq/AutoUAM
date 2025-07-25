<img src="banner.jpeg" alt="AutoUAM Banner" width="100%">

# AutoUAM

Automated Cloudflare Under Attack Mode management based on server load metrics.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

AutoUAM is a modern, production-ready Python system for automatically managing Cloudflare's Under Attack Mode based on server load metrics. The system monitors your server's load average and automatically enables/disables Cloudflare's Under Attack Mode to protect against DDoS attacks and high-load situations.

## Features

- **Automated UAM Management**: Enable UAM when load exceeds threshold, disable when normalized
- **Configurable Thresholds**: User-defined upper and lower load limits
- **Time-based Controls**: Minimum UAM duration to prevent oscillation
- **Multiple Deployment Options**: Python package, systemd service, container, or cloud function
- **Infrastructure-as-Code Ready**: Terraform integration and cloud deployment support
- **Comprehensive Logging**: Structured logging with multiple output formats
- **Health Monitoring**: Built-in health checks and monitoring endpoints
- **Security**: Secure credential management and API token handling
- **Comprehensive Testing**: Unit, integration, and end-to-end tests with 65+ test cases

## Quick Start

### Installation

#### From PyPI (Recommended)

```bash
# Install the latest stable version
pip install autouam

# Or install with specific version
pip install autouam==1.0.0a1
```

#### From Source (Development)

```bash
# Install from source (recommended for development)
git clone https://github.com/your-org/AutoUAM.git
cd AutoUAM
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Or install development dependencies
pip install -e ".[dev]"
```

### Configuration

Create a configuration file:

```bash
autouam config generate --output config.yaml
```

Edit the configuration file with your Cloudflare credentials:

```yaml
cloudflare:
  api_token: "${CF_API_TOKEN}"
  zone_id: "${CF_ZONE_ID}"
  email: "contact@wikiteq.com"

monitoring:
  load_thresholds:
    upper: 2.0     # Enable UAM when normalized load > 2.0
    lower: 1.0     # Disable UAM when normalized load < 1.0
  check_interval: 5  # seconds
  minimum_uam_duration: 300  # seconds

  # Load thresholds use normalized values (load average ÷ CPU cores)
  # Example: On a 2-core system, normalized load 2.0 = actual load 4.0

security:
  regular_mode: "essentially_off"  # Normal security level

logging:
  level: "INFO"
  format: "json"
  output: "file"
  file_path: "/var/log/autouam.log"

health:
  enabled: true
  port: 8080
  endpoint: "/health"
  metrics_endpoint: "/metrics"
```

Set your environment variables:

```bash
export CF_API_TOKEN="your-cloudflare-api-token"
export CF_ZONE_ID="your-cloudflare-zone-id"
```

### Usage

#### Run in Foreground (Continuous Monitoring)

```bash
autouam daemon --config config.yaml
```

#### One-time Check

```bash
autouam check --config config.yaml
```

#### Manual Control

```bash
# Enable UAM manually
autouam enable --config config.yaml

# Disable UAM manually
autouam disable --config config.yaml
```

#### Status Check

```bash
autouam status --config config.yaml
```

#### Health Monitoring

```bash
# Perform health check
autouam health check --config config.yaml

# View metrics
autouam metrics show --config config.yaml
```

## Configuration

### Configuration Sources (Priority Order)

1. **Command-line arguments**
2. **Environment variables**
3. **Configuration file** (YAML/JSON/TOML)
4. **Default values**

### Environment Variables

All configuration values can be overridden with environment variables:

```bash
export AUTOUAM_CLOUDFLARE__API_TOKEN="your-token"
export AUTOUAM_CLOUDFLARE__ZONE_ID="your-zone"
export AUTOUAM_MONITORING__LOAD_THRESHOLDS__UPPER="2.0"
export AUTOUAM_MONITORING__LOAD_THRESHOLDS__LOWER="1.0"
export AUTOUAM_LOGGING__LEVEL="INFO"
```

### Configuration Schema

```yaml
cloudflare:
  api_token: string          # Required: Cloudflare API token
  zone_id: string           # Required: Cloudflare zone ID
  email: string             # Optional: Account email (for reference)

monitoring:
  load_thresholds:
    upper: float            # Enable UAM when load > this value
    lower: float            # Disable UAM when load < this value
  check_interval: int       # Check interval in seconds
  minimum_uam_duration: int # Minimum UAM duration in seconds

security:
  regular_mode: string      # Normal security level

logging:
  level: string             # DEBUG, INFO, WARNING, ERROR
  format: string            # json, text
  output: string            # file, stdout, syslog
  file_path: string         # Log file path
  max_size_mb: int          # Maximum log file size
  max_backups: int          # Maximum log backups

deployment:
  mode: string              # daemon, oneshot, lambda
  pid_file: string          # PID file path
  user: string              # User to run as
  group: string             # Group to run as

health:
  enabled: bool             # Enable health monitoring
  port: int                 # Health server port
  endpoint: string          # Health endpoint
  metrics_endpoint: string  # Metrics endpoint


```

## Deployment Options

### 1. Python Package Installation

```bash
pip install autouam
autouam daemon --config config.yaml
```

### 2. Systemd Service

Create a systemd service file:

```ini
[Unit]
Description=AutoUAM Service
After=network.target

[Service]
Type=simple
User=autouam
Group=autouam
ExecStart=/usr/local/bin/autouam daemon --config /etc/autouam/config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Docker Container

#### Using Docker Compose (Recommended)

```bash
# Set environment variables
export CF_API_TOKEN="your-cloudflare-api-token"
export CF_ZONE_ID="your-cloudflare-zone-id"
export CF_EMAIL="your-email@example.com"

# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f autouam

# Stop the service
docker-compose down
```

#### Using Docker directly

```bash
# Build the image
docker build -t autouam .

# Run the container
docker run -d \
  --name autouam \
  --restart unless-stopped \
  -e CF_API_TOKEN="your-cloudflare-api-token" \
  -e CF_ZONE_ID="your-cloudflare-zone-id" \
  -e CF_EMAIL="your-email@example.com" \
  -p 8080:8080 \
  -v autouam_logs:/var/log/autouam \
  autouam
```

The Docker container includes:
- Non-root user for security
- Health checks on port 8080
- Volume for persistent logs
- Environment variable configuration
- Automatic restart policy

### 4. Cloud Functions

AutoUAM can be deployed as a cloud function for serverless operation.

## Health Monitoring

AutoUAM provides comprehensive health monitoring:

### Health Endpoints

- `/health` - Comprehensive health check
- `/metrics` - Prometheus metrics
- `/ready` - Readiness probe
- `/live` - Liveness probe

### Metrics

AutoUAM exposes the following Prometheus metrics:

- `autouam_load_average` - Current system load average
- `autouam_uam_enabled` - UAM enabled status
- `autouam_uam_duration_seconds` - Current UAM duration
- `autouam_cloudflare_api_requests_total` - Total API requests
- `autouam_cloudflare_api_errors_total` - Total API errors
- `autouam_health_check_duration_seconds` - Health check duration



## Logging

AutoUAM uses structured logging with support for multiple formats:

### Log Formats

- **JSON**: Machine-readable structured logs
- **Text**: Human-readable formatted logs

### Log Outputs

- **File**: Rotating log files
- **stdout**: Standard output
- **syslog**: System logging

### Log Levels

- **DEBUG**: Detailed debugging information
- **INFO**: General operational messages
- **WARNING**: Warning messages
- **ERROR**: Error messages

## Security

### Credential Management

- Environment variables for secure credential injection
- File-based secrets with secure permissions
- No hardcoded credentials

### Security Best Practices

- Input validation with Pydantic models
- Secure configuration defaults
- Complete action audit trail
- Principle of least privilege for API tokens

## Development

### Setup Development Environment

```bash
git clone https://github.com/your-org/AutoUAM.git
cd AutoUAM
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=autouam --cov-report=term-missing --cov-report=html

# Run specific test file
pytest tests/test_monitor.py

# Run integration tests
pytest tests/test_integration.py --asyncio-mode=auto
```

**Current Test Status**: ✅ **65/65 tests passing** (100% success rate)
- **53 unit tests** - Configuration, monitoring, and core functionality
- **12 integration tests** - UAM management, health checks, state persistence

For comprehensive testing information, see [TESTING.md](TESTING.md).

### Code Quality

```bash
# Format code
black autouam/

# Sort imports
isort autouam/

# Lint code
flake8 autouam/

# Type checking
mypy autouam/
```

### Pre-commit Hooks

```bash
pre-commit install
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
