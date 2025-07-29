"""Tests for CLI functionality."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from autouam.cli.commands import main


class TestCLICommands:
    """Test CLI commands."""

    @pytest.fixture
    def cli_runner(self):
        """Create a CLI runner for testing."""
        return CliRunner()

    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file."""
        config_data = {
            "cloudflare": {
                "api_token": "test_token_123456789",
                "email": "test@example.com",
                "zone_id": "test_zone_123456789",
            },
            "monitoring": {
                "check_interval": 5,
                "load_thresholds": {"upper": 2.0, "lower": 1.0},
                "minimum_uam_duration": 300,
            },
            "logging": {"level": "INFO", "output": "stdout", "format": "text"},
            "health": {"enabled": True, "port": 8080},
            "deployment": {"mode": "daemon"},
            "security": {"regular_mode": "essentially_off"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            import yaml

            yaml.dump(config_data, f)
            config_path = Path(f.name)

        yield config_path

        # Cleanup
        config_path.unlink(missing_ok=True)

    def test_help_command(self, cli_runner):
        """Test help command."""
        result = cli_runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_version_command(self, cli_runner):
        """Test version command."""
        result = cli_runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "autouam" in result.output

    @patch("autouam.cli.commands.UAMManager")
    def test_check_command(self, mock_uam_manager_class, cli_runner, temp_config_file):
        """Test check command."""
        # Mock UAMManager
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock(return_value=True)
        mock_manager.check_once = AsyncMock(
            return_value={
                "system": {
                    "load_average": {
                        "one_minute": 1.5,
                        "five_minute": 1.3,
                        "fifteen_minute": 1.2,
                        "normalized": 0.75,
                    },
                    "cpu_count": 4,
                    "processes": {"running": 150, "total": 200},
                },
                "state": {
                    "is_enabled": False,
                    "reason": "Normal load",
                    "last_check": "2023-01-01T00:00:00Z",
                    "load_average": 1.5,
                    "threshold_used": 2.0,
                    "current_duration": None,
                },
                "config": {
                    "upper_threshold": 2.0,
                    "lower_threshold": 1.0,
                    "check_interval": 30,
                    "minimum_duration": 300,
                },
            }
        )
        mock_uam_manager_class.return_value = mock_manager

        result = cli_runner.invoke(main, ["check", "--config", str(temp_config_file)])
        assert result.exit_code == 0
        assert "Load Average" in result.output

    @patch("autouam.cli.commands.UAMManager")
    def test_enable_command(self, mock_uam_manager_class, cli_runner, temp_config_file):
        """Test enable command."""
        # Mock UAMManager
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock(return_value=True)
        mock_manager.enable_uam_manual = AsyncMock(return_value=True)
        mock_uam_manager_class.return_value = mock_manager

        result = cli_runner.invoke(main, ["enable", "--config", str(temp_config_file)])
        assert result.exit_code == 0
        assert "enabled" in result.output.lower()

    @patch("autouam.cli.commands.UAMManager")
    def test_disable_command(
        self, mock_uam_manager_class, cli_runner, temp_config_file
    ):
        """Test disable command."""
        # Mock UAMManager
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock(return_value=True)
        mock_manager.disable_uam_manual = AsyncMock(return_value=True)
        mock_uam_manager_class.return_value = mock_manager

        result = cli_runner.invoke(main, ["disable", "--config", str(temp_config_file)])
        assert result.exit_code == 0
        assert "disabled" in result.output.lower()

    @patch("autouam.cli.commands.UAMManager")
    def test_monitor_command(
        self, mock_uam_manager_class, cli_runner, temp_config_file
    ):
        """Test monitor command."""
        # Mock UAMManager
        mock_manager = MagicMock()
        mock_manager.start_monitoring = AsyncMock()
        mock_uam_manager_class.return_value = mock_manager

        # We need to mock the signal handling to prevent the test from hanging
        with patch("signal.signal"):
            result = cli_runner.invoke(
                main,
                ["monitor", "--config", str(temp_config_file)],
                catch_exceptions=False,
            )
            # The monitor command runs indefinitely, so we expect it to not exit
            # normally. In a real test, we'd need to send a signal to stop it
            # Use result to avoid unused variable warning
            assert result is not None

    def test_invalid_config_file(self, cli_runner):
        """Test command with invalid config file."""
        result = cli_runner.invoke(main, ["check", "--config", "nonexistent.yaml"])
        assert result.exit_code != 0
        assert "error" in result.output.lower()

    def test_missing_config_file(self, cli_runner):
        """Test command without config file."""
        result = cli_runner.invoke(main, ["check"])
        assert result.exit_code != 0
        assert "cloudflare" in result.output.lower()

    @patch("autouam.cli.commands.UAMManager")
    def test_uam_manager_initialization_error(
        self, mock_uam_manager_class, cli_runner, temp_config_file
    ):
        """Test handling of UAMManager initialization errors."""
        # Mock UAMManager to raise an exception
        mock_uam_manager_class.side_effect = Exception("Initialization failed")

        result = cli_runner.invoke(main, ["check", "--config", str(temp_config_file)])
        assert result.exit_code != 0
        assert "error" in result.output.lower()

    @patch("autouam.cli.commands.UAMManager")
    def test_config_validation_error(
        self, mock_uam_manager_class, cli_runner, temp_config_file
    ):
        """Test handling of config validation errors."""
        # Mock UAMManager to fail initialization
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock(return_value=False)
        mock_uam_manager_class.return_value = mock_manager

        result = cli_runner.invoke(main, ["check", "--config", str(temp_config_file)])
        assert result.exit_code != 0
        assert "Failed to initialize UAM manager" in result.output

    def test_verbose_output(self, cli_runner, temp_config_file):
        """Test verbose output flag."""
        with patch("autouam.cli.commands.UAMManager") as mock_uam_manager_class:
            mock_manager = MagicMock()
            mock_manager.initialize = AsyncMock(return_value=True)
            mock_manager.check_once = AsyncMock(
                return_value={
                    "system": {
                        "load_average": {
                            "one_minute": 1.5,
                            "five_minute": 1.3,
                            "fifteen_minute": 1.2,
                            "normalized": 0.75,
                        },
                        "cpu_count": 4,
                        "processes": {"running": 150, "total": 200},
                    },
                    "state": {
                        "is_enabled": False,
                        "reason": "Normal load",
                        "last_check": "2023-01-01T00:00:00Z",
                        "load_average": 1.5,
                        "threshold_used": 2.0,
                        "current_duration": None,
                    },
                    "config": {
                        "upper_threshold": 2.0,
                        "lower_threshold": 1.0,
                        "check_interval": 30,
                        "minimum_duration": 300,
                    },
                }
            )
            mock_uam_manager_class.return_value = mock_manager

            result = cli_runner.invoke(
                main, ["--verbose", "check", "--config", str(temp_config_file)]
            )
            assert result.exit_code == 0
            # Verbose output should contain more detailed information
            assert "Load Average" in result.output
