"""UAM management logic for AutoUAM."""

import asyncio

from ..config.settings import Settings
from ..logging.setup import get_logger
from .cloudflare import CloudflareClient
from .monitor import LoadMonitor
from .state import StateManager


class UAMManager:
    """Main UAM management class."""

    def __init__(self, config: Settings):
        self.config = config
        self.logger = get_logger(__name__)
        self.monitor = LoadMonitor()
        self.state_manager = StateManager()
        self.cloudflare = CloudflareClient(
            api_token=config.cloudflare.api_token,
            zone_id=config.cloudflare.zone_id,
        )
        self._running = False

    async def initialize(self) -> bool:
        """Initialize and test Cloudflare connection."""
        try:
            return await self.cloudflare.test_connection()
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return False

    async def run(self) -> None:
        """Run the main monitoring loop."""
        if not await self.initialize():
            raise RuntimeError("Failed to initialize UAM manager")

        self._running = True
        self.logger.info("Starting UAM monitoring")

        try:
            while self._running:
                await self._monitoring_cycle()
                await asyncio.sleep(self.config.monitoring.check_interval)
        finally:
            self._running = False
            await self.cloudflare.close()
            self.logger.info("UAM monitoring stopped")

    async def _monitoring_cycle(self) -> None:
        """Execute one monitoring cycle."""
        try:
            # Update baseline if needed
            if self.monitor.baseline.should_update_baseline(
                self.config.monitoring.load_thresholds.baseline_update_interval
            ):
                self.monitor.baseline.calculate_baseline(
                    self.config.monitoring.load_thresholds.baseline_calculation_hours
                )

            load_average = self.monitor.get_normalized_load()
            current_state = self.state_manager.load_state()

            await self._evaluate_and_act(load_average, current_state)

        except Exception as e:
            self.logger.error(f"Monitoring cycle error: {e}")

    async def _evaluate_and_act(self, load_average: float, current_state) -> None:
        """Evaluate load and take appropriate action."""
        thresholds = self.config.monitoring.load_thresholds

        # Determine thresholds to use
        use_relative = (
            thresholds.use_relative_thresholds
            and self.monitor.baseline.get_baseline() is not None
        )

        if use_relative:
            upper_threshold = (
                self.monitor.baseline.get_baseline() or 0
            ) * thresholds.relative_upper_multiplier
            lower_threshold = (
                self.monitor.baseline.get_baseline() or 0
            ) * thresholds.relative_lower_multiplier
        else:
            upper_threshold = thresholds.upper
            lower_threshold = thresholds.lower

        # Check thresholds
        is_high_load = load_average > upper_threshold
        is_low_load = load_average < lower_threshold

        # Take action
        if is_high_load and not current_state.is_enabled:
            reason = "High load detected" + (" (relative)" if use_relative else "")
            await self._enable_uam(load_average, upper_threshold, reason)

        elif is_low_load and current_state.is_enabled:
            if self.state_manager.can_disable_uam(
                self.config.monitoring.minimum_uam_duration
            ):
                reason = "Load normalized" + (" (relative)" if use_relative else "")
                await self._disable_uam(load_average, lower_threshold, reason)

    async def _enable_uam(
        self, load_average: float, threshold: float, reason: str
    ) -> None:
        """Enable Under Attack Mode."""
        self.logger.warning(f"Enabling UAM: {reason} (load: {load_average:.2f})")

        await self.cloudflare.enable_under_attack_mode()
        self.state_manager.update_state(
            is_enabled=True,
            load_average=load_average,
            threshold_used=threshold,
            reason=reason,
        )

    async def _disable_uam(
        self, load_average: float, threshold: float, reason: str
    ) -> None:
        """Disable Under Attack Mode."""
        self.logger.info(f"Disabling UAM: {reason} (load: {load_average:.2f})")

        await self.cloudflare.disable_under_attack_mode(
            self.config.security.regular_mode
        )
        self.state_manager.update_state(
            is_enabled=False,
            load_average=load_average,
            threshold_used=threshold,
            reason=reason,
        )

    async def enable_uam_manual(self) -> bool:
        """Manually enable Under Attack Mode."""
        try:
            await self.cloudflare.enable_under_attack_mode()
            self.state_manager.update_state(
                is_enabled=True,
                load_average=0.0,
                threshold_used=0.0,
                reason="Manual enable",
            )
            return True
        except Exception as e:
            self.logger.error(f"Manual enable failed: {e}")
            return False

    async def disable_uam_manual(self) -> bool:
        """Manually disable Under Attack Mode."""
        try:
            await self.cloudflare.disable_under_attack_mode(
                self.config.security.regular_mode
            )
            self.state_manager.update_state(
                is_enabled=False,
                load_average=0.0,
                threshold_used=0.0,
                reason="Manual disable",
            )
            return True
        except Exception as e:
            self.logger.error(f"Manual disable failed: {e}")
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
            return {"error": str(e)}

    def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False

    async def check_once(self) -> dict:
        """Perform a single check."""
        if not await self.initialize():
            return {"error": "Failed to initialize"}

        try:
            load_average = self.monitor.get_normalized_load()
            current_state = self.state_manager.load_state()
            await self._evaluate_and_act(load_average, current_state)
            return self.get_status()
        except Exception as e:
            return {"error": str(e)}
