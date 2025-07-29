"""Configuration validation utilities."""

import os
from pathlib import Path
from typing import Any, Dict, List

from .settings import Settings


def validate_config(config: Settings) -> List[str]:
    """Validate configuration and return list of errors."""
    errors = []

    # Validate Cloudflare configuration
    if not config.cloudflare.api_token:
        errors.append("Cloudflare API token is required")

    if not config.cloudflare.zone_id:
        errors.append("Cloudflare zone ID is required")

    # Validate monitoring configuration
    if (
        config.monitoring.load_thresholds.lower
        >= config.monitoring.load_thresholds.upper
    ):
        errors.append("Lower load threshold must be less than upper threshold")

    if config.monitoring.check_interval < 1:
        errors.append("Check interval must be at least 1 second")

    if config.monitoring.minimum_uam_duration < 60:
        errors.append("Minimum UAM duration must be at least 60 seconds")

    # Validate relative threshold configuration
    thresholds = config.monitoring.load_thresholds
    if thresholds.use_relative_thresholds:
        if thresholds.relative_upper_multiplier <= 0:
            errors.append("Relative upper multiplier must be positive")

        if thresholds.relative_lower_multiplier <= 0:
            errors.append("Relative lower multiplier must be positive")

        if thresholds.relative_lower_multiplier >= thresholds.relative_upper_multiplier:
            errors.append(
                "Relative lower multiplier must be less than upper multiplier"
            )

        if (
            thresholds.baseline_calculation_hours < 1
            or thresholds.baseline_calculation_hours > 168
        ):
            errors.append("Baseline calculation hours must be between 1 and 168")

        if thresholds.baseline_update_interval < 60:
            errors.append("Baseline update interval must be at least 60 seconds")

        # Ensure baseline update interval is reasonable compared to check interval
        if thresholds.baseline_update_interval < config.monitoring.check_interval * 10:
            errors.append(
                "Baseline update interval should be at least 10x the check interval"
            )

    # Validate logging configuration
    if config.logging.output == "file" and not config.logging.file_path:
        errors.append("Log file path is required when output is 'file'")

    if config.logging.output == "file" and config.logging.file_path:
        log_dir = Path(config.logging.file_path).parent
        if not log_dir.exists():
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                errors.append(f"Cannot create log directory: {log_dir}")

    # Validate deployment configuration
    if config.deployment.mode == "daemon" and not config.deployment.pid_file:
        errors.append("PID file path is required for daemon mode")

    if config.deployment.pid_file:
        pid_dir = Path(config.deployment.pid_file).parent
        if not pid_dir.exists():
            try:
                pid_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                errors.append(f"Cannot create PID directory: {pid_dir}")

    # Validate health configuration
    if config.health.enabled and (config.health.port < 1 or config.health.port > 65535):
        errors.append("Health port must be between 1 and 65535")

    return errors


def validate_config_file(config_path: Path) -> List[str]:
    """Validate configuration file and return list of errors."""
    errors = []

    if not config_path.exists():
        errors.append(f"Configuration file not found: {config_path}")
        return errors

    try:
        config = Settings.from_file(config_path)
        errors.extend(validate_config(config))
    except Exception as e:
        errors.append(f"Failed to load configuration: {e}")

    return errors


def check_environment_variables() -> List[str]:
    """Check for required environment variables and return list of missing ones."""
    required_vars = [
        "AUTOUAM_CLOUDFLARE__API_TOKEN",
        "AUTOUAM_CLOUDFLARE__ZONE_ID",
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    return missing_vars


def generate_sample_config() -> Dict[str, Any]:
    """Generate a sample configuration."""
    return {
        "cloudflare": {
            "api_token": "${CF_API_TOKEN}",
            "zone_id": "${CF_ZONE_ID}",
            "email": "contact@wikiteq.com",
        },
        "monitoring": {
            "load_thresholds": {
                "upper": 2.0,
                "lower": 1.0,
                "use_relative_thresholds": False,
                "relative_upper_multiplier": 2.0,
                "relative_lower_multiplier": 1.5,
                "baseline_calculation_hours": 24,
                "baseline_update_interval": 3600,
            },
            "check_interval": 5,
            "minimum_uam_duration": 300,
        },
        "security": {
            "regular_mode": "essentially_off",
        },
        "logging": {
            "level": "INFO",
            "format": "json",
            "output": "file",
            "file_path": "/var/log/autouam.log",
            "max_size_mb": 100,
            "max_backups": 5,
        },
        "deployment": {
            "mode": "daemon",
            "pid_file": "/var/run/autouam.pid",
            "user": "autouam",
            "group": "autouam",
        },
        "health": {
            "enabled": True,
            "port": 8080,
            "endpoint": "/health",
            "metrics_endpoint": "/metrics",
        },
    }
