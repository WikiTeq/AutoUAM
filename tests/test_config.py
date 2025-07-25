"""Tests for configuration management functionality."""

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from autouam.config.settings import (
    CloudflareConfig,
    DeploymentConfig,
    HealthConfig,
    LoadThresholds,
    LoggingConfig,
    MonitoringConfig,
    Settings,
)
from autouam.config.validators import (
    generate_sample_config,
    validate_config,
    validate_config_file,
)


class TestCloudflareConfig:
    """Test CloudflareConfig class."""

    def test_valid_config(self):
        """Test valid Cloudflare configuration."""
        config = CloudflareConfig(
            api_token="test_token_123456789",
            zone_id="test_zone_123456789",
            email="test@example.com",
        )

        assert config.api_token == "test_token_123456789"
        assert config.zone_id == "test_zone_123456789"
        assert config.email == "test@example.com"

    def test_invalid_api_token(self):
        """Test invalid API token validation."""
        with pytest.raises(
            ValueError, match="API token must be at least 10 characters long"
        ):
            CloudflareConfig(api_token="short", zone_id="test_zone_123456789")

    def test_invalid_zone_id(self):
        """Test invalid zone ID validation."""
        with pytest.raises(
            ValueError, match="Zone ID must be at least 10 characters long"
        ):
            CloudflareConfig(api_token="test_token_123456789", zone_id="short")


class TestLoadThresholds:
    """Test LoadThresholds class."""

    def test_valid_thresholds(self):
        """Test valid load thresholds."""
        thresholds = LoadThresholds(upper=2.0, lower=1.0)

        assert thresholds.upper == 2.0
        assert thresholds.lower == 1.0

    def test_invalid_negative_threshold(self):
        """Test negative threshold validation."""
        with pytest.raises(ValueError, match="Thresholds must be positive"):
            LoadThresholds(upper=-1.0, lower=1.0)

    def test_invalid_zero_threshold(self):
        """Test zero threshold validation."""
        with pytest.raises(ValueError, match="Thresholds must be positive"):
            LoadThresholds(upper=2.0, lower=0.0)

    def test_invalid_lower_greater_than_upper(self):
        """Test lower threshold greater than upper threshold."""
        with pytest.raises(
            ValueError, match="Lower threshold must be less than upper threshold"
        ):
            LoadThresholds(upper=1.0, lower=2.0)

    def test_invalid_lower_equal_to_upper(self):
        """Test lower threshold equal to upper threshold."""
        with pytest.raises(
            ValueError, match="Lower threshold must be less than upper threshold"
        ):
            LoadThresholds(upper=2.0, lower=2.0)


class TestMonitoringConfig:
    """Test MonitoringConfig class."""

    def test_valid_config(self):
        """Test valid monitoring configuration."""
        config = MonitoringConfig(
            load_thresholds=LoadThresholds(upper=2.0, lower=1.0),
            check_interval=5,
            minimum_uam_duration=300,
        )

        assert config.load_thresholds.upper == 2.0
        assert config.load_thresholds.lower == 1.0
        assert config.check_interval == 5
        assert config.minimum_uam_duration == 300

    def test_invalid_check_interval(self):
        """Test invalid check interval validation."""
        with pytest.raises(
            ValueError, match="Check interval must be at least 1 second"
        ):
            MonitoringConfig(check_interval=0)

    def test_invalid_minimum_duration(self):
        """Test invalid minimum duration validation."""
        with pytest.raises(
            ValueError, match="Minimum UAM duration must be at least 60 seconds"
        ):
            MonitoringConfig(minimum_uam_duration=30)


