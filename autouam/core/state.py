"""State management for AutoUAM."""

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from ..logging.setup import get_logger


@dataclass
class UAMState:
    """UAM state information."""

    is_enabled: bool
    last_check: float
    load_average: float
    threshold_used: float
    reason: str
    enabled_at: Optional[float] = None
    disabled_at: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UAMState":
        """Create from dictionary."""
        return cls(**data)


class StateManager:
    """Manage UAM state and persistence."""

    def __init__(self, state_file: Optional[str] = None):
        """Initialize state manager."""
        self.logger = get_logger(__name__)
        # Check for environment variable first, then parameter, then default
        self.state_file = (
            state_file
            or os.environ.get("AUTOUAM_STATE_FILE")
            or "/var/lib/autouam/state.json"
        )
        self._state: Optional[UAMState] = None
        self._ensure_state_directory()

    def _ensure_state_directory(self) -> None:
        """Ensure state directory exists."""
        state_path = Path(self.state_file)
        state_dir = state_path.parent

        if not state_dir.exists():
            try:
                state_dir.mkdir(parents=True, exist_ok=True)
                self.logger.debug("Created state directory", path=str(state_dir))
            except PermissionError as e:
                self.logger.warning(
                    "Cannot create state directory, using memory-only state",
                    path=str(state_dir),
                    error=str(e),
                )

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

    def load_state(self) -> UAMState:
        """Load state from file or create initial state."""
        if self._state is not None:
            return self._state

        state_path = Path(self.state_file)

        if state_path.exists():
            try:
                with open(state_path, "r") as f:
                    data = json.load(f)

                # Validate the loaded data
                if not isinstance(data, dict):
                    raise ValueError("State file contains invalid data format")

                self._state = UAMState.from_dict(data)
                self.logger.debug("State loaded from file", state_file=self.state_file)

            except (IOError, PermissionError) as e:
                self.logger.warning(
                    "Failed to read state file due to I/O error, using initial state",
                    error=str(e),
                    state_file=self.state_file,
                )
                self._state = self.get_initial_state()
            except json.JSONDecodeError as e:
                self.logger.warning(
                    "Failed to parse state file (corrupted), using initial state",
                    error=str(e),
                    state_file=self.state_file,
                )
                # Try to backup corrupted file
                try:
                    backup_path = state_path.with_suffix(".corrupted")
                    state_path.rename(backup_path)
                    self.logger.info(
                        "Corrupted state file backed up", backup_file=str(backup_path)
                    )
                except OSError:
                    pass
                self._state = self.get_initial_state()
            except (ValueError, TypeError) as e:
                self.logger.warning(
                    "State file contains invalid data, using initial state",
                    error=str(e),
                    state_file=self.state_file,
                )
                self._state = self.get_initial_state()
        else:
            self._state = self.get_initial_state()
            self.logger.debug("No state file found, using initial state")

        return self._state

    def save_state(self, state: UAMState) -> None:
        """Save state to file."""
        self._state = state

        try:
            state_path = Path(self.state_file)

            # Ensure directory exists
            try:
                state_path.parent.mkdir(parents=True, exist_ok=True)
            except PermissionError as e:
                self.logger.error(
                    "Permission denied creating state directory",
                    error=str(e),
                    directory=str(state_path.parent),
                )
                raise

            # Create a temporary file first to avoid corruption
            temp_path = state_path.with_suffix(".tmp")
            try:
                with open(temp_path, "w") as f:
                    json.dump(state.to_dict(), f, indent=2)

                # Atomic move to final location
                temp_path.replace(state_path)

                self.logger.debug("State saved to file", state_file=self.state_file)

            except (IOError, PermissionError):
                # Clean up temp file if it exists
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
                raise

        except (IOError, PermissionError) as e:
            self.logger.warning(
                "Failed to save state file",
                error=str(e),
                state_file=self.state_file,
            )
            # Don't raise - allow operation to continue with in-memory state

    def update_state(
        self,
        is_enabled: bool,
        load_average: float,
        threshold_used: float,
        reason: str,
    ) -> UAMState:
        """Update state with new information."""
        current_time = time.time()
        state = self.load_state()

        # Store previous state for transition detection
        was_enabled = state.is_enabled

        # Update state
        state.is_enabled = is_enabled
        state.last_check = current_time
        state.load_average = load_average
        state.threshold_used = threshold_used
        state.reason = reason

        # Update timestamps
        if is_enabled and not was_enabled:
            # UAM was just enabled
            state.enabled_at = current_time
            state.disabled_at = None
        elif not is_enabled and was_enabled:
            # UAM was just disabled
            state.disabled_at = current_time

        self.save_state(state)

        self.logger.info(
            "State updated",
            is_enabled=is_enabled,
            load_average=load_average,
            threshold_used=threshold_used,
            reason=reason,
        )

        return state

    def get_uam_duration(self) -> Optional[float]:
        """Get current UAM duration in seconds."""
        state = self.load_state()

        if not state.is_enabled or state.enabled_at is None:
            return None

        return time.time() - state.enabled_at

    def can_disable_uam(self, minimum_duration: int) -> bool:
        """Check if UAM can be disabled based on minimum duration."""
        duration = self.get_uam_duration()

        if duration is None:
            return True

        can_disable = duration >= minimum_duration

        self.logger.debug(
            "UAM duration check",
            current_duration=duration,
            minimum_duration=minimum_duration,
            can_disable=can_disable,
        )

        return can_disable

    def get_state_summary(self) -> dict:
        """Get a summary of current state."""
        # Force reload from file to get the latest state
        self._state = None
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

    def clear_state(self) -> None:
        """Clear state and reset to initial state."""
        self._state = self.get_initial_state()
        self.save_state(self._state)
        self.logger.info("State cleared and reset to initial state")

    def get_state_file_path(self) -> str:
        """Get the state file path."""
        return self.state_file
