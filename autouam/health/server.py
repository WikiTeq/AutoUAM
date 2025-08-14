"""HTTP health server for AutoUAM."""

import asyncio
from typing import Optional

from aiohttp import web

from ..config.settings import Settings
from ..logging.setup import get_logger
from .checks import HealthChecker


class HealthServer:
    """HTTP server for health checks and metrics."""

    def __init__(self, config: Settings, health_checker: HealthChecker):
        """Initialize health server."""
        self.config = config
        self.health_checker = health_checker
        self.logger = get_logger(__name__)
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

        # Setup routes
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Setup HTTP routes."""
        self.app.router.add_get(self.config.health.endpoint, self._health_handler)
        self.app.router.add_get(
            self.config.health.metrics_endpoint, self._metrics_handler
        )
        self.app.router.add_get("/", self._root_handler)
        self.app.router.add_get("/ready", self._ready_handler)
        self.app.router.add_get("/live", self._live_handler)

    async def _health_handler(self, request: web.Request) -> web.Response:
        """Handle health check requests."""
        try:
            health_result = await self.health_checker.check_health()

            status_code = 200 if health_result["healthy"] else 503
            content_type = "application/json"

            response_data = {
                "status": "healthy" if health_result["healthy"] else "unhealthy",
                "timestamp": health_result["timestamp"],
                "duration": health_result["duration"],
                "checks": health_result["checks"],
                "summary": health_result["summary"],
            }

            if "error" in health_result:
                response_data["error"] = health_result["error"]

            self.logger.debug(
                "Health check request",
                status_code=status_code,
                healthy=health_result["healthy"],
            )

            return web.json_response(
                response_data,
                status=status_code,
                content_type=content_type,
            )

        except Exception as e:
            self.logger.error("Health check handler error", error=str(e))
            return web.json_response(
                {
                    "status": "error",
                    "error": str(e),
                    "timestamp": asyncio.get_event_loop().time(),
                },
                status=500,
                content_type="application/json",
            )

    async def _metrics_handler(self, request: web.Request) -> web.Response:
        """Handle metrics requests."""
        try:
            metrics = self.health_checker.get_metrics()

            self.logger.debug("Metrics request served")

            return web.Response(
                text=metrics,
                content_type="text/plain; version=0.0.4",
                charset="utf-8",
            )

        except Exception as e:
            self.logger.error("Metrics handler error", error=str(e))
            return web.Response(
                text=f"# Error generating metrics: {e}\n",
                status=500,
                content_type="text/plain",
            )

    async def _root_handler(self, request: web.Request) -> web.Response:
        """Handle root requests."""
        return web.json_response(
            {
                "service": "AutoUAM Health Server",
                "version": "1.0.0a5",
                "endpoints": {
                    "health": self.config.health.endpoint,
                    "metrics": self.config.health.metrics_endpoint,
                    "ready": "/ready",
                    "live": "/live",
                },
            }
        )

    async def _ready_handler(self, request: web.Request) -> web.Response:
        """Handle readiness probe requests."""
        try:
            # Quick health check
            is_healthy = self.health_checker.is_healthy()

            status_code = 200 if is_healthy else 503

            return web.json_response(
                {
                    "ready": is_healthy,
                    "timestamp": asyncio.get_event_loop().time(),
                },
                status=status_code,
            )

        except Exception as e:
            self.logger.error("Readiness probe error", error=str(e))
            return web.json_response(
                {
                    "ready": False,
                    "error": str(e),
                    "timestamp": asyncio.get_event_loop().time(),
                },
                status=503,
            )

    async def _live_handler(self, request: web.Request) -> web.Response:
        """Handle liveness probe requests."""
        # Liveness probe is always successful if the server is running
        return web.json_response(
            {
                "alive": True,
                "timestamp": asyncio.get_event_loop().time(),
            }
        )

    async def start(self) -> None:
        """Start the health server."""
        if self.runner is not None:
            self.logger.warning("Health server already running")
            return

        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            self.site = web.TCPSite(
                self.runner,
                "0.0.0.0",  # Bind to all interfaces
                self.config.health.port,
            )

            await self.site.start()

            self.logger.info(
                "Health server started",
                port=self.config.health.port,
                endpoint=self.config.health.endpoint,
                metrics_endpoint=self.config.health.metrics_endpoint,
            )

        except Exception as e:
            self.logger.error("Failed to start health server", error=str(e))
            raise

    async def stop(self) -> None:
        """Stop the health server."""
        if self.runner is None:
            return

        try:
            await self.runner.cleanup()
            self.runner = None
            self.site = None

            self.logger.info("Health server stopped")

        except Exception as e:
            self.logger.error("Error stopping health server", error=str(e))

    def get_server_info(self) -> dict:
        """Get server information."""
        return {
            "running": self.runner is not None,
            "port": self.config.health.port,
            "endpoint": self.config.health.endpoint,
            "metrics_endpoint": self.config.health.metrics_endpoint,
        }
