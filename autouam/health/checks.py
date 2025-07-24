"""Health check implementations for AutoUAM."""

import time
from typing import Any, Dict, Optional

from prometheus_client import Counter, Gauge, Histogram, generate_latest

from ..config.settings import Settings
from ..core.cloudflare import CloudflareClient
from ..core.monitor import LoadMonitor
from ..core.state import StateManager
from ..logging.setup import get_logger

# Prometheus metrics
LOAD_AVERAGE_GAUGE = Gauge("autouam_load_average", "Current system load average")
UAM_STATUS_GAUGE = Gauge(
    "autouam_uam_enabled", "UAM enabled status (1=enabled, 0=disabled)"
)
UAM_DURATION_GAUGE = Gauge(
    "autouam_uam_duration_seconds", "Current UAM duration in seconds"
)
CLOUDFLARE_API_REQUESTS = Counter(
    "autouam_cloudflare_api_requests_total", "Total Cloudflare API requests"
)
CLOUDFLARE_API_ERRORS = Counter(
    "autouam_cloudflare_api_errors_total", "Total Cloudflare API errors"
)
HEALTH_CHECK_DURATION = Histogram(
    "autouam_health_check_duration_seconds", "Health check duration"
)


class HealthChecker:
    """Health check implementation."""

    def __init__(self, config: Settings):
        """Initialize health checker."""
        self.config = config
        self.logger = get_logger(__name__)

        # Initialize components
        self.monitor = LoadMonitor()
        self.state_manager = StateManager()
        self.cloudflare_client: Optional[CloudflareClient] = None

        # Health state
        self._last_check = 0.0
        self._last_success = 0.0
        self._consecutive_failures = 0
        self._max_failures = 3

    async def initialize(self) -> bool:
        """Initialize health checker."""
        try:
            self.cloudflare_client = CloudflareClient(
                api_token=self.config.cloudflare.api_token,
                zone_id=self.config.cloudflare.zone_id,
                base_url=self.config.cloudflare.base_url
                or "https://api.cloudflare.com/client/v4",
            )

            # Test initial connection
            async with self.cloudflare_client as client:
                if not await client.test_connection():
                    self.logger.error(
                        "Failed to connect to Cloudflare API during health check "
                        "initialization"
                    )
                    return False

            self.logger.info("Health checker initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to initialize health checker", error=str(e))
            return False

    @HEALTH_CHECK_DURATION.time()
    async def check_health(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        start_time = time.time()
        self._last_check = start_time

        try:
            # Check system load
            load_info = await self._check_system_load()

            # Check UAM state
            uam_info = await self._check_uam_state()

            # Check Cloudflare API
            cloudflare_info = await self._check_cloudflare_api()

            # Determine overall health
            overall_health = self._determine_overall_health(
                load_info, uam_info, cloudflare_info
            )

            # Update metrics
            self._update_metrics(load_info, uam_info, cloudflare_info)

            # Update failure tracking
            if overall_health["healthy"]:
                self._last_success = start_time
                self._consecutive_failures = 0
            else:
                self._consecutive_failures += 1

            health_result = {
                "healthy": overall_health["healthy"],
                "status": overall_health["status"],
                "timestamp": start_time,
                "duration": time.time() - start_time,
                "checks": {
                    "system_load": load_info,
                    "uam_state": uam_info,
                    "cloudflare_api": cloudflare_info,
                },
                "summary": {
                    "last_success": self._last_success,
                    "consecutive_failures": self._consecutive_failures,
                    "max_failures": self._max_failures,
                },
            }

            self.logger.debug("Health check completed", result=health_result)
            return health_result

        except Exception as e:
            self.logger.error("Health check failed", error=str(e))
            self._consecutive_failures += 1

            return {
                "healthy": False,
                "status": "Health check error",
                "error": str(e),
                "timestamp": start_time,
                "duration": time.time() - start_time,
                "checks": {},
                "summary": {
                    "last_success": self._last_success,
                    "consecutive_failures": self._consecutive_failures,
                    "max_failures": self._max_failures,
                },
            }

    async def _check_system_load(self) -> Dict[str, Any]:
        """Check system load health."""
        try:
            system_info = self.monitor.get_system_info()

            if "error" in system_info:
                return {
                    "healthy": False,
                    "status": "System load check failed",
                    "error": system_info["error"],
                }

            # Check if load is reasonable (not too high for extended periods)
            load_avg = system_info["load_average"]["normalized"]
            cpu_count = system_info["cpu_count"]

            # Consider unhealthy if load is extremely high (> 100 per CPU)
            is_healthy = load_avg < (cpu_count * 100)

            return {
                "healthy": is_healthy,
                "status": (
                    "System load normal" if is_healthy else "System load extremely high"
                ),
                "load_average": load_avg,
                "cpu_count": cpu_count,
                "raw_load": system_info["load_average"],
                "processes": system_info["processes"],
            }

        except Exception as e:
            return {
                "healthy": False,
                "status": "System load check error",
                "error": str(e),
            }

    async def _check_uam_state(self) -> Dict[str, Any]:
        """Check UAM state health."""
        try:
            state_summary = self.state_manager.get_state_summary()

            # Check if state is reasonable
            is_healthy = True
            status = "UAM state normal"

            if state_summary["is_enabled"]:
                duration = state_summary["current_duration"]
                if duration and duration > 3600:  # More than 1 hour
                    is_healthy = False
                    status = "UAM enabled for extended period"

            return {
                "healthy": is_healthy,
                "status": status,
                "state": state_summary,
            }

        except Exception as e:
            return {
                "healthy": False,
                "status": "UAM state check error",
                "error": str(e),
            }

    async def _check_cloudflare_api(self) -> Dict[str, Any]:
        """Check Cloudflare API health."""
        if not self.cloudflare_client:
            return {
                "healthy": False,
                "status": "Cloudflare client not initialized",
            }

        try:
            CLOUDFLARE_API_REQUESTS.inc()

            async with self.cloudflare_client as client:
                # Test connection
                if not await client.test_connection():
                    CLOUDFLARE_API_ERRORS.inc()
                    return {
                        "healthy": False,
                        "status": "Cloudflare API connection failed",
                    }

                # Get current security level
                security_level = await client.get_current_security_level()

                return {
                    "healthy": True,
                    "status": "Cloudflare API healthy",
                    "security_level": security_level,
                }

        except Exception as e:
            CLOUDFLARE_API_ERRORS.inc()
            return {
                "healthy": False,
                "status": "Cloudflare API check error",
                "error": str(e),
            }

    def _determine_overall_health(
        self, load_info: Dict, uam_info: Dict, cloudflare_info: Dict
    ) -> Dict[str, Any]:
        """Determine overall health status."""
        checks = [load_info, uam_info, cloudflare_info]
        failed_checks = [check for check in checks if not check.get("healthy", True)]

        if failed_checks:
            failed_statuses = [
                check.get("status", "Unknown") for check in failed_checks
            ]
            status = f"Health check failed: {', '.join(failed_statuses)}"
            return {"healthy": False, "status": status}

        return {"healthy": True, "status": "All health checks passed"}

    def _update_metrics(
        self, load_info: Dict, uam_info: Dict, cloudflare_info: Dict
    ) -> None:
        """Update Prometheus metrics."""
        try:
            # Update load average metric
            if "load_average" in load_info:
                LOAD_AVERAGE_GAUGE.set(load_info["load_average"])

            # Update UAM status metric
            if "state" in uam_info:
                uam_enabled = uam_info["state"]["is_enabled"]
                UAM_STATUS_GAUGE.set(1 if uam_enabled else 0)

                # Update UAM duration metric
                duration = uam_info["state"]["current_duration"]
                if duration is not None:
                    UAM_DURATION_GAUGE.set(duration)
                else:
                    UAM_DURATION_GAUGE.set(0)

        except Exception as e:
            self.logger.warning("Failed to update metrics", error=str(e))

    def get_metrics(self) -> str:
        """Get Prometheus metrics."""
        try:
            return generate_latest().decode("utf-8")
        except Exception as e:
            self.logger.error("Failed to generate metrics", error=str(e))
            return ""

    def is_healthy(self) -> bool:
        """Quick health check based on recent results."""
        # Consider healthy if last success was within 5 minutes
        return (time.time() - self._last_success) < 300

    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary."""
        return {
            "healthy": self.is_healthy(),
            "last_check": self._last_check,
            "last_success": self._last_success,
            "consecutive_failures": self._consecutive_failures,
            "max_failures": self._max_failures,
        }
