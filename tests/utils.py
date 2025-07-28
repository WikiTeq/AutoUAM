"""Utility functions for testing."""

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError

from autouam.config.settings import Settings
from autouam.core.cloudflare import CloudflareClient


def create_mock_cloudflare_client(
    api_token: str = "test_token",
    zone_id: str = "test_zone",
    base_url: str = "https://api.cloudflare.com/client/v4",
) -> MagicMock:
    """Create a mock CloudflareClient for testing."""
    mock_client = MagicMock(spec=CloudflareClient)
    mock_client.api_token = api_token
    mock_client.zone_id = zone_id
    mock_client.base_url = base_url

    # Mock async methods
    mock_client.test_connection = AsyncMock(return_value=True)
    mock_client.get_current_security_level = AsyncMock(
        return_value="essentially_off"
    )
    mock_client.enable_under_attack_mode = AsyncMock(return_value=True)
    mock_client.disable_under_attack_mode = AsyncMock(return_value=True)
    mock_client._make_request = AsyncMock(return_value={"success": True})

    # Mock context manager
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    return mock_client


def create_api_error_response(
    status: int = 400, message: str = "Bad request"
) -> ClientResponseError:
    """Create a mock API error response."""
    return ClientResponseError(
        request_info=MagicMock(),
        history=[],
        status=status,
        message=message,
    )


@contextmanager
def mock_environment_variables(**variables: str):
    """Context manager to mock environment variables."""
    with patch.dict("os.environ", variables):
        yield


def patch_cloudflare_client(func):
    """Decorator to patch CloudflareClient in tests."""
    return patch("autouam.core.cloudflare.CloudflareClient")(func)


def create_load_average_data(
    one_minute: float = 1.5,
    five_minute: float = 1.3,
    fifteen_minute: float = 1.2,
    normalized: float = 0.75,
) -> Dict[str, Any]:
    """Create mock load average data."""
    return {
        "one_minute": one_minute,
        "five_minute": five_minute,
        "fifteen_minute": fifteen_minute,
        "normalized": normalized,
    }


def mock_load_monitor_methods(monitor_mock: MagicMock):
    """Mock common LoadMonitor methods."""
    monitor_mock.get_system_info.return_value = {
        "load_average": create_load_average_data(),
        "cpu_count": 4,
        "processes": {"running": 150, "total": 200},
    }
    monitor_mock.get_load_average.return_value = create_load_average_data()
    monitor_mock.get_cpu_count.return_value = 4
    monitor_mock.get_normalized_load.return_value = 0.75
    monitor_mock.is_high_load.return_value = False
    monitor_mock.is_low_load.return_value = True


def create_temp_config_file(content: str) -> Path:
    """Create a temporary configuration file for testing."""
    temp_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    )
    temp_file.write(content)
    temp_file.close()
    return Path(temp_file.name)


def create_sample_settings() -> Settings:
    """Create sample settings for testing."""
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