class TestLoggingConfig:
    """Test LoggingConfig class."""

    def test_valid_config(self):
        """Test valid logging configuration."""
        config = LoggingConfig(
            level="INFO",
            format="json",
            output="file",
            file_path="/var/log/autouam.log",
            max_size_mb=100,
            max_backups=5,
        )

        assert config.level == "INFO"
        assert config.format == "json"
        assert config.output == "file"
        assert config.file_path == "/var/log/autouam.log"
        assert config.max_size_mb == 100
        assert config.max_backups == 5

    def test_invalid_log_level(self):
        """Test invalid log level validation."""
        with pytest.raises(ValueError, match="Log level must be one of"):
            LoggingConfig(level="INVALID")

    def test_invalid_log_format(self):
        """Test invalid log format validation."""
        with pytest.raises(ValueError, match="Log format must be one of"):
            LoggingConfig(format="invalid")

    def test_invalid_log_output(self):
        """Test invalid log output validation."""
        with pytest.raises(ValueError, match="Log output must be one of"):
            LoggingConfig(output="invalid")


class TestDeploymentConfig:
    """Test DeploymentConfig class."""

    def test_valid_config(self):
        """Test valid deployment configuration."""
        config = DeploymentConfig(
            mode="daemon",
            pid_file="/var/run/autouam.pid",
            user="autouam",
            group="autouam",
        )

        assert config.mode == "daemon"
        assert config.pid_file == "/var/run/autouam.pid"
        assert config.user == "autouam"
        assert config.group == "autouam"

    def test_invalid_deployment_mode(self):
        """Test invalid deployment mode validation."""
        with pytest.raises(ValueError, match="Deployment mode must be one of"):
            DeploymentConfig(mode="invalid")


class TestHealthConfig:
    """Test HealthConfig class."""

    def test_valid_config(self):
        """Test valid health configuration."""
        config = HealthConfig(
            enabled=True, port=8080, endpoint="/health", metrics_endpoint="/metrics"
        )

        assert config.enabled is True
        assert config.port == 8080
        assert config.endpoint == "/health"
        assert config.metrics_endpoint == "/metrics"

    def test_invalid_port_too_low(self):
        """Test invalid port validation (too low)."""
        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            HealthConfig(port=0)

    def test_invalid_port_too_high(self):
        """Test invalid port validation (too high)."""
        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            HealthConfig(port=70000)


class TestSettings:
    """Test Settings class."""

    def test_valid_settings(self):
        """Test valid settings configuration."""
        settings = Settings(
            cloudflare=CloudflareConfig(
                api_token="test_token_123456789", zone_id="test_zone_123456789"
            )
        )

        assert settings.cloudflare.api_token == "test_token_123456789"
        assert settings.cloudflare.zone_id == "test_zone_123456789"
        assert settings.monitoring.load_thresholds.upper == 2.0  # Default
        assert settings.monitoring.load_thresholds.lower == 1.0  # Default

    def test_from_file_success(self):
        """Test loading settings from file."""
        config_data = {
            "cloudflare": {
                "api_token": "test_token_123456789",
                "zone_id": "test_zone_123456789",
            },
            "monitoring": {"load_thresholds": {"upper": 30.0, "lower": 20.0}},
        }

        with patch("pathlib.Path.exists", return_value=True):
            with patch(
                "builtins.open",
                mock_open(
                    read_data=(
                        "cloudflare:\n  api_token: test_token_123456789\n"
                        "  zone_id: test_zone_123456789\nmonitoring:\n"
                        "  load_thresholds:\n    upper: 30.0\n    lower: 20.0"
                    )
                ),
            ):
                with patch("yaml.safe_load", return_value=config_data):
                    settings = Settings.from_file(Path("test.yaml"))

                    assert settings.cloudflare.api_token == "test_token_123456789"
                    assert settings.cloudflare.zone_id == "test_zone_123456789"
                    assert settings.monitoring.load_thresholds.upper == 30.0
                    assert settings.monitoring.load_thresholds.lower == 20.0

    def test_from_file_not_found(self):
        """Test loading settings from non-existent file."""
        with pytest.raises(FileNotFoundError):
            Settings.from_file(Path("nonexistent.yaml"))

    def test_environment_variable_substitution(self):
        """Test environment variable substitution."""
        config_data = {
            "cloudflare": {"api_token": "${CF_API_TOKEN}", "zone_id": "${CF_ZONE_ID}"}
        }

        with patch.dict(
            "os.environ",
            {"CF_API_TOKEN": "env_token_123456789", "CF_ZONE_ID": "env_zone_123456789"},
        ):
            substituted = Settings._substitute_env_vars(config_data)

            assert substituted["cloudflare"]["api_token"] == "env_token_123456789"
            assert substituted["cloudflare"]["zone_id"] == "env_zone_123456789"

    def test_to_dict(self):
        """Test converting settings to dictionary."""
        settings = Settings(
            cloudflare=CloudflareConfig(
                api_token="test_token_123456789", zone_id="test_zone_123456789"
            )
        )

        config_dict = settings.to_dict()

        assert "cloudflare" in config_dict
        assert "monitoring" in config_dict
        assert "logging" in config_dict
        assert config_dict["cloudflare"]["api_token"] == "test_token_123456789"
        assert config_dict["cloudflare"]["zone_id"] == "test_zone_123456789"


