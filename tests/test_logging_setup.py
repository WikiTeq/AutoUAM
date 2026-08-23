"""Tests for logging setup."""

import io
import json
import logging
from contextlib import redirect_stdout

from autouam.config.settings import LoggingConfig
from autouam.logging.setup import setup_logging


def _capture_logs(format_name: str, messages: list[str]) -> str:
    capture = io.StringIO()
    config = LoggingConfig(level="INFO", output="stdout", format=format_name)
    root = logging.getLogger("autouam")
    try:
        with redirect_stdout(capture):
            setup_logging(config)
            log = logging.getLogger("autouam.test")
            for message in messages:
                log.info(message)
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
    return capture.getvalue()


def test_json_format_emits_parseable_lines_with_quotes_and_backslashes():
    tricky = 'Failed to load "/var/lib/autouam/state.json": bad \\ escape'
    out = _capture_logs("json", [tricky, "Baseline calculated: 1.95 from 1440 samples"])
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["message"] == tricky
    assert parsed[1]["message"] == "Baseline calculated: 1.95 from 1440 samples"
    assert parsed[0]["level"] == "INFO"
    # ISO-8601 machine timestamp
    assert "T" in parsed[0]["timestamp"]


def test_text_format_unchanged():
    out = _capture_logs("text", ["plain text line"])
    assert "plain text line" in out
