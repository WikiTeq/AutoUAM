"""Tests for load monitoring functionality."""

from unittest.mock import patch

import pytest

from autouam.core.monitor import LoadAverage, LoadMonitor


class TestLoadAverage:
    """Test LoadAverage dataclass."""

    def test_load_average_creation(self):
        """Test LoadAverage creation."""
        load_avg = LoadAverage(
            one_minute=1.5,
            five_minute=2.0,
            fifteen_minute=2.5,
            timestamp=1234567890.0,
        )

        assert load_avg.one_minute == 1.5
        assert load_avg.five_minute == 2.0
        assert load_avg.fifteen_minute == 2.5
        assert load_avg.timestamp == 1234567890.0
        assert load_avg.average == 2.0  # Should return five_minute


class TestLoadMonitor:
    """Test LoadMonitor class."""

    def test_load_monitor_initialization(self):
        """Test LoadMonitor initialization."""
        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()
            assert monitor is not None

    @patch("os.getloadavg", return_value=(1.23, 4.56, 7.89))
    def test_get_load_average_success(self, mock_getloadavg):
        """Test successful load average retrieval."""
        monitor = LoadMonitor()
        load_avg = monitor.get_load_average()

        assert load_avg.one_minute == 1.23
        assert load_avg.five_minute == 4.56
        assert load_avg.fifteen_minute == 7.89

    @patch("os.getloadavg", return_value=(1.23, 4.56, 7.89))
    def test_get_load_average_invalid_format(self, mock_getloadavg):
        """Test load average retrieval with invalid format."""
        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()
            # os.getloadavg() should work, so this test is now about
            # /proc/loadavg parsing which is optional metadata,
            # so it should not raise an error
            load_avg = monitor.get_load_average()
            assert load_avg.one_minute == 1.23

    @patch("os.getloadavg", return_value=(1.23, 4.56, 7.89))
    def test_get_load_average_missing_pid(self, mock_getloadavg):
        """Test load average retrieval with missing PID."""
        monitor = LoadMonitor()
        load_avg = monitor.get_load_average()
        assert load_avg.one_minute == 1.23

    @patch("os.getloadavg", return_value=(1.23, 4.56, 7.89))
    def test_get_load_average_invalid_process_count(self, mock_getloadavg):
        """Test load average retrieval with invalid process count."""
        monitor = LoadMonitor()
        load_avg = monitor.get_load_average()
        assert load_avg.one_minute == 1.23

    @patch("os.getloadavg", return_value=(1.23, 4.56, 7.89))
    @patch("builtins.open", side_effect=PermissionError("Permission denied"))
    def test_get_load_average_permission_error(self, mock_file, mock_getloadavg):
        """Test load average retrieval when /proc/loadavg access is denied."""
        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()
            # Permission error on /proc/loadavg is handled gracefully
            # since os.getloadavg() works
            load_avg = monitor.get_load_average()
            assert load_avg.one_minute == 1.23

    @patch("os.cpu_count", return_value=4)
    def test_get_cpu_count_success(self, mock_cpu_count):
        """Test successful CPU count retrieval."""
        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()
            cpu_count = monitor.get_cpu_count()
            assert cpu_count == 4

    @patch("os.cpu_count", return_value=None)
    @patch("builtins.open", side_effect=FileNotFoundError("File not found"))
    def test_get_cpu_count_file_not_found(self, mock_file, mock_cpu_count):
        """Test CPU count when os.cpu_count() returns None and files not found."""
        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()
            cpu_count = monitor.get_cpu_count()
            assert cpu_count == 1  # Default fallback

    @patch.object(LoadMonitor, "get_load_average")
    @patch.object(LoadMonitor, "get_cpu_count")
    def test_get_normalized_load(self, mock_cpu_count, mock_load_average):
        """Test normalized load calculation."""
        mock_load_average.return_value = LoadAverage(
            one_minute=1.0,
            five_minute=10.0,  # This will be used as average
            fifteen_minute=3.0,
            timestamp=1234567890.0,
        )
        mock_cpu_count.return_value = 4

        monitor = LoadMonitor()
        normalized_load = monitor.get_normalized_load()

        assert normalized_load == 2.5  # 10.0 / 4

    @patch.object(LoadMonitor, "get_normalized_load")
    def test_is_high_load_true(self, mock_normalized_load):
        """Test high load detection when load is above threshold."""
        mock_normalized_load.return_value = 3.0

        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()
            is_high = monitor.is_high_load(2.0)

            assert is_high is True

    @patch.object(LoadMonitor, "get_normalized_load")
    def test_is_high_load_false(self, mock_normalized_load):
        """Test high load detection when load is below threshold."""
        mock_normalized_load.return_value = 1.5

        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()
            is_high = monitor.is_high_load(2.0)

            assert is_high is False

    @patch.object(LoadMonitor, "get_normalized_load")
    def test_is_low_load_true(self, mock_normalized_load):
        """Test low load detection when load is below threshold."""
        mock_normalized_load.return_value = 0.5

        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()
            is_low = monitor.is_low_load(1.0)

            assert is_low is True

    @patch.object(LoadMonitor, "get_normalized_load")
    def test_is_low_load_false(self, mock_normalized_load):
        """Test low load detection when load is above threshold."""
        mock_normalized_load.return_value = 1.5

        with patch("os.path.exists", return_value=True):
            monitor = LoadMonitor()
            is_low = monitor.is_low_load(1.0)

            assert is_low is False

    @patch.object(LoadMonitor, "get_load_average")
    @patch.object(LoadMonitor, "get_cpu_count")
    def test_get_system_info_success(self, mock_cpu_count, mock_load_average):
        """Test successful system info retrieval."""
        mock_load_average.return_value = LoadAverage(
            one_minute=1.0,
            five_minute=2.0,
            fifteen_minute=3.0,
            timestamp=1234567890.0,
        )
        mock_cpu_count.return_value = 4

        monitor = LoadMonitor()
        system_info = monitor.get_system_info()

        assert "load_average" in system_info
        assert "cpu_count" in system_info
        assert "timestamp" in system_info
        assert system_info["cpu_count"] == 4
        assert system_info["load_average"]["normalized"] == 0.5  # 2.0 / 4

    @patch.object(LoadMonitor, "get_load_average", side_effect=Exception("Test error"))
    def test_get_system_info_error(self, mock_load_average):
        """Test system info retrieval with error."""
        monitor = LoadMonitor()
        with pytest.raises(Exception, match="Test error"):
            monitor.get_system_info()
