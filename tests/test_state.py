"""Tests for state persistence behavior."""

import io
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from autouam.core.state import StateManager


def test_env_var_selects_state_file():
    with tempfile.TemporaryDirectory() as tmp:
        env_path = os.path.join(tmp, "env", "state.json")
        manager = StateManager()
        with patch.dict(os.environ, {"AUTOUAM_STATE_FILE": env_path}):
            from autouam.core.state import StateManager as SM

            manager = SM()
        assert manager.state_file == env_path


def test_explicit_argument_beats_env_var():
    with tempfile.TemporaryDirectory() as tmp:
        explicit = os.path.join(tmp, "explicit.json")
        with patch.dict(os.environ, {"AUTOUAM_STATE_FILE": "/tmp/other.json"}):
            manager = StateManager(state_file=explicit)
        assert manager.state_file == explicit


def test_save_failure_logs_and_does_not_raise():
    root = logging.getLogger("autouam")
    capture = io.StringIO()
    handler = logging.StreamHandler(capture)
    handler.setLevel(logging.DEBUG)
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        manager = StateManager(state_file="/proc/nonexistent/state.json")
        state = manager.update_state(
            is_enabled=True,
            load_average=5.0,
            threshold_used=2.0,
            reason="High load detected",
        )
        assert state.is_enabled is True  # memory still works
        assert "Failed to persist" in capture.getvalue()
    finally:
        root.removeHandler(handler)


def test_external_modification_is_visible_on_next_load():
    with tempfile.TemporaryDirectory() as tmp:
        state_file = os.path.join(tmp, "state.json")
        manager = StateManager(state_file=state_file)

        manager.update_state(
            is_enabled=True, load_average=5.0, threshold_used=2.0, reason="attack"
        )
        assert manager.get_state_summary()["is_enabled"] is True

        # Simulate an out-of-band change (operator/second process) on disk.
        external = {
            "is_enabled": False,
            "last_check": time.time(),
            "load_average": 0.0,
            "threshold_used": 0.0,
            "reason": "operator disabled out-of-band",
            "enabled_at": None,
            "disabled_at": 123.0,
        }
        Path(state_file).write_text(json.dumps(external))

        summary = manager.get_state_summary()
        assert summary["is_enabled"] is False
        assert summary["current_duration"] is None


def test_missing_file_not_stale_cached():
    """Deleting the state file must not leave phantom cached state forever."""
    with tempfile.TemporaryDirectory() as tmp:
        state_file = os.path.join(tmp, "state.json")
        manager = StateManager(state_file=state_file)
        manager.update_state(
            is_enabled=True, load_average=5.0, threshold_used=2.0, reason="attack"
        )
        os.unlink(state_file)
        # File gone: next load falls back to initial state instead of the
        # stale enabled cache.
        assert manager.load_state().is_enabled is False


def test_roundtrip_preserves_fields():
    with tempfile.TemporaryDirectory() as tmp:
        state_file = os.path.join(tmp, "state.json")
        manager = StateManager(state_file=state_file)
        manager.update_state(
            is_enabled=True, load_average=3.5, threshold_used=2.0, reason="spike"
        )
        reloaded = StateManager(state_file=state_file).load_state()
        assert reloaded.is_enabled is True
        assert reloaded.load_average == 3.5
        assert reloaded.reason == "spike"
