"""Tests for dynamic threshold configuration and integration."""

import time
from unittest.mock import AsyncMock, patch

import pytest

from autouam.config.settings import LoadThresholds, Settings
from autouam.core.uam_manager import UAMManager


class TestDynamicThresholdConfig:
    """Test dynamic threshold configuration validation."""

    def test_valid_relative_thresholds(self):
        """Test valid relative threshold configuration."""
        thresholds = LoadThresholds(
            upper=2.0,
            lower=1.0,
            use_relative_thresholds=True,
            relative_upper_multiplier=2.0,
            relative_lower_multiplier=1.5,
            baseline_calculation_hours=24,
            baseline_update_interval=3600,
        )

        assert thresholds.use_relative_thresholds is True
        assert thresholds.relative_upper_multiplier == 2.0
        assert thresholds.relative_lower_multiplier == 1.5
        assert thresholds.baseline_calculation_hours == 24
        assert thresholds.baseline_update_interval == 3600

    def test_invalid_relative_multiplier_negative(self):
        """Test negative relative multiplier validation."""
        with pytest.raises(ValueError, match="Relative multipliers must be positive"):
            LoadThresholds(
                upper=2.0,
                lower=1.0,
                use_relative_thresholds=True,
                relative_upper_multiplier=-1.0,
                relative_lower_multiplier=1.5,
            )

    def test_invalid_relative_multiplier_zero(self):
        """Test zero relative multiplier validation."""
        with pytest.raises(ValueError, match="Relative multipliers must be positive"):
            LoadThresholds(
                upper=2.0,
                lower=1.0,
                use_relative_thresholds=True,
                relative_upper_multiplier=0.0,
                relative_lower_multiplier=1.5,
            )

    def test_invalid_baseline_hours_too_low(self):
        """Test baseline hours validation - too low."""
        with pytest.raises(
            ValueError, match="Baseline calculation hours must be between 1 and 168"
        ):
            LoadThresholds(
                upper=2.0,
                lower=1.0,
                use_relative_thresholds=True,
                baseline_calculation_hours=0,
            )

    def test_invalid_baseline_hours_too_high(self):
        """Test baseline hours validation - too high."""
        with pytest.raises(
            ValueError, match="Baseline calculation hours must be between 1 and 168"
        ):
            LoadThresholds(
                upper=2.0,
                lower=1.0,
                use_relative_thresholds=True,
                baseline_calculation_hours=200,
            )

    def test_invalid_baseline_interval_too_low(self):
        """Test baseline interval validation - too low."""
        with pytest.raises(
            ValueError, match="Baseline update interval must be at least 60 seconds"
        ):
            LoadThresholds(
                upper=2.0,
                lower=1.0,
                use_relative_thresholds=True,
                baseline_update_interval=30,
            )

    def test_default_relative_thresholds_disabled(self):
        """Test that relative thresholds are disabled by default."""
        thresholds = LoadThresholds()
        assert thresholds.use_relative_thresholds is False

    def test_relative_thresholds_with_absolute_fallback(self):
        """Test that absolute thresholds still work when relative is disabled."""
        thresholds = LoadThresholds(
            upper=2.0,
            lower=1.0,
            use_relative_thresholds=False,
        )

        assert thresholds.upper == 2.0
        assert thresholds.lower == 1.0


