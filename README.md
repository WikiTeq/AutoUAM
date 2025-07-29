<img src="banner.jpeg" alt="AutoUAM Banner" width="100%">

# AutoUAM

Automated Cloudflare Under Attack Mode management based on server load metrics.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

AutoUAM is a vibe-coded Python system for automatically managing Cloudflare's Under Attack Mode based on server load metrics. The system monitors your server's load average and automatically enables/disables Cloudflare's Under Attack Mode to protect against DDoS attacks and high-load situations.

## Features

- **Automated UAM Management**: Enable UAM when load exceeds threshold, disable when normalized
- **Intelligent Load Monitoring**: Support for both absolute and relative load thresholds based on deviations from historical baseline
- **Configurable Thresholds**: User-defined upper and lower load limits with relative multipliers
- **Time-based Controls**: Minimum UAM duration to prevent oscillation
- **Multiple Deployment Options**: Python package, systemd service, container, or cloud function

## Quick Start

### Installation

#### From PyPI (Recommended)

```bash
# Install the latest stable version
pip install autouam
```

**Requirements:**
- Python 3.8+ with pip
- The `autouam` command will be installed to `~/.local/bin/` (user installation) or `/usr/local/bin/` (system installation)
- **Note:** If installed to `~/.local/bin/`, add it to your PATH: `export PATH=$PATH:~/.local/bin`

#### From Source (Development)

```bash
# Install from source (recommended for development)
git clone https://github.com/wikiteq/AutoUAM.git
cd AutoUAM
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Or install development dependencies
pip install -e ".[dev]"
```

**Requirements:**
- Python 3.8+ with venv support
- Git for cloning the repository
- Build tools (usually included with python3-dev)

**Important Notes:**
- The source version may be different from the PyPI version
- Always activate the virtual environment before using: `source venv/bin/activate`
- For production use, prefer the PyPI version for stability

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
    # Absolute thresholds (traditional approach)
    upper: 2.0     # Enable UAM when normalized load > 2.0
    lower: 1.0     # Disable UAM when normalized load < 1.0

    # Relative thresholds (recommended - learns your system's normal patterns)
    use_relative_thresholds: false  # Set to true to enable relative thresholds
    relative_upper_multiplier: 2.0  # Enable UAM when load > baseline * 2.0
    relative_lower_multiplier: 1.5  # Disable UAM when load < baseline * 1.5
    baseline_calculation_hours: 24  # Hours of historical data for baseline
    baseline_update_interval: 3600  # Seconds between baseline recalculations

  check_interval: 5  # seconds
  minimum_uam_duration: 300  # seconds

  # Load thresholds use normalized values (load average ÷ CPU cores)
  # Example: On a 2-core system, normalized load 2.0 = actual load 4.0
  #
  # Relative thresholds are recommended because they:
  # - Learn your system's normal load patterns over time
  # - Trigger based on deviations from baseline (e.g., 200% increase)
  # - Work across different server types and workloads
  # - Avoid false positives from normal load variations

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

**Configuration Validation:**
- AutoUAM validates that API tokens and zone IDs are present and at least 10 characters long
- Configuration errors will prevent the daemon from starting
- Use `autouam config validate` to check your configuration before starting
- Environment variables referenced in config files must be set before running AutoUAM

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

AutoUAM supports environment variables in two ways:

#### 1. Environment Variable Substitution in Config Files
You can reference environment variables in your config file using `${VAR_NAME}` syntax:

```yaml
cloudflare:
  api_token: "${CF_API_TOKEN}"
  zone_id: "${CF_ZONE_ID}"
```

Then set the environment variables:
```bash
export CF_API_TOKEN="your-cloudflare-api-token"
export CF_ZONE_ID="your-cloudflare-zone-id"
```

#### 2. Direct Environment Variable Override
All configuration values can be overridden with environment variables using the `AUTOUAM_` prefix:

```bash
export AUTOUAM_CLOUDFLARE__API_TOKEN="your-token"
export AUTOUAM_CLOUDFLARE__ZONE_ID="your-zone"
export AUTOUAM_MONITORING__LOAD_THRESHOLDS__UPPER="2.0"
export AUTOUAM_MONITORING__LOAD_THRESHOLDS__LOWER="1.0"
export AUTOUAM_LOGGING__LEVEL="INFO"
```

**Note**: Environment variable substitution in config files (method 1) is the recommended approach for sensitive values like API tokens.

### Configuration Validation

AutoUAM includes comprehensive configuration validation to prevent runtime errors:

#### Validation Features
- **Required Fields**: Validates all required configuration fields
- **Type Checking**: Ensures correct data types for all values
- **Range Validation**: Validates numeric values within acceptable ranges
- **Relative Threshold Validation**: Comprehensive validation for relative threshold configuration
- **File Permissions**: Checks file and directory permissions
- **Environment Variables**: Validates environment variable substitution

