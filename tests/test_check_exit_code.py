"""Tests for check command exit-code behavior."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from click.testing import CliRunner

from autouam.cli.commands import main


@pytest.fixture
def config_file():
    config_data = {
        "cloudflare": {"api_token": "t", "zone_id": "z"},
        "logging": {"level": "INFO", "output": "stdout", "format": "text"},
        "health": {"enabled": False},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@patch("autouam.cli.commands.UAMManager")
def test_check_exits_nonzero_when_initialization_fails(mock_manager_class, config_file):
    """Failed init (bad token, unreachable API) must not look like success."""
    manager = mock_manager_class.return_value
    manager.initialize = AsyncMock(return_value=False)
    manager.check_once = AsyncMock(side_effect=RuntimeError("Failed to initialize"))
    manager.stop = lambda: None

    result = CliRunner().invoke(main, ["--config", str(config_file), "check"])
    assert result.exit_code != 0
    assert "check failed" in result.output.lower()


@patch("autouam.cli.commands.UAMManager")
def test_check_exits_zero_on_success(mock_manager_class, config_file):
    manager = mock_manager_class.return_value
    manager.check_once = AsyncMock(
        return_value={
            "system": {
                "load_average": {
                    "one_minute": 1.0,
                    "five_minute": 1.0,
                    "fifteen_minute": 1.0,
                    "normalized": 0.25,
                }
            },
            "cpu_count": 4,
            "state": {
                "is_enabled": False,
                "last_check": 1.0,
                "load_average": 1.0,
                "threshold_used": 2.0,
                "reason": "ok",
                "current_duration": None,
            },
            "config": {
                "upper_threshold": 2.0,
                "lower_threshold": 1.0,
                "check_interval": 60,
                "minimum_duration": 300,
            },
        }
    )
    manager.stop = lambda: None

    result = CliRunner().invoke(main, ["--config", str(config_file), "check"])
    assert result.exit_code == 0


@patch("autouam.core.uam_manager.UAMManager.initialize")
@patch("autouam.core.uam_manager.UAMManager.get_status")
def test_check_once_raises_when_init_fails(mock_status, mock_init):
    """check_once must surface failure instead of returning {'error': ...}."""
    from autouam.config.settings import Settings
    from autouam.core.uam_manager import UAMManager

    mock_init.return_value = False
    settings = Settings(
        cloudflare={"api_token": "t", "zone_id": "z"},
        logging={"level": "INFO", "output": "stdout", "format": "text"},
        health={"enabled": False},
    )
    manager = UAMManager(settings)
    with pytest.raises(RuntimeError, match="Failed to initialize"):
        import asyncio

        asyncio.run(manager.check_once())
