"""Tests for dynamic threshold baseline functionality."""

import time
from unittest.mock import patch

from autouam.core.monitor import LoadBaseline, LoadMonitor


class TestLoadBaseline:
    """Test LoadBaseline class."""

    def test_baseline_initialization(self):
        """Test LoadBaseline initialization."""
        baseline = LoadBaseline()
        assert baseline.samples.maxlen == 1440  # 24 hours at 1-minute intervals
        assert baseline.last_update == 0
        assert baseline.baseline is None

    def test_baseline_custom_max_samples(self):
        """Test LoadBaseline with custom max samples."""
        baseline = LoadBaseline(max_samples=100)
        assert baseline.samples.maxlen == 100

    def test_add_sample(self):
        """Test adding samples to baseline."""
        baseline = LoadBaseline(max_samples=5)

        # Add samples
        baseline.add_sample(1.0, time.time())
        baseline.add_sample(2.0, time.time())
        baseline.add_sample(3.0, time.time())

        assert len(baseline.samples) == 3

    def test_add_sample_max_length(self):
        """Test that samples respect max length."""
        baseline = LoadBaseline(max_samples=3)

        # Add more samples than max length
        baseline.add_sample(1.0, time.time())
        baseline.add_sample(2.0, time.time())
        baseline.add_sample(3.0, time.time())
        baseline.add_sample(4.0, time.time())  # This should remove the first sample

        assert len(baseline.samples) == 3
        # The oldest sample (1.0) should be removed
        assert baseline.samples[0][0] == 2.0

    def test_calculate_baseline_no_samples(self):
        """Test baseline calculation with no samples."""
        baseline = LoadBaseline()
        result = baseline.calculate_baseline()
        assert result is None

    def test_calculate_baseline_with_samples(self):
        """Test baseline calculation with samples."""
        baseline = LoadBaseline(max_samples=10)
        current_time = time.time()

        # Add samples with different timestamps
        for i in range(10):
            baseline.add_sample(
                float(i + 1), current_time - (i * 3600)
            )  # Each hour apart

        result = baseline.calculate_baseline(hours=24)
        assert result is not None
        assert result > 0
        assert baseline.baseline == result
        assert baseline.last_update > 0

    def test_calculate_baseline_filtered_by_hours(self):
        """Test that baseline calculation filters by hours."""
        baseline = LoadBaseline(max_samples=10)
        current_time = time.time()

        # Add old samples (more than 24 hours ago)
        baseline.add_sample(1.0, current_time - (25 * 3600))
        baseline.add_sample(2.0, current_time - (26 * 3600))

        # Add recent samples (within 24 hours)
        baseline.add_sample(10.0, current_time - (12 * 3600))
        baseline.add_sample(20.0, current_time - (6 * 3600))

        result = baseline.calculate_baseline(hours=24)
        assert result is not None
        # Should only consider recent samples (10.0 and 20.0)
        assert result >= 10.0

    def test_calculate_baseline_no_recent_samples(self):
        """Test baseline calculation when no samples are within the time window."""
        baseline = LoadBaseline(max_samples=10)
        current_time = time.time()

        # Add only old samples
        baseline.add_sample(1.0, current_time - (25 * 3600))
        baseline.add_sample(2.0, current_time - (26 * 3600))

        result = baseline.calculate_baseline(hours=24)
        assert result is None

    def test_get_baseline(self):
        """Test getting baseline value."""
        baseline = LoadBaseline()

        # Initially should be None
        assert baseline.get_baseline() is None

        # After calculation, should return the value
        baseline.add_sample(1.0, time.time())
        baseline.add_sample(2.0, time.time())  # Need at least 2 samples
        baseline.calculate_baseline()
        assert baseline.get_baseline() is not None

    def test_should_update_baseline(self):
        """Test baseline update timing."""
        baseline = LoadBaseline()

        # Initially should update
        assert baseline.should_update_baseline(3600) is True

        # After calculation, should not update immediately
        baseline.add_sample(1.0, time.time())
        baseline.add_sample(2.0, time.time())  # Need at least 2 samples
        baseline.calculate_baseline()
        assert baseline.should_update_baseline(3600) is False

        # After enough time, should update again
        with patch("time.time", return_value=time.time() + 3601):
            assert baseline.should_update_baseline(3600) is True