#### Relative Threshold Validation
When using relative thresholds, AutoUAM validates:
- **Multiplier Values**: Must be positive numbers
- **Multiplier Relationships**: Lower multiplier must be less than upper multiplier
- **Baseline Hours**: Must be between 1 and 168 hours (1 week)
- **Update Interval**: Must be at least 60 seconds
- **Interval Relationships**: Baseline update interval should be at least 10x the check interval

### Configuration Schema

```yaml
cloudflare:
  api_token: string          # Required: Cloudflare API token
  zone_id: string           # Required: Cloudflare zone ID
  email: string             # Optional: Account email (for reference)

monitoring:
  load_thresholds:
    # Absolute thresholds
    upper: float            # Enable UAM when load > this value
    lower: float            # Disable UAM when load < this value

    # Relative thresholds (recommended)
    use_relative_thresholds: bool    # Use relative thresholds based on baseline
    relative_upper_multiplier: float # Enable UAM when load > baseline * multiplier
    relative_lower_multiplier: float # Disable UAM when load < baseline * multiplier
    baseline_calculation_hours: int  # Hours of historical data for baseline
    baseline_update_interval: int    # Seconds between baseline recalculations

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

## Load Monitoring: Absolute vs Relative Thresholds

AutoUAM supports two approaches to load monitoring, each with different benefits:

### Absolute Thresholds (Traditional)

```yaml
monitoring:
  load_thresholds:
    upper: 2.0  # Enable UAM when normalized load > 2.0
    lower: 1.0  # Disable UAM when normalized load < 1.0
```

**Pros:**
- Simple to understand and configure
- Immediate protection without learning period
- Predictable behavior

**Cons:**
- Requires manual tuning for each system
- May trigger false positives on high-traffic servers
- May miss attacks on low-traffic servers
- No adaptation to changing workloads

### Relative Thresholds (Recommended)

```yaml
monitoring:
  load_thresholds:
    use_relative_thresholds: true
    relative_upper_multiplier: 2.0  # Enable UAM when load > baseline * 2.0
    relative_lower_multiplier: 1.5  # Disable UAM when load < baseline * 1.5
    baseline_calculation_hours: 24  # Learn from last 24 hours
    baseline_update_interval: 3600  # Update baseline every hour
```

**How it works:**
1. **Learning Phase**: Collects load samples over the specified time period
2. **Baseline Calculation**: Computes 95th percentile as "normal" load level
3. **Relative Comparison**: Triggers UAM when current load exceeds baseline by multiplier
4. **Continuous Adaptation**: Updates baseline periodically to adapt to workload changes

**Pros:**
- **Context-Aware**: Each system learns its own normal patterns
- **Adaptive**: Automatically adjusts to different server types and workloads
- **Robust**: Uses 95th percentile to handle occasional spikes
- **Intelligent**: Triggers based on significant deviations, not absolute values

**Example Scenarios:**

| Server Type | Normal Baseline | Attack Load | Ratio | Action |
|-------------|----------------|-------------|-------|---------|
| High-traffic web | 0.3 (30% CPU) | 1.2 (120% CPU) | 4x | ✅ Trigger UAM |
| Low-traffic app | 0.05 (5% CPU) | 0.4 (40% CPU) | 8x | ✅ Trigger UAM |
| Database server | 0.8 (80% CPU) | 1.6 (160% CPU) | 2x | ✅ Trigger UAM |

All scenarios trigger UAM despite having very different absolute load values, because they represent significant deviations from their respective baselines.

**When to use each approach:**

- **Use Relative Thresholds** for:
  - Production systems with variable workloads
  - Different server types (web, database, application)
  - Systems where you want automatic adaptation
  - Reducing false positives and false negatives

- **Use Absolute Thresholds** for:
  - Simple, predictable workloads
  - Systems with very specific load requirements
  - When you need immediate protection without learning period
  - Testing and development environments

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
Environment=CF_API_TOKEN=your-api-token
Environment=CF_ZONE_ID=your-zone-id

[Install]
WantedBy=multi-user.target
```

**Setup Steps:**
1. Install AutoUAM globally: `sudo pip3 install autouam`
2. Create service user: `sudo useradd -r -s /bin/false autouam`
3. Create config directory: `sudo mkdir -p /etc/autouam`
4. Copy config file: `sudo cp config.yaml /etc/autouam/`
5. Set permissions: `sudo chown -R autouam:autouam /etc/autouam`
6. Enable and start service: `sudo systemctl enable autouam && sudo systemctl start autouam`

### 3. Docker Container

#### Using Docker Compose (Recommended)