class TestUAMManagerDynamicThresholds:
    """Test UAM manager with dynamic thresholds."""

    @pytest.fixture
    def config_with_relative_thresholds(self):
        """Create config with relative thresholds enabled."""
        return Settings(
            cloudflare={
                "api_token": "test_token_123456789",
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
    def config_with_absolute_thresholds(self):
        """Create config with absolute thresholds."""
        return Settings(
            cloudflare={
                "api_token": "test_token_123456789",
                "zone_id": "test_zone_123456789",
            },
            monitoring={
                "load_thresholds": {
                    "upper": 2.0,
                    "lower": 1.0,
                    "use_relative_thresholds": False,
                },
                "check_interval": 60,
                "minimum_uam_duration": 300,
            },
            security={"regular_mode": "essentially_off"},
            logging={"level": "INFO", "output": "stdout"},
            health={"enabled": False},
            deployment={"mode": "daemon"},
        )

    @patch("os.path.exists", return_value=True)
    async def test_uam_manager_relative_thresholds_enabled(
        self, mock_exists, config_with_relative_thresholds
    ):
        """Test UAM manager with relative thresholds enabled."""
        manager = UAMManager(config_with_relative_thresholds)

        # Mock Cloudflare client
        manager.cloudflare_client = AsyncMock()
        manager.cloudflare_client.test_connection.return_value = True

        # Mock monitor to return high load
        with patch.object(
            manager.monitor, "get_normalized_load", return_value=3.0
        ), patch.object(
            manager.monitor, "is_high_load", return_value=True
        ), patch.object(
            manager.monitor, "is_low_load", return_value=False
        ), patch.object(
            manager.monitor.baseline, "get_baseline", return_value=1.0
        ), patch.object(
            manager.monitor.baseline, "should_update_baseline", return_value=False
        ):

            # Mock state manager
            with patch.object(
                manager.state_manager, "load_state"
            ) as mock_load_state, patch.object(
                manager.state_manager, "update_state"
            ) as mock_update_state:

                mock_load_state.return_value.is_enabled = False

                # Run evaluation
                await manager._evaluate_and_act(3.0, mock_load_state.return_value)

                # Should have called update_state with enabled=True
                mock_update_state.assert_called()
                call_args = mock_update_state.call_args
                assert call_args[1]["is_enabled"] is True
                assert "relative" in call_args[1]["reason"]

    @patch("os.path.exists", return_value=True)
    async def test_uam_manager_absolute_thresholds(
        self, mock_exists, config_with_absolute_thresholds
    ):
        """Test UAM manager with absolute thresholds."""
        manager = UAMManager(config_with_absolute_thresholds)

        # Mock Cloudflare client
        manager.cloudflare_client = AsyncMock()
        manager.cloudflare_client.test_connection.return_value = True

        # Mock monitor to return high load
        with patch.object(
            manager.monitor, "get_normalized_load", return_value=3.0
        ), patch.object(
            manager.monitor, "is_high_load", return_value=True
        ), patch.object(
            manager.monitor, "is_low_load", return_value=False
        ):

            # Mock state manager
            with patch.object(
                manager.state_manager, "load_state"
            ) as mock_load_state, patch.object(
                manager.state_manager, "update_state"
            ) as mock_update_state:

                mock_load_state.return_value.is_enabled = False

                # Run evaluation
                await manager._evaluate_and_act(3.0, mock_load_state.return_value)

                # Should have called update_state with enabled=True
                mock_update_state.assert_called()
                call_args = mock_update_state.call_args
                assert call_args[1]["is_enabled"] is True
                assert "relative" not in call_args[1]["reason"]

    @patch("os.path.exists", return_value=True)
    async def test_uam_manager_baseline_update_triggered(
        self, mock_exists, config_with_relative_thresholds
    ):
        """Test that baseline update is triggered when needed."""
        manager = UAMManager(config_with_relative_thresholds)

        # Mock Cloudflare client
        manager.cloudflare_client = AsyncMock()
        manager.cloudflare_client.test_connection.return_value = True

        # Mock monitor with baseline update needed
        with patch.object(
            manager.monitor, "get_normalized_load", return_value=1.5
        ), patch.object(
            manager.monitor, "is_high_load", return_value=False
        ), patch.object(
            manager.monitor, "is_low_load", return_value=False
        ), patch.object(
            manager.monitor.baseline, "should_update_baseline", return_value=True
        ), patch.object(
            manager.monitor, "update_baseline"
        ) as mock_update_baseline:

            # Mock state manager
            with patch.object(
                manager.state_manager, "load_state"
            ) as mock_load_state, patch.object(manager.state_manager, "update_state"):

                mock_load_state.return_value.is_enabled = False

                # Run monitoring cycle
                await manager._monitoring_cycle()

                # Should have called update_baseline
                mock_update_baseline.assert_called_once_with(
                    24
                )  # baseline_calculation_hours

    @patch("os.path.exists", return_value=True)
    async def test_uam_manager_relative_thresholds_no_baseline(
        self, mock_exists, config_with_relative_thresholds
    ):
        """Test UAM manager with relative thresholds but no baseline available."""
        manager = UAMManager(config_with_relative_thresholds)

        # Mock Cloudflare client
        manager.cloudflare_client = AsyncMock()
        manager.cloudflare_client.test_connection.return_value = True

        # Mock monitor with no baseline
        with patch.object(
            manager.monitor, "get_normalized_load", return_value=3.0
        ), patch.object(
            manager.monitor, "is_high_load", return_value=True
        ), patch.object(
            manager.monitor, "is_low_load", return_value=False
        ), patch.object(
            manager.monitor.baseline, "get_baseline", return_value=None
        ):

            # Mock state manager
            with patch.object(
                manager.state_manager, "load_state"
            ) as mock_load_state, patch.object(
                manager.state_manager, "update_state"
            ) as mock_update_state:

                mock_load_state.return_value.is_enabled = False

                # Run evaluation
                await manager._evaluate_and_act(3.0, mock_load_state.return_value)

                # Should have called update_state with enabled=True (fallback)
                mock_update_state.assert_called()
                call_args = mock_update_state.call_args
                assert call_args[1]["is_enabled"] is True
                assert (
                    "relative" not in call_args[1]["reason"]
                )  # Should not mention relative


class TestDynamicThresholdIntegration:
    """Integration tests for dynamic thresholds."""

    @patch("os.path.exists", return_value=True)
    def test_end_to_end_relative_threshold_workflow(self, mock_exists):
        """Test end-to-end workflow with relative thresholds."""
        from autouam.config.settings import LoadThresholds
        from autouam.core.monitor import LoadMonitor

        # Create monitor
        monitor = LoadMonitor()

        # Add some baseline data
        for i in range(10):
            monitor.baseline.add_sample(1.0 + (i * 0.1), time.time() - (i * 3600))

        # Calculate baseline
        baseline = monitor.baseline.calculate_baseline(hours=24)
        assert baseline is not None

        # Test relative thresholds
        thresholds = LoadThresholds(
            use_relative_thresholds=True,
            relative_upper_multiplier=2.0,
            relative_lower_multiplier=1.5,
        )

        # Mock normalized load
        with patch.object(monitor, "get_normalized_load", return_value=baseline * 2.5):
            # Should trigger high load (2.5 > 2.0 * baseline)
            is_high = monitor.is_high_load(
                threshold=5.0,  # Not used
                use_relative=True,
                relative_multiplier=thresholds.relative_upper_multiplier,
            )
            assert is_high is True

        with patch.object(monitor, "get_normalized_load", return_value=baseline * 1.2):
            # Should not trigger high load (1.2 < 2.0 * baseline)
            is_high = monitor.is_high_load(
                threshold=5.0,  # Not used
                use_relative=True,
                relative_multiplier=thresholds.relative_upper_multiplier,
            )
            assert is_high is False
