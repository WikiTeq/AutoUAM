"""Configuration validation utilities."""

from pathlib import Path
from typing import Any


def validate_config_file(config_path: Path) -> list[str]:
    """Validate configuration file and return list of errors."""
    errors = []

    if not config_path.exists():
        errors.append(f"Configuration file not found: {config_path}")
        return errors

    try:
        from .settings import Settings

        Settings.from_file(config_path)
    except Exception as e:
        errors.append(f"Failed to load configuration: {e}")

    return errors


def generate_sample_config() -> dict[str, Any]:
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