```bash
# Set environment variables
export CF_API_TOKEN="your-cloudflare-api-token"
export CF_ZONE_ID="your-cloudflare-zone-id"
export CF_EMAIL="your-email@example.com"

# Build and run with Docker Compose
docker compose up -d

# View logs
docker compose logs -f autouam

# Stop the service
docker compose down
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

**Important Notes:**
- The container uses the CMD directive, not ENTRYPOINT, so commands must be prefixed: `docker run autouam autouam --version`
- Container will exit if Cloudflare API connection fails during initialization
- Health checks use curl to test the /health endpoint

### 4. Cloud Functions

AutoUAM can be deployed as a cloud function for serverless operation.

## Health Monitoring

AutoUAM provides comprehensive health monitoring with built-in reliability features:

### Health Endpoints

- `/health` - Comprehensive health check
- `/metrics` - Prometheus metrics
- `/ready` - Readiness probe
- `/live` - Liveness probe

### Reliability Features

AutoUAM's health monitoring includes several reliability improvements:

#### Timeout Protection
- **API Timeouts**: 10-second timeout for Cloudflare API calls
- **Load Check Timeouts**: 5-second timeout for system load monitoring
- **Automatic Retries**: Failed checks are retried once with exponential backoff

#### Circuit Breaker Pattern
- **Failure Tracking**: Monitors consecutive API failures
- **Circuit Breaker**: Opens circuit after 3 consecutive failures
- **Automatic Recovery**: Circuit resets after 60 seconds
- **Graceful Degradation**: System remains operational during API outages

#### Graceful Degradation
- **Critical vs Non-Critical**: Distinguishes between critical and non-critical failures
- **Load Failures**: Critical (system may be overloaded)
- **API Failures**: Critical (required for UAM functionality)
- **State Failures**: Non-critical (state management issues)
- **Degraded Mode**: System reports healthy but degraded when non-critical components fail

### Metrics

AutoUAM exposes the following Prometheus metrics:

- `autouam_load_average` - Current system load average
- `autouam_uam_enabled` - UAM enabled status
- `autouam_uam_duration_seconds` - Current UAM duration
- `autouam_cloudflare_api_requests_total` - Total API requests
- `autouam_cloudflare_api_errors_total` - Total API errors
- `autouam_health_check_duration_seconds` - Health check duration

**Additional Baseline Metrics** (when relative thresholds enabled):
- `autouam_baseline_value` - Current load baseline value
- `autouam_baseline_ratio` - Current load ratio to baseline
- `autouam_baseline_samples_count` - Number of samples in baseline calculation
- `autouam_baseline_last_update` - Timestamp of last baseline update

## Logging

AutoUAM uses structured logging with support for multiple formats and improved reliability:

### Log Formats

- **JSON**: Machine-readable structured logs
- **Text**: Human-readable formatted logs

### Log Outputs

- **File**: Rotating log files with automatic cleanup
- **stdout**: Standard output for containerized deployments
- **syslog**: System logging for systemd services

### Log Levels

- **DEBUG**: Detailed debugging information
- **INFO**: General operational messages
- **WARNING**: Warning messages
- **ERROR**: Error messages

### Logging Features

#### Handler Management
- **Automatic Cleanup**: Removes existing handlers to prevent duplication
- **Proper Initialization**: Ensures clean logging setup on each initialization
- **Resource Management**: Proper cleanup of file handlers and streams

#### Formatter Consistency
- **Unified Formatting**: Consistent formatting across all output types
- **Structlog Integration**: Proper integration with structured logging
- **Context Preservation**: Maintains structured log context across handlers

#### Error Handling
- **Graceful Fallbacks**: Falls back to stdout if file logging fails
- **Permission Handling**: Handles permission errors gracefully
- **Directory Creation**: Automatically creates log directories when needed

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

### Set Up Development Environment

```bash
git clone https://github.com/wikiteq/AutoUAM.git
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

For comprehensive testing information, see [TESTING.md](TESTING.md).

**Dynamic Thresholds Testing**: For detailed testing documentation of the dynamic thresholds feature, see [DYNAMIC_THRESHOLDS_TESTING.md](DYNAMIC_THRESHOLDS_TESTING.md).

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

### Releasing to PyPI

**Important**: AutoUAM uses a specific twine version (3.8.0) to ensure compatibility with PyPI metadata validation.

#### Using the Release Script (Recommended)

```bash
# Make sure you're on the master branch and all changes are committed
git checkout master
git pull origin master

# Run the release script
./scripts/release.sh
```

#### Manual Release Process

```bash
# 1. Install the correct twine version
python -m pip install "twine==3.8.0"

# 2. Clean and build
rm -rf dist/ build/ *.egg-info/
python -m build

# 3. Check the package
twine check dist/*

# 4. Upload to PyPI
twine upload dist/* --skip-existing
```

**Note**: The pinned twine version (3.8.0) is included in the dev dependencies to ensure consistent releases.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
