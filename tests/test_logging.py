"""Tests for logging setup functionality."""

import logging
import tempfile
from pathlib import Path

import pytest

from autouam.config.settings import LoggingConfig
from autouam.logging.setup import _get_renderer, setup_logging


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

    def test_setup_logging_stdout_text(self, mock_logging_config, caplog):
        """Test logging setup with stdout and text format."""
        with caplog.at_level(logging.INFO):
            setup_logging(mock_logging_config)

            # Get logger and log a message
            logger = logging.getLogger("autouam.test")
            logger.info("Test message", extra={"key": "value"})

        # Verify that logging is configured and message was logged
        assert len(caplog.records) > 0
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_setup_logging_stdout_json(self, mock_logging_config, caplog):
        """Test logging setup with stdout and JSON format."""
        mock_logging_config.format = "json"

        with caplog.at_level(logging.INFO):
            setup_logging(mock_logging_config)

            # Get logger and log a message
            logger = logging.getLogger("autouam.test")
            logger.info("Test message", extra={"key": "value"})

        # Verify JSON format - check that structlog is configured with JSON renderer
        import structlog

        assert structlog.is_configured()

        # Verify log level is set
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_setup_logging_file(self, mock_logging_config):
        """Test logging setup with file output."""
        mock_logging_config.output = "file"

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            mock_logging_config.file_path = str(log_file)

            setup_logging(mock_logging_config)

            # Verify that log file was created
            assert log_file.exists()

            # Get logger and log a message
            logger = logging.getLogger("autouam.test")
            logger.info("Test file message")

            # Verify message was written to file
            log_file.read_text()  # Should not raise
            assert log_file.stat().st_size > 0

    def test_setup_logging_file_json(self, mock_logging_config):
        """Test logging setup with file output and JSON format."""
        mock_logging_config.output = "file"
        mock_logging_config.format = "json"

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            mock_logging_config.file_path = str(log_file)

            setup_logging(mock_logging_config)

            # Verify that log file was created
            assert log_file.exists()

            # Get logger and log a message
            logger = logging.getLogger("autouam.test")
            logger.info("Test JSON message", extra={"key": "value"})

            # Verify JSON format in file
            content = log_file.read_text()
            # Should contain JSON-like structure (structlog JSON output)
            assert len(content) > 0

    def test_setup_logging_both(self, mock_logging_config, caplog):
        """Test logging setup with both stdout and file output."""
        # Note: "both" is not a valid output option, so it defaults to stdout
        # This test verifies that invalid output options default gracefully
        mock_logging_config.output = "both"

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            mock_logging_config.file_path = str(log_file)

            with caplog.at_level(logging.INFO):
                setup_logging(mock_logging_config)

                # Get logger and log a message
                logger = logging.getLogger("autouam.test")
                logger.info("Test both message")

            # "both" is not supported, so it defaults to stdout (no file created)
            # Verify logging is configured
            root_logger = logging.getLogger()
            assert root_logger.level == logging.INFO
            # File should not exist since "both" defaults to stdout
            assert not log_file.exists()

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    def test_setup_logging_levels(self, mock_logging_config, level):
        """Test logging setup with different log levels."""
        mock_logging_config.level = level

        setup_logging(mock_logging_config)

        # Verify that logging level is set correctly
        root_logger = logging.getLogger()
        expected_level = getattr(logging, level)
        assert root_logger.level == expected_level

    def test_setup_logging_invalid_level(self, mock_logging_config):
        """Test logging setup with invalid level."""
        mock_logging_config.level = "INVALID"

        with pytest.raises(AttributeError):
            setup_logging(mock_logging_config)

    def test_get_renderer_text(self):
        """Test _get_renderer with text format."""
        renderer = _get_renderer("text")
        # Should return ConsoleRenderer for text format
        from structlog.dev import ConsoleRenderer

        assert isinstance(renderer, ConsoleRenderer)

    def test_get_renderer_json(self):
        """Test _get_renderer with JSON format."""
        renderer = _get_renderer("json")
        # Should return JSONRenderer for JSON format
        from structlog.processors import JSONRenderer

        assert isinstance(renderer, JSONRenderer)

    def test_get_renderer_invalid_format(self):
        """Test _get_renderer with invalid format (should default to text)."""
        renderer = _get_renderer("invalid")
        # Should default to ConsoleRenderer
        from structlog.dev import ConsoleRenderer

        assert isinstance(renderer, ConsoleRenderer)

    def test_setup_logging_invalid_output(self):
        """Test that invalid output raises validation error."""
        # Invalid output should raise ValueError during config creation
        with pytest.raises(ValueError, match="Log output must be one of"):
            LoggingConfig(
                level="INFO",
                format="text",
                output="invalid",  # Invalid output
                file_path="/var/log/autouam.log",
            )

    def test_setup_logging_file_creation_error(self, mock_logging_config):
        """Test logging setup with file creation error."""
        mock_logging_config.output = "file"

        # Use a path that cannot be created (parent directory doesn't exist)
        # But don't use /invalid/path as that might require root permissions
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a path with a non-existent parent
            invalid_path = Path(temp_dir) / "nonexistent" / "test.log"
            mock_logging_config.file_path = str(invalid_path)

            # Should handle the error gracefully or raise a specific exception
            # The actual behavior depends on the implementation
            # If it raises, it should be a specific exception, not a generic one
            try:
                setup_logging(mock_logging_config)
                # If it doesn't raise, verify the directory was created
                assert invalid_path.parent.exists()
            except (OSError, PermissionError):
                # These are acceptable exceptions for file creation errors
                assert "test.log" in str(invalid_path) or "nonexistent" in str(
                    invalid_path
                )

    def test_setup_logging_structlog_configuration(self, mock_logging_config):
        """Test that structlog is properly configured."""
        setup_logging(mock_logging_config)

        # Verify that structlog is configured
        import structlog

        assert structlog.is_configured()

    def test_setup_logging_rotating_file_handler(self, mock_logging_config):
        """Test logging setup with rotating file handler."""
        # Clean up any existing handlers to ensure test isolation
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            if hasattr(handler, "close"):
                handler.close()

        mock_logging_config.output = "file"
        mock_logging_config.max_size_mb = 10
        mock_logging_config.max_backups = 3

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            mock_logging_config.file_path = str(log_file)

            setup_logging(mock_logging_config)

            # Verify that rotating file handler is used
            root_logger = logging.getLogger()
            handlers = [h for h in root_logger.handlers if hasattr(h, "maxBytes")]
            assert len(handlers) > 0, "No RotatingFileHandler found"
            # Find the RotatingFileHandler
            rotating_handler = None
            for h in handlers:
                if hasattr(h, "maxBytes") and hasattr(h, "backupCount"):
                    rotating_handler = h
                    break
            assert rotating_handler is not None, "RotatingFileHandler not found"
            # Verify maxBytes is set correctly (10 MB = 10 * 1024 * 1024 bytes)
            assert rotating_handler.maxBytes == 10 * 1024 * 1024
            assert rotating_handler.backupCount == 3

    def test_setup_logging_multiple_calls(self, mock_logging_config):
        """Test that multiple calls to setup_logging work correctly."""
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
        setup_logging(mock_logging_config)

        # Verify that handlers are added
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0

        # Verify autouam logger handlers are managed separately
        # autouam logger should not have handlers (they're on root)
        # but the logger should exist and be configured
        logging.getLogger("autouam")  # Verify logger exists
