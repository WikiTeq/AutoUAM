"""State management for AutoUAM."""

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..logging.setup import get_logger


@dataclass
class UAMState:
    """UAM state information."""

    is_enabled: bool
    last_check: float
    load_average: float
    threshold_used: float
    reason: str
    enabled_at: float | None = None
    disabled_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class StateManager:
    """Manage UAM state persistence."""

    def __init__(self, state_file: str | None = None):
        # Explicit argument wins, then AUTOUAM_STATE_FILE (restores support
        # regressed in PR #6, commit 1b53805 originally added it), then the
        # historical default.
        self.state_file = (
            state_file
            or os.environ.get("AUTOUAM_STATE_FILE")
            or "/var/lib/autouam/state.json"
        )
        self._state: UAMState | None = None
        self._file_signature: tuple[float, int] | None = None
        self.logger = get_logger(__name__)

    def get_initial_state(self) -> UAMState:
        """Get initial state."""
        return UAMState(
            is_enabled=False,
            enabled_at=None,
            disabled_at=None,
            last_check=time.time(),
            load_average=0.0,
            threshold_used=0.0,
            reason="Initial state",
        )

    def _current_file_signature(self) -> tuple[float, int] | None:
        """Stat the state file, returning (mtime_ns, size) or None."""
        try:
            stat = Path(self.state_file).stat()
        except OSError:
            return None
        return (stat.st_mtime_ns, stat.st_size)

    def load_state(self) -> UAMState:
        """Load state from file, re-reading when the file changed on disk.

        The cache is invalidated whenever the file's mtime/size signature
        differs from the last read, so out-of-band modifications (another
        process, an operator, a second daemon) are picked up instead of
        being shadowed by stale in-memory state forever.
        """
        signature = self._current_file_signature()
        if self._state is not None and signature == self._file_signature:
            return self._state

        state_path = Path(self.state_file)
        if state_path.exists():
            try:
                with open(state_path) as f:
                    data = json.load(f)
                self._state = UAMState(**data)
                self._file_signature = signature
            except Exception:
                self.logger.warning(
                    f"Failed to load state file {state_path}; " "using initial state",
                    exc_info=True,
                )
                self._state = self.get_initial_state()
                self._file_signature = signature
        else:
            # Missing file is not cached against a signature so that a file
            # appearing later is still picked up.
            self._state = self.get_initial_state()

        return self._state

    def save_state(self, state: UAMState) -> None:
        """Save state to file, logging (not raising) on failure."""
        self._state = state
        try:
            state_path = Path(self.state_file)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(state_path, "w") as f:
                json.dump(state.to_dict(), f, indent=2)
            self._file_signature = self._current_file_signature()
        except Exception:
            # Persistence is best-effort, but it must never be silent:
            # a lost write means the daemon restarts with wrong beliefs
            # about whether UAM is enabled.
            self._file_signature = None
            self.logger.error(
                f"Failed to persist state to {self.state_file}; running "
                "with memory-only state until this is fixed",
                exc_info=True,
            )

    def update_state(
        self, is_enabled: bool, load_average: float, threshold_used: float, reason: str
    ) -> UAMState:
        """Update state with new information."""
        current_time = time.time()
        state = self.load_state()

        was_enabled = state.is_enabled
        state.is_enabled = is_enabled
        state.last_check = current_time
        state.load_average = load_average
        state.threshold_used = threshold_used
        state.reason = reason

        # Update timestamps
        if is_enabled and not was_enabled:
            state.enabled_at = current_time
            state.disabled_at = None
        elif not is_enabled and was_enabled:
            state.disabled_at = current_time

        self.save_state(state)
        return state

    def get_uam_duration(self) -> float | None:
        """Get current UAM duration in seconds."""
        state = self.load_state()
        if not state.is_enabled or state.enabled_at is None:
            return None
        return time.time() - state.enabled_at

    def can_disable_uam(self, minimum_duration: int) -> bool:
        """Check if UAM can be disabled based on minimum duration."""
        duration = self.get_uam_duration()
        return duration is None or duration >= minimum_duration

    def get_state_summary(self) -> dict[str, Any]:
        """Get a summary of current state."""
        state = self.load_state()
        duration = self.get_uam_duration()

        return {
            "is_enabled": state.is_enabled,
            "enabled_at": state.enabled_at,
            "disabled_at": state.disabled_at,
            "current_duration": duration,
            "last_check": state.last_check,
            "load_average": state.load_average,
            "threshold_used": state.threshold_used,
            "reason": state.reason,
        }
