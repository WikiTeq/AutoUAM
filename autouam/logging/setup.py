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

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=_get_output_stream(config),
        level=getattr(logging, config.level.upper()),
    )

    # Configure file handler if needed
    if config.output == "file" and config.file_path:
        _setup_file_handler(config)

    # Configure syslog handler if needed
    elif config.output == "syslog":
        _setup_syslog_handler(config)


def _get_renderer(format_type: str):
    """Get the appropriate renderer based on format type."""
    if format_type == "json":
        return structlog.processors.JSONRenderer()
    else:
        return structlog.dev.ConsoleRenderer(colors=True)


def _get_output_stream(config: LoggingConfig):
    """Get the appropriate output stream."""
    if config.output == "stdout":
        return sys.stdout
    elif config.output == "stderr":
        return sys.stderr
    else:
        return sys.stdout


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

    # Set formatter
    if config.format == "json":
        formatter = logging.Formatter("%(message)s")
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

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

        # Set formatter
        if config.format == "json":
            formatter = logging.Formatter("%(message)s")
        else:
            formatter = logging.Formatter(
                "autouam: %(name)s - %(levelname)s - %(message)s"
            )

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