class TestValidators:
    """Test configuration validators."""

    def test_validate_config_success(self):
        """Test successful configuration validation."""
        settings = Settings(
            cloudflare=CloudflareConfig(
                api_token="test_token_123456789", zone_id="test_zone_123456789"
            )
        )

        errors = validate_config(settings)
        assert len(errors) == 0

    def test_validate_config_missing_api_token(self):
        """Test configuration validation with missing API token."""
        # Create settings with empty API token - this will fail at validation level
        with pytest.raises(
            ValueError, match="API token must be at least 10 characters long"
        ):
            Settings(
                cloudflare=CloudflareConfig(api_token="", zone_id="test_zone_123456789")
            )

    def test_validate_config_missing_zone_id(self):
        """Test configuration validation with missing zone ID."""
        # Create settings with empty zone ID - this will fail at validation level
        with pytest.raises(
            ValueError, match="Zone ID must be at least 10 characters long"
        ):
            Settings(
                cloudflare=CloudflareConfig(
                    api_token="test_token_123456789", zone_id=""
                )
            )

    def test_validate_config_invalid_thresholds(self):
        """Test configuration validation with invalid thresholds."""
        # Create settings with valid thresholds first
        settings = Settings(
            cloudflare=CloudflareConfig(
                api_token="test_token_123456789", zone_id="test_zone_123456789"
            )
        )
        # Then manually set invalid thresholds to test the validate_config function
        settings.monitoring.load_thresholds.upper = 1.0
        settings.monitoring.load_thresholds.lower = 2.0

        errors = validate_config(settings)
        assert len(errors) == 1
        assert "Lower load threshold must be less than upper threshold" in errors[0]

    def test_validate_config_file_success(self):
        """Test successful configuration file validation."""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("autouam.config.settings.Settings.from_file") as mock_from_file:
                mock_settings = Settings(
                    cloudflare=CloudflareConfig(
                        api_token="test_token_123456789", zone_id="test_zone_123456789"
                    )
                )
                mock_from_file.return_value = mock_settings

                errors = validate_config_file(Path("test.yaml"))
                assert len(errors) == 0

    def test_validate_config_file_not_found(self):
        """Test configuration file validation with non-existent file."""
        with patch("pathlib.Path.exists", return_value=False):
            errors = validate_config_file(Path("nonexistent.yaml"))
            assert len(errors) == 1
            assert "Configuration file not found" in errors[0]

    def test_generate_sample_config(self):
        """Test sample configuration generation."""
        sample_config = generate_sample_config()

        assert "cloudflare" in sample_config
        assert "monitoring" in sample_config
        assert "logging" in sample_config
        assert "health" in sample_config

        assert sample_config["cloudflare"]["api_token"] == "${CF_API_TOKEN}"
        assert sample_config["cloudflare"]["zone_id"] == "${CF_ZONE_ID}"
        assert sample_config["monitoring"]["load_thresholds"]["upper"] == 2.0
        assert sample_config["monitoring"]["load_thresholds"]["lower"] == 1.0
