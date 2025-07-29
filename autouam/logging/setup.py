"""Logging setup for AutoUAM."""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

import structlog
from structlog.stdlib import LoggerFactory

from ..config.settings import LoggingConfig


def setup_logging(config: LoggingConfig) -> None:
    """Setup structured logging based on configuration."""

    # Clear existing handlers to prevent duplication
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            _get_renderer(config.format),
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Set log level
    root_logger.setLevel(getattr(logging, config.level.upper()))

    # Configure appropriate handler based on output type
    if config.output == "file" and config.file_path:
        _setup_file_handler(config)
    elif config.output == "syslog":
        _setup_syslog_handler(config)
    else:
        # Default to stdout/stderr
        _setup_stream_handler(config)


def _get_renderer(format_type: str):
    """Get the appropriate renderer based on format type."""
    if format_type == "json":
        return structlog.processors.JSONRenderer()
    else:
        return structlog.dev.ConsoleRenderer(colors=True)


def _setup_stream_handler(config: LoggingConfig) -> None:
    """Setup stream-based logging (stdout/stderr)."""
    stream = sys.stderr if config.output == "stderr" else sys.stdout

    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)


def _setup_file_handler(config: LoggingConfig) -> None:
    """Setup file-based logging with rotation."""
    if not config.file_path:
        return

    log_file = Path(config.file_path)
    log_dir = log_file.parent

    # Create log directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create rotating file handler
    handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=config.max_size_mb * 1024 * 1024,  # Convert MB to bytes
        backupCount=config.max_backups,
        encoding="utf-8",
    )

    # Set formatter - use simple formatter since structlog handles the formatting
    formatter = logging.Formatter("%(message)s")

    handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)


def _setup_syslog_handler(config: LoggingConfig) -> None:
    """Setup syslog handler."""
    try:
        handler = logging.handlers.SysLogHandler(
            address="/dev/log",
            facility=logging.handlers.SysLogHandler.LOG_DAEMON,
        )

        # Set formatter - use simple formatter since structlog handles the formatting
        formatter = logging.Formatter("autouam: %(message)s")

        handler.setFormatter(formatter)

        # Add handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

    except Exception as e:
        # Fallback to stdout if syslog setup fails
        print(f"Failed to setup syslog handler: {e}", file=sys.stderr)
        print("Falling back to stdout", file=sys.stderr)


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def log_config(config: LoggingConfig) -> None:
    """Log the current logging configuration."""
    logger = get_logger(__name__)
    logger.info(
        "Logging configured",
        level=config.level,
        format=config.format,
        output=config.output,
        file_path=config.file_path if config.output == "file" else None,
    )