class TestLoadMonitorWithBaseline:
    """Test LoadMonitor with baseline functionality."""

    def test_monitor_has_baseline(self):
        """Test that LoadMonitor has baseline functionality."""
        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()
            assert hasattr(monitor, "baseline")
            assert isinstance(monitor.baseline, LoadBaseline)

    def test_update_baseline(self):
        """Test baseline update functionality."""
        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()

            # Add some samples first
            monitor.baseline.add_sample(1.0, time.time())
            monitor.baseline.add_sample(2.0, time.time())

            # Update baseline
            monitor.update_baseline(hours=24)
            assert monitor.baseline.get_baseline() is not None

    @patch.object(LoadMonitor, "get_normalized_load", return_value=4.0)
    def test_is_high_load_relative_true(self, mock_normalized_load):
        """Test relative high load detection when load is above threshold."""
        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()

            # Set up baseline
            monitor.baseline.add_sample(1.0, time.time())
            monitor.baseline.add_sample(1.5, time.time())  # Need at least 2 samples
            monitor.baseline.calculate_baseline()

            # Test with relative threshold (baseline ~1.925 * 2.0 = 3.85, load = 4.0)
            result = monitor.is_high_load(
                threshold=5.0,  # Not used when relative=True
                use_relative=True,
                relative_multiplier=2.0,
            )

            assert result is True

    @patch.object(LoadMonitor, "get_normalized_load", return_value=1.5)
    def test_is_high_load_relative_false(self, mock_normalized_load):
        """Test relative high load detection when load is below threshold."""
        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()

            # Set up baseline
            monitor.baseline.add_sample(1.0, time.time())
            monitor.baseline.add_sample(1.5, time.time())  # Need at least 2 samples
            monitor.baseline.calculate_baseline()

            # Test with relative threshold (baseline ~1.925 * 2.0 = 3.85, load = 1.5)
            result = monitor.is_high_load(
                threshold=5.0,  # Not used when relative=True
                use_relative=True,
                relative_multiplier=2.0,
            )

            assert result is False

    @patch.object(LoadMonitor, "get_normalized_load", return_value=0.5)
    def test_is_low_load_relative_true(self, mock_normalized_load):
        """Test relative low load detection when load is below threshold."""
        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()

            # Set up baseline
            monitor.baseline.add_sample(1.0, time.time())
            monitor.baseline.add_sample(1.5, time.time())  # Need at least 2 samples
            monitor.baseline.calculate_baseline()

            # Test with relative threshold (baseline ~1.925 * 1.5 = 2.89, load = 0.5)
            result = monitor.is_low_load(
                threshold=0.1,  # Not used when relative=True
                use_relative=True,
                relative_multiplier=1.5,
            )

            assert result is True

    @patch.object(LoadMonitor, "get_normalized_load", return_value=3.0)
    def test_is_low_load_relative_false(self, mock_normalized_load):
        """Test relative low load detection when load is above threshold."""
        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()

            # Set up baseline
            monitor.baseline.add_sample(1.0, time.time())
            monitor.baseline.add_sample(1.5, time.time())  # Need at least 2 samples
            monitor.baseline.calculate_baseline()

            # Test with relative threshold (baseline ~1.925 * 1.5 = 2.89, load = 3.0)
            result = monitor.is_low_load(
                threshold=0.1,  # Not used when relative=True
                use_relative=True,
                relative_multiplier=1.5,
            )

            assert result is False

    @patch.object(LoadMonitor, "get_normalized_load", return_value=3.0)
    def test_relative_thresholds_fallback_to_absolute(self, mock_normalized_load):
        """Test that relative thresholds fall back to absolute when no baseline."""
        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()

            # No baseline set up

            # Test with relative threshold but no baseline
            result = monitor.is_high_load(
                threshold=2.0, use_relative=True, relative_multiplier=2.0
            )

            # Should fall back to absolute threshold (3.0 > 2.0)
            assert result is True

    def test_get_normalized_load_adds_to_baseline(self):
        """Test that get_normalized_load adds samples to baseline."""
        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()

            # Mock the load average and CPU count
            with patch.object(
                monitor, "get_load_average"
            ) as mock_load_avg, patch.object(monitor, "get_cpu_count", return_value=2):

                # Mock load average
                mock_load_avg.return_value.average = 4.0
                mock_load_avg.return_value.timestamp = time.time()

                # Get normalized load
                result = monitor.get_normalized_load()

                # Should return normalized value (4.0 / 2 = 2.0)
                assert result == 2.0

                # Should have added sample to baseline
                assert len(monitor.baseline.samples) == 1
                assert monitor.baseline.samples[0][0] == 2.0
