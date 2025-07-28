"""Common test fixtures and utilities for AutoUAM tests."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from autouam.config.settings import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    return Settings(
        cloudflare={
            "api_token": "test_token_123456789",
            "email": "test@example.com",
            "zone_id": "test_zone_123456789",
        },
        monitoring={
            "check_interval": 5,
            "load_thresholds": {"upper": 2.0, "lower": 1.0},
            "minimum_uam_duration": 300,
        },
        logging={"level": "INFO", "output": "stdout", "format": "text"},
        health={"enabled": True, "port": 8080},
        deployment={"mode": "daemon"},
        security={"regular_mode": "essentially_off"},
    )


@pytest.fixture
def mock_settings_with_relative_thresholds():
    """Create mock settings with relative thresholds enabled."""
    return Settings(
        cloudflare={
            "api_token": "test_token_123456789",
            "email": "test@example.com",
            "zone_id": "test_zone_123456789",
        },
        monitoring={
            "load_thresholds": {
                "upper": 2.0,
                "lower": 1.0,
                "use_relative_thresholds": True,
                "relative_upper_multiplier": 2.0,
                "relative_lower_multiplier": 1.5,
                "baseline_calculation_hours": 24,
                "baseline_update_interval": 3600,
            },
            "check_interval": 60,
            "minimum_uam_duration": 300,
        },
        security={"regular_mode": "essentially_off"},
        logging={"level": "INFO", "output": "stdout"},
        health={"enabled": False},
        deployment={"mode": "daemon"},
    )


@pytest.fixture
def mock_cloudflare_response():
    """Mock successful Cloudflare API response."""
    return {"result": {"security_level": "essentially_off"}, "success": True}


@pytest.fixture
def mock_cloudflare_client():
    """Create a mock Cloudflare client."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.test_connection = AsyncMock(return_value=True)
    return mock_client


@pytest.fixture
def temp_config_file():
    """Create a temporary configuration file."""
    config_data = {
        "cloudflare": {
            "api_token": "${CF_API_TOKEN}",
            "email": "contact@wikiteq.com",
            "zone_id": "${CF_ZONE_ID}",
        },
        "monitoring": {
            "check_interval": 10,
            "load_thresholds": {"upper": 30.0, "lower": 10.0},
            "minimum_uam_duration": 600,
        },
        "logging": {
            "level": "DEBUG",
            "output": "file",
            "format": "json",
            "file_path": "/var/log/autouam.log",
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = Path(f.name)

    yield config_path

    # Cleanup
    config_path.unlink(missing_ok=True)


@pytest.fixture
def temp_state_dir():
    """Create a temporary directory for state files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        state_dir = Path(temp_dir) / "autouam"
        state_dir.mkdir()
        yield state_dir
