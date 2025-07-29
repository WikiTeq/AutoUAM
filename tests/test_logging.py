"""Tests for logging setup functionality."""

import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from autouam.config.settings import LoggingConfig
from autouam.logging.setup import setup_logging


class TestLoggingSetup:
    """Test logging setup functionality."""

    @pytest.fixture
    def mock_logging_config(self):
        """Create mock logging config for testing."""
        return LoggingConfig(
            level="INFO",
            format="text",
            output="stdout",
            file_path="/var/log/autouam.log",
            max_size_mb=100,
            max_backups=5,
        )

    def test_setup_logging_stdout_text(self, mock_logging_config):
        """Test logging setup with stdout and text format."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

        with patch("sys.stdout"):
            setup_logging(mock_logging_config)

        # Verify that logging is configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_setup_logging_stdout_json(self, mock_logging_config):
        """Test logging setup with stdout and JSON format."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

        mock_logging_config.format = "json"

        with patch("sys.stdout"):
            setup_logging(mock_logging_config)

        # Verify that logging is configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_setup_logging_file(self, mock_logging_config):
        """Test logging setup with file output."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

        mock_logging_config.output = "file"

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            mock_logging_config.file_path = str(log_file)

            setup_logging(mock_logging_config)

            # Verify that logging is configured
            root_logger = logging.getLogger()
            assert root_logger.level == logging.INFO

    def test_setup_logging_file_json(self, mock_logging_config):
        """Test logging setup with file output and JSON format."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

        mock_logging_config.output = "file"
        mock_logging_config.format = "json"

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            mock_logging_config.file_path = str(log_file)

            setup_logging(mock_logging_config)

            # Verify that logging is configured
            root_logger = logging.getLogger()
            assert root_logger.level == logging.INFO

    def test_setup_logging_both(self, mock_logging_config):
        """Test logging setup with both stdout and file output."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

        mock_logging_config.output = "both"

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            mock_logging_config.file_path = str(log_file)

            with patch("sys.stdout"):
                setup_logging(mock_logging_config)

            # Verify that logging is configured
            root_logger = logging.getLogger()
            assert root_logger.level == logging.INFO

    def test_setup_logging_debug_level(self, mock_logging_config):
        """Test logging setup with DEBUG level."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

        mock_logging_config.level = "DEBUG"

        with patch("sys.stdout"):
            setup_logging(mock_logging_config)

        # Verify that logging is configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_warning_level(self, mock_logging_config):
        """Test logging setup with WARNING level."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.DEBUG)

        mock_logging_config.level = "WARNING"

        with patch("sys.stdout"):
            setup_logging(mock_logging_config)

        # Verify that logging is configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    def test_setup_logging_error_level(self, mock_logging_config):
        """Test logging setup with ERROR level."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

        mock_logging_config.level = "ERROR"

        with patch("sys.stdout"):
            setup_logging(mock_logging_config)

        # Verify that logging is configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.ERROR

    def test_setup_logging_critical_level(self, mock_logging_config):
        """Test logging setup with CRITICAL level."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

        mock_logging_config.level = "CRITICAL"

        with patch("sys.stdout"):
            setup_logging(mock_logging_config)

        # Verify that logging is configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.CRITICAL

    def test_setup_logging_invalid_level(self, mock_logging_config):
        """Test logging setup with invalid level."""
        mock_logging_config.level = "INVALID"

        with pytest.raises(AttributeError):
            setup_logging(mock_logging_config)

    def test_setup_logging_invalid_format(self, mock_logging_config):
        """Test logging setup with invalid format (should default to text)."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

        mock_logging_config.format = "invalid"

        with patch("sys.stdout"):
            setup_logging(mock_logging_config)

        # Verify that logging is configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_setup_logging_invalid_output(self, mock_logging_config):
        """Test logging setup with invalid output (should default to stdout)."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

        mock_logging_config.output = "invalid"

        with patch("sys.stdout"):
            setup_logging(mock_logging_config)

        # Verify that logging is configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_setup_logging_file_creation_error(self, mock_logging_config):
        """Test logging setup with file creation error."""
        mock_logging_config.output = "file"
        mock_logging_config.file_path = "/invalid/path"

        with pytest.raises(PermissionError):
            setup_logging(mock_logging_config)

    def test_setup_logging_structlog_configuration(self, mock_logging_config):
        """Test that structlog is properly configured."""
        with patch("sys.stdout"):
            setup_logging(mock_logging_config)

        # Verify that structlog is configured
        import structlog

        assert structlog.is_configured()

    def test_setup_logging_structlog_json_format(self, mock_logging_config):
        """Test structlog configuration with JSON format."""
        mock_logging_config.format = "json"

        with patch("sys.stdout"):
            setup_logging(mock_logging_config)

        # Verify that structlog is configured
        import structlog

        assert structlog.is_configured()

    def test_setup_logging_rotating_file_handler(self, mock_logging_config):
        """Test logging setup with rotating file handler."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

        mock_logging_config.output = "file"
        mock_logging_config.max_size_mb = 10
        mock_logging_config.max_backups = 3

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            mock_logging_config.file_path = str(log_file)

            setup_logging(mock_logging_config)

            # Verify that logging is configured
            root_logger = logging.getLogger()
            assert root_logger.level == logging.INFO

    def test_setup_logging_multiple_calls(self, mock_logging_config):
        """Test that multiple calls to setup_logging work correctly."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

        with patch("sys.stdout"):
            # First call
            setup_logging(mock_logging_config)
            root_logger1 = logging.getLogger()

            # Second call
            setup_logging(mock_logging_config)
            root_logger2 = logging.getLogger()

            # Both should be the same logger instance
            assert root_logger1 is root_logger2
            assert root_logger1.level == logging.INFO

    def test_setup_logging_handler_removal(self, mock_logging_config):
        """Test that existing handlers are properly managed."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

        with patch("sys.stdout"):
            setup_logging(mock_logging_config)

        # Verify that handlers are added
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0
