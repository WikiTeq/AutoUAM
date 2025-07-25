"""Integration tests for AutoUAM."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientResponseError

from autouam.config.settings import Settings
from autouam.core.uam_manager import UAMManager
from autouam.health.checks import HealthChecker


class TestUAMManagerIntegration:
    """Integration tests for UAMManager."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        return Settings(
            cloudflare={
                "api_token": "test_token",
                "email": "test@example.com",
                "zone_id": "test_zone_id",
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
    def mock_cloudflare_response(self):
        """Mock successful Cloudflare API response."""
        return {"result": {"security_level": "essentially_off"}, "success": True}

    @pytest.mark.asyncio
    async def test_uam_manager_initialization(self, mock_settings):
        """Test UAMManager initializes correctly."""
        with patch("autouam.core.uam_manager.CloudflareClient") as mock_client_class:
            # Mock the client instance and its async context manager
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.test_connection = AsyncMock(return_value=True)
            mock_client_class.return_value = mock_client_instance

            manager = UAMManager(mock_settings)
            success = await manager.initialize()

            assert success is True

    @pytest.mark.asyncio
    async def test_uam_manager_enable_uam(
        self, mock_settings, mock_cloudflare_response
    ):
        """Test enabling UAM."""
        with patch("autouam.core.uam_manager.CloudflareClient") as mock_client_class:
            # Mock the client instance and its async context manager
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.test_connection = AsyncMock(return_value=True)
            mock_client_instance.enable_under_attack_mode = AsyncMock(
                return_value=mock_cloudflare_response
            )
            mock_client_class.return_value = mock_client_instance

            manager = UAMManager(mock_settings)
            await manager.initialize()

            result = await manager.enable_uam_manual()

            assert result is True
            mock_client_instance.enable_under_attack_mode.assert_called_once()

    @pytest.mark.asyncio
    async def test_uam_manager_disable_uam(
        self, mock_settings, mock_cloudflare_response
    ):
        """Test disabling UAM."""
        with patch("autouam.core.uam_manager.CloudflareClient") as mock_client_class:
            # Mock the client instance and its async context manager
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.test_connection = AsyncMock(return_value=True)
            mock_client_instance.disable_under_attack_mode = AsyncMock(
                return_value=mock_cloudflare_response
            )
            mock_client_class.return_value = mock_client_instance

            manager = UAMManager(mock_settings)
            await manager.initialize()

            result = await manager.disable_uam_manual()

            assert result is True
            mock_client_instance.disable_under_attack_mode.assert_called_once_with(
                regular_mode="essentially_off"
            )

    @pytest.mark.asyncio
    async def test_uam_manager_check_once(self, mock_settings):
        """Test UAM manager check_once method."""
        with patch("autouam.core.uam_manager.CloudflareClient") as mock_client_class:
            # Mock the client instance and its async context manager
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.test_connection = AsyncMock(return_value=True)
            mock_client_class.return_value = mock_client_instance

            # Mock high load
            with patch(
                "autouam.core.monitor.LoadMonitor.get_normalized_load",
                return_value=30.0,
            ):
                manager = UAMManager(mock_settings)

                result = await manager.check_once()

                # Should contain status information
                assert "system" in result
                assert "state" in result
                assert "config" in result

    @pytest.mark.asyncio
    async def test_uam_manager_api_error_handling(self, mock_settings):
        """Test UAM manager handles API errors gracefully."""
        with patch("autouam.core.uam_manager.CloudflareClient") as mock_client_class:
            # Mock the client instance and its async context manager
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.test_connection = AsyncMock(
                side_effect=ClientResponseError(
                    request_info=MagicMock(),
                    history=[],
                    status=403,
                    message="Invalid API token",
                )
            )
            mock_client_class.return_value = mock_client_instance

            manager = UAMManager(mock_settings)
            success = await manager.initialize()

            assert success is False

    @pytest.mark.asyncio
    async def test_uam_manager_rate_limiting(self, mock_settings):
        """Test UAM manager handles rate limiting."""
        with patch("autouam.core.uam_manager.CloudflareClient") as mock_client_class:
            # Mock the client instance and its async context manager
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.test_connection = AsyncMock(return_value=True)
            mock_client_instance.enable_under_attack_mode = AsyncMock(
                side_effect=[
                    ClientResponseError(
                        request_info=MagicMock(),
                        history=[],
                        status=429,
                        message="Rate limited",
                    ),
                    {"success": True},  # Second call succeeds
                ]
            )
            mock_client_class.return_value = mock_client_instance

            manager = UAMManager(mock_settings)
            await manager.initialize()

            # This will fail because the CloudflareClient's retry logic is not being
            # tested here. The rate limiting happens inside the CloudflareClient, not
            # at the UAMManager level
            result = await manager.enable_uam_manual()

            # Should fail due to the rate limit error
            assert result is False


class TestHealthCheckerIntegration:
    """Integration tests for HealthChecker."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        return Settings(
            cloudflare={
                "api_token": "test_token",
                "email": "test@example.com",
                "zone_id": "test_zone_id",
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

    @pytest.mark.asyncio
    async def test_health_checker_all_healthy(self, mock_settings):
        """Test health checker when all systems are healthy."""
        with patch("autouam.health.checks.CloudflareClient") as mock_client_class:
            # Mock the client instance and its async context manager
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.test_connection = AsyncMock(return_value=True)
            mock_client_instance.get_current_security_level = AsyncMock(
                return_value="essentially_off"
            )
            mock_client_class.return_value = mock_client_instance

            checker = HealthChecker(mock_settings)
            await checker.initialize()

            result = await checker.check_health()

            assert result["healthy"] is True
            assert result["checks"]["system_load"]["healthy"] is True
            assert result["checks"]["uam_state"]["healthy"] is True
            assert result["checks"]["cloudflare_api"]["healthy"] is True

    @pytest.mark.asyncio
    async def test_health_checker_api_unhealthy(self, mock_settings):
        """Test health checker when Cloudflare API is unhealthy."""
        with patch("autouam.health.checks.CloudflareClient") as mock_client_class:
            # Mock the client instance and its async context manager
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.test_connection = AsyncMock(
                side_effect=ClientResponseError(
                    request_info=MagicMock(),
                    history=[],
                    status=403,
                    message="Invalid API token",
                )
            )
            mock_client_class.return_value = mock_client_instance

            checker = HealthChecker(mock_settings)
            await checker.initialize()

            result = await checker.check_health()

            assert result["healthy"] is False
            assert result["checks"]["cloudflare_api"]["healthy"] is False
            assert result["checks"]["system_load"]["healthy"] is True
            assert result["checks"]["uam_state"]["healthy"] is True


class TestConfigurationIntegration:
    """Integration tests for configuration handling."""

    def test_configuration_from_file(self):
        """Test loading configuration from file."""
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
            import yaml

            yaml.dump(config_data, f)
            config_path = f.name

        try:
            settings = Settings.from_file(Path(config_path))

            assert settings.cloudflare.email == "contact@wikiteq.com"
            assert settings.monitoring.check_interval == 10
            assert settings.monitoring.load_thresholds.upper == 30.0
            assert settings.logging.level == "DEBUG"

        finally:
            Path(config_path).unlink()

    def test_environment_variable_substitution(self):
        """Test environment variable substitution in configuration."""
        import os

        # Set test environment variables
        os.environ["CF_API_TOKEN"] = "test_token_123"
        os.environ["CF_ZONE_ID"] = "test_zone_456"

        config_data = {
            "cloudflare": {
                "api_token": "${CF_API_TOKEN}",
                "email": "contact@wikiteq.com",
                "zone_id": "${CF_ZONE_ID}",
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            import yaml

            yaml.dump(config_data, f)
            config_path = f.name

        try:
            settings = Settings.from_file(Path(config_path))

            assert settings.cloudflare.api_token == "test_token_123"
            assert settings.cloudflare.zone_id == "test_zone_456"

        finally:
            Path(config_path).unlink()
            # Clean up environment variables
            os.environ.pop("CF_API_TOKEN", None)
            os.environ.pop("CF_ZONE_ID", None)


class TestStatePersistence:
    """Integration tests for state persistence."""

    def test_state_persistence_to_file(self):
        """Test that state is properly persisted to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir) / "autouam"
            state_dir.mkdir()

            from autouam.core.state import StateManager

            state_manager = StateManager(str(state_dir / "state.json"))

            # Get initial state
            initial_state = state_manager.load_state()
            assert initial_state.is_enabled is False

            # Test updating state to enabled
            state_manager.update_state(
                is_enabled=True,
                load_average=25.0,
                threshold_used=25.0,
                reason="High load detected",
            )

            # Test loading state
            loaded_state = state_manager.load_state()

            assert loaded_state.is_enabled is True
            assert loaded_state.load_average == 25.0
            assert loaded_state.threshold_used == 25.0
            assert loaded_state.reason == "High load detected"

    def test_state_persistence_with_minimum_duration(self):
        """Test that minimum duration is respected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir) / "autouam"
            state_dir.mkdir()

            from autouam.core.state import StateManager

            state_manager = StateManager(str(state_dir / "state.json"))

            # Enable UAM at time 1000
            with patch("time.time", return_value=1000.0):
                state_manager.update_state(
                    is_enabled=True,
                    load_average=30.0,
                    threshold_used=25.0,
                    reason="High load detected",
                )

            # Try to disable soon after (should fail due to minimum duration)
            with patch("time.time", return_value=1100.0):  # Only 100 seconds passed
                can_disable = state_manager.can_disable_uam(minimum_duration=300)
                assert can_disable is False

            # Wait longer and try again (should succeed)
            with patch("time.time", return_value=1400.0):  # 400 seconds passed
                can_disable = state_manager.can_disable_uam(minimum_duration=300)
                assert can_disable is True
