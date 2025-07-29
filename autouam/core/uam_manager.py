"""UAM management logic for AutoUAM."""

import asyncio
from typing import Optional

import aiohttp

from ..config.settings import Settings
from ..logging.setup import get_logger
from .cloudflare import CloudflareClient, CloudflareError
from .monitor import LoadMonitor
from .state import StateManager, UAMState


class UAMManagerError(Exception):
    """Base exception for UAM manager errors."""

    pass


class UAMManagerInitializationError(UAMManagerError):
    """Raised when UAM manager fails to initialize."""

    pass


class UAMManagerOperationError(UAMManagerError):
    """Raised when UAM manager operation fails."""

    pass


class UAMManager:
    """Main UAM management class."""

    def __init__(self, config: Settings):
        """Initialize UAM manager."""
        self.config = config
        self.logger = get_logger(__name__)

        # Initialize components
        self.monitor = LoadMonitor()
        self.state_manager = StateManager()
        self.cloudflare_client: Optional[CloudflareClient] = None

        # Control flags
        self._running = False
        self._stop_event = asyncio.Event()

    async def initialize(self) -> bool:
        """Initialize the UAM manager."""
        try:
            # Initialize Cloudflare client
            self.cloudflare_client = CloudflareClient(
                api_token=self.config.cloudflare.api_token,
                zone_id=self.config.cloudflare.zone_id,
                base_url=self.config.cloudflare.base_url
                or "https://api.cloudflare.com/client/v4",
            )

            # Test Cloudflare connection
            async with self.cloudflare_client as client:
                if not await client.test_connection():
                    self.logger.error("Failed to connect to Cloudflare API")
                    return False

            self.logger.info("UAM manager initialized successfully")
            return True

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.logger.error("Network error during initialization", error=str(e))
            return False
        except (ValueError, TypeError) as e:
            self.logger.error("Configuration error during initialization", error=str(e))
            return False
        except Exception as e:
            self.logger.error("Unexpected error during initialization", error=str(e))
            return False

    async def _sync_state_with_cloudflare(self) -> None:
        """Sync internal state with actual Cloudflare state."""
        if not self.cloudflare_client:
            self.logger.error("Cloudflare client not initialized")
            return

        try:
            # Get current Cloudflare security level
            async with self.cloudflare_client as client:
                current_security_level = await client.get_current_security_level()

            # Get current internal state
            current_state = self.state_manager.load_state()

            # Check if there's a mismatch
            cloudflare_uam_active = current_security_level == "under_attack"

            if cloudflare_uam_active != current_state.is_enabled:
                self.logger.warning(
                    "State mismatch detected, syncing with Cloudflare",
                    cloudflare_state=current_security_level,
                    internal_state_enabled=current_state.is_enabled,
                )

                # Update internal state to match Cloudflare
                if cloudflare_uam_active:
                    # UAM is active on Cloudflare but not in our state
                    self.state_manager.update_state(
                        is_enabled=True,
                        load_average=current_state.load_average,
                        threshold_used=self.config.monitoring.load_thresholds.upper,
                        reason="UAM was already active when AutoUAM started",
                    )
                    self.logger.info("Synced state: UAM is active on Cloudflare")
                else:
                    # UAM is not active on Cloudflare but is in our state
                    self.state_manager.update_state(
                        is_enabled=False,
                        load_average=current_state.load_average,
                        threshold_used=self.config.monitoring.load_thresholds.lower,
                        reason="UAM is not active on Cloudflare",
                    )
                    self.logger.info("Synced state: UAM is not active on Cloudflare")
            else:
                self.logger.info(
                    "State is in sync with Cloudflare",
                    uam_active=cloudflare_uam_active,
                )

        except Exception as e:
            self.logger.error(
                "Failed to sync state with Cloudflare",
                error=str(e),
            )

    async def run(self) -> None:
        """Run the main monitoring loop."""
        if not await self.initialize():
            raise RuntimeError("Failed to initialize UAM manager")

        # Sync state with actual Cloudflare state on startup
        await self._sync_state_with_cloudflare()

        self._running = True
        self.logger.info("Starting UAM monitoring loop")

        try:
            while self._running and not self._stop_event.is_set():
                await self._monitoring_cycle()
                await asyncio.sleep(self.config.monitoring.check_interval)

        except asyncio.CancelledError:
            self.logger.info("UAM monitoring loop cancelled")
        except Exception as e:
            self.logger.error("UAM monitoring loop error", error=str(e))
            # Attempt to restart the monitoring loop after a delay
            await asyncio.sleep(30)  # Wait 30 seconds before restarting
            if self._running and not self._stop_event.is_set():
                self.logger.info("Attempting to restart monitoring loop")
                await self.run()  # Recursive restart
        finally:
            self._running = False
            self.logger.info("UAM monitoring loop stopped")

    async def _monitoring_cycle(self) -> None:
        """Execute one monitoring cycle."""
        try:
            # Get current load average (run in thread pool to avoid blocking)
            load_average = await asyncio.to_thread(self.monitor.get_normalized_load)

            # Update baseline if needed (run in thread pool)
            if self.monitor.baseline.should_update_baseline(
                self.config.monitoring.load_thresholds.baseline_update_interval
            ):
                await asyncio.to_thread(
                    self.monitor.update_baseline,
                    self.config.monitoring.load_thresholds.baseline_calculation_hours,
                )

            # Get current state (run in thread pool)
            current_state = await asyncio.to_thread(self.state_manager.load_state)

            # Determine action based on load and current state
            await self._evaluate_and_act(load_average, current_state)

        except (OSError, IOError) as e:
            self.logger.error("System I/O error in monitoring cycle", error=str(e))
            # Continue monitoring despite I/O errors
        except (ValueError, TypeError) as e:
            self.logger.error("Data validation error in monitoring cycle", error=str(e))
            # Continue monitoring despite data errors
        except Exception as e:
            self.logger.error("Unexpected error in monitoring cycle", error=str(e))
            # Continue monitoring despite unexpected errors

    async def _evaluate_and_act(
        self, load_average: float, current_state: "UAMState"
    ) -> None:
        """Evaluate load and take appropriate action."""
        thresholds = self.config.monitoring.load_thresholds
        minimum_duration = self.config.monitoring.minimum_uam_duration

        # Use relative thresholds if enabled and baseline is available
        use_relative = (
            thresholds.use_relative_thresholds
            and self.monitor.baseline.get_baseline() is not None
        )

        if use_relative:
            # Use relative thresholds
            is_high_load = self.monitor.is_high_load(
                threshold=thresholds.upper,  # Not used when relative=True
                use_relative=True,
                relative_multiplier=thresholds.relative_upper_multiplier,
            )
            is_low_load = self.monitor.is_low_load(
                threshold=thresholds.lower,  # Not used when relative=True
                use_relative=True,
                relative_multiplier=thresholds.relative_lower_multiplier,
            )

            # Get the actual threshold values for logging
            baseline = self.monitor.baseline.get_baseline()
            if baseline is not None:
                upper_threshold = baseline * thresholds.relative_upper_multiplier
                lower_threshold = baseline * thresholds.relative_lower_multiplier
            else:
                # Fallback to absolute thresholds if no baseline
                upper_threshold = thresholds.upper
                lower_threshold = thresholds.lower

            self.logger.debug(
                "Using relative thresholds",
                baseline=baseline,
                upper_threshold=upper_threshold,
                lower_threshold=lower_threshold,
                load_average=load_average,
            )
        else:
            # Use absolute thresholds
            is_high_load = self.monitor.is_high_load(thresholds.upper)
            is_low_load = self.monitor.is_low_load(thresholds.lower)
            upper_threshold = thresholds.upper
            lower_threshold = thresholds.lower

            self.logger.debug(
                "Using absolute thresholds",
                upper_threshold=upper_threshold,
                lower_threshold=lower_threshold,
                load_average=load_average,
            )

        # Check if UAM should be enabled
        if is_high_load and not current_state.is_enabled:
            reason = (
                "High load detected (relative)"
                if use_relative
                else "High load detected"
            )
            await self._enable_uam(load_average, upper_threshold, reason)

        # Check if UAM should be disabled
        elif is_low_load and current_state.is_enabled:
            if self.state_manager.can_disable_uam(minimum_duration):
                reason = (
                    "Load normalized (relative)" if use_relative else "Load normalized"
                )
                await self._disable_uam(load_average, lower_threshold, reason)
            else:
                duration = self.state_manager.get_uam_duration()
                remaining = minimum_duration - (duration or 0)
                self.logger.info(
                    "UAM cannot be disabled yet",
                    current_duration=duration,
                    minimum_duration=minimum_duration,
                    remaining_seconds=remaining,
                    load_average=load_average,
                )

        # Update state if no action was taken
        else:
            reason = "No action needed"
            if current_state.is_enabled:
                reason = "UAM active, load within acceptable range"
            else:
                reason = "Load within normal range"

            self.state_manager.update_state(
                is_enabled=current_state.is_enabled,
                load_average=load_average,
                threshold_used=(
                    upper_threshold if current_state.is_enabled else lower_threshold
                ),
                reason=reason,
            )

    async def _enable_uam(
        self, load_average: float, threshold: float, reason: str
    ) -> None:
        """Enable Under Attack Mode."""
        if not self.cloudflare_client:
            self.logger.error("Cloudflare client not initialized")
            return

        try:
            self.logger.warning(
                "Enabling Under Attack Mode",
                load_average=load_average,
                threshold=threshold,
                reason=reason,
            )

            async with self.cloudflare_client as client:
                await client.enable_under_attack_mode()

            # Update state
            self.state_manager.update_state(
                is_enabled=True,
                load_average=load_average,
                threshold_used=threshold,
                reason=reason,
            )

            self.logger.info("Under Attack Mode enabled successfully")

        except CloudflareError as e:
            self.logger.error("Failed to enable Under Attack Mode", error=str(e))
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.logger.error("Network error enabling Under Attack Mode", error=str(e))
        except Exception as e:
            self.logger.error(
                "Unexpected error enabling Under Attack Mode", error=str(e)
            )

    async def _disable_uam(
        self, load_average: float, threshold: float, reason: str
    ) -> None:
        """Disable Under Attack Mode."""
        if not self.cloudflare_client:
            self.logger.error("Cloudflare client not initialized")
            return

        try:
            self.logger.info(
                "Disabling Under Attack Mode",
                load_average=load_average,
                threshold=threshold,
                reason=reason,
            )

            async with self.cloudflare_client as client:
                await client.disable_under_attack_mode(
                    regular_mode=self.config.security.regular_mode
                )

            # Update state
            self.state_manager.update_state(
                is_enabled=False,
                load_average=load_average,
                threshold_used=threshold,
                reason=reason,
            )

            self.logger.info("Under Attack Mode disabled successfully")

        except CloudflareError as e:
            self.logger.error("Failed to disable Under Attack Mode", error=str(e))
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.logger.error("Network error disabling Under Attack Mode", error=str(e))
        except Exception as e:
            self.logger.error(
                "Unexpected error disabling Under Attack Mode", error=str(e)
            )

    async def enable_uam_manual(self) -> bool:
        """Manually enable Under Attack Mode."""
        if not self.cloudflare_client:
            self.logger.error("Cloudflare client not initialized")
            return False

        try:
            self.logger.info("Manually enabling Under Attack Mode")

            async with self.cloudflare_client as client:
                await client.enable_under_attack_mode()

            # Update state
            self.state_manager.update_state(
                is_enabled=True,
                load_average=0.0,  # Not relevant for manual action
                threshold_used=0.0,
                reason="Manual enable",
            )

            self.logger.info("Under Attack Mode manually enabled")
            return True

        except Exception as e:
            self.logger.error(
                "Failed to manually enable Under Attack Mode", error=str(e)
            )
            return False

    async def disable_uam_manual(self) -> bool:
        """Manually disable Under Attack Mode."""
        if not self.cloudflare_client:
            self.logger.error("Cloudflare client not initialized")
            return False

        try:
            self.logger.info("Manually disabling Under Attack Mode")

            async with self.cloudflare_client as client:
                await client.disable_under_attack_mode(
                    regular_mode=self.config.security.regular_mode
                )

            # Update state
            self.state_manager.update_state(
                is_enabled=False,
                load_average=0.0,  # Not relevant for manual action
                threshold_used=0.0,
                reason="Manual disable",
            )

            self.logger.info("Under Attack Mode manually disabled")
            return True

        except Exception as e:
            self.logger.error(
                "Failed to manually disable Under Attack Mode", error=str(e)
            )
            return False

    def get_status(self) -> dict:
        """Get current status information."""
        try:
            system_info = self.monitor.get_system_info()
            state_summary = self.state_manager.get_state_summary()

            return {
                "system": system_info,
                "state": state_summary,
                "config": {
                    "upper_threshold": self.config.monitoring.load_thresholds.upper,
                    "lower_threshold": self.config.monitoring.load_thresholds.lower,
                    "check_interval": self.config.monitoring.check_interval,
                    "minimum_duration": self.config.monitoring.minimum_uam_duration,
                },
                "running": self._running,
            }

        except Exception as e:
            self.logger.error("Failed to get status", error=str(e))
            return {"error": str(e)}

    def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        self._stop_event.set()
        self.logger.info("UAM manager stop requested")

    async def _handle_graceful_degradation(self, error: Exception) -> None:
        """Handle graceful degradation when errors occur."""
        self.logger.warning(
            "Entering graceful degradation mode",
            error_type=type(error).__name__,
            error=str(error),
        )

        # Continue monitoring but with reduced functionality
        # State management and logging still work
        try:
            # Get current state without Cloudflare operations
            current_state = self.state_manager.load_state()
            self.logger.info(
                "Continuing in degraded mode",
                current_state_enabled=current_state.is_enabled,
            )
        except Exception as e:
            self.logger.error("Failed to get state in degraded mode", error=str(e))

    async def check_once(self) -> dict:
        """Perform a single check without starting the monitoring loop."""
        if not await self.initialize():
            return {"error": "Failed to initialize"}

        try:
            load_average = self.monitor.get_normalized_load()
            current_state = self.state_manager.load_state()

            await self._evaluate_and_act(load_average, current_state)

            return self.get_status()

        except Exception as e:
            self.logger.error("Error in single check", error=str(e))
            return {"error": str(e)}
