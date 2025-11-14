"""Logging setup for AutoUAM."""

import logging
import sys
from pathlib import Path

from ..config.settings import LoggingConfig


def setup_logging(config: LoggingConfig) -> None:
    """Setup basic logging based on configuration."""
    # Clear existing handlers
    logger = logging.getLogger("autouam")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Set log level
    log_level = getattr(logging, config.level.upper())
    logger.setLevel(log_level)

    # Create formatter
    if config.format == "json":
        formatter = logging.Formatter('{"timestamp": "%(asctime)s", "level": '
                                       '"%(levelname)s", "message": "%(message)s"}')
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Create handler based on output
    if config.output == "file" and config.file_path:
        # Ensure directory exists
        Path(config.file_path).parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(config.file_path)
    else:
        handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(formatter)
    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(f"autouam.{name}")
