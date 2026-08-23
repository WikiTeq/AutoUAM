"""Logging setup for AutoUAM."""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..config.settings import LoggingConfig


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line.

    Uses json.dumps so message content is always escaped correctly; the
    previous %-template approach emitted unparseable lines whenever a
    message contained a quote or backslash.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


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
        formatter = JsonFormatter()
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
