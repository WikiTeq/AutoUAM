"""HTTP health server for AutoUAM."""

import json

from aiohttp import web

from ..config.settings import Settings
from ..logging.setup import get_logger
from .checks import HealthChecker


class HealthServer:
    """Simple HTTP server for health checks."""

    def __init__(self, config: Settings, health_checker: HealthChecker):
        self.config = config
        self.health_checker = health_checker
        self.logger = get_logger(__name__)
        self.app = web.Application()
        self.runner = None
        self.site = None

        # Setup routes
        self.app.router.add_get(self.config.health.endpoint, self._health_handler)
        self.app.router.add_get(
            self.config.health.metrics_endpoint, self._metrics_handler
        )

    async def _health_handler(self, request: web.Request) -> web.Response:
        """Handle health check requests."""
        health_result = await self.health_checker.check_health()
        status_code = 200 if health_result["healthy"] else 503

        return web.Response(
            text=json.dumps(health_result, indent=2),
            status=status_code,
            content_type="application/json",
        )

    async def _metrics_handler(self, request: web.Request) -> web.Response:
        """Handle metrics requests."""
        metrics_data = self.health_checker.get_metrics()
        return web.Response(text=metrics_data, content_type="text/plain")

    async def start(self) -> None:
        """Start the health server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "localhost", self.config.health.port)
        await self.site.start()
        self.logger.info(f"Health server started on port {self.config.health.port}")

    async def stop(self) -> None:
        """Stop the health server."""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        self.logger.info("Health server stopped")
