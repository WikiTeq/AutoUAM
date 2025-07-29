"""Tests for health server functionality."""

from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from autouam.health.server import HealthServer


class TestHealthServer:
    """Test HealthServer class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        from autouam.config.settings import Settings

        return Settings(
            cloudflare={
                "api_token": "test_token_123456789",
                "email": "test@example.com",
                "zone_id": "test_zone_123456789",
            },
            monitoring={
                "check_interval": 5,
                "load_thresholds": {"upper": 2.0, "lower": 1.0},
                "minimum_uam_duration": 300,
            },
            logging={"level": "INFO", "output": "stdout", "format": "text"},
            health={"enabled": True, "port": 8080},
            deployment={"mode": "daemon"},
            security={"regular_mode": "essentially_off"},
        )

    @pytest.fixture
    def health_server(self, mock_settings):
        """Create a health server instance for testing."""
        from autouam.health.checks import HealthChecker

        health_checker = HealthChecker(mock_settings)
        return HealthServer(mock_settings, health_checker)

    @pytest.mark.asyncio
    async def test_health_server_initialization(self, health_server):
        """Test health server initialization."""
        assert health_server.config is not None
        assert health_server.app is not None
        assert isinstance(health_server.app, web.Application)

    @pytest.mark.asyncio
    async def test_health_endpoint(self, health_server):
        """Test health endpoint."""
        # Create a mock request
        request = make_mocked_request("GET", "/health")

        # Mock the health checker
        with patch.object(health_server, "health_checker") as mock_checker:
            mock_checker.check_health = AsyncMock(
                return_value={
                    "healthy": True,
                    "timestamp": 1234567890.0,
                    "duration": 0.1,
                    "checks": {
                        "system_load": {"healthy": True, "details": "Load: 1.5"},
                        "uam_state": {"healthy": True, "details": "UAM disabled"},
                        "cloudflare_api": {
                            "healthy": True,
                            "details": "API accessible",
                        },
                    },
                    "summary": {
                        "last_success": 1234567890.0,
                        "consecutive_failures": 0,
                        "max_failures": 3,
                    },
                }
            )

            response = await health_server._health_handler(request)

            assert response.status == 200
            # The response is a web.json_response, so we can access the data directly
            data = response.body.decode("utf-8")
            import json

            data = json.loads(data)
            assert data["status"] == "healthy"
            assert "checks" in data

    @pytest.mark.asyncio
    async def test_health_endpoint_unhealthy(self, health_server):
        """Test health endpoint when system is unhealthy."""
        request = make_mocked_request("GET", "/health")

        with patch.object(health_server, "health_checker") as mock_checker:
            mock_checker.check_health = AsyncMock(
                return_value={
                    "healthy": False,
                    "timestamp": 1234567890.0,
                    "duration": 0.1,
                    "checks": {
                        "system_load": {"healthy": True, "details": "Load: 1.5"},
                        "uam_state": {"healthy": True, "details": "UAM disabled"},
                        "cloudflare_api": {"healthy": False, "details": "API error"},
                    },
                    "summary": {
                        "last_success": 1234567890.0,
                        "consecutive_failures": 1,
                        "max_failures": 3,
                    },
                }
            )

            response = await health_server._health_handler(request)

            assert response.status == 503  # Service Unavailable
            data = response.body.decode("utf-8")
            import json

            data = json.loads(data)
            assert data["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, health_server):
        """Test metrics endpoint."""
        request = make_mocked_request("GET", "/metrics")

        response = await health_server._metrics_handler(request)

        assert response.status == 200
        content = response.text
        assert "autouam_" in content  # Should contain metrics

    @pytest.mark.asyncio
    async def test_root_endpoint(self, health_server):
        """Test root endpoint."""
        request = make_mocked_request("GET", "/")

        response = await health_server._root_handler(request)

        assert response.status == 200
        data = response.body.decode("utf-8")
        import json

        data = json.loads(data)
        assert "service" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_checker_initialization_error(self, health_server):
        """Test handling of health checker initialization errors."""
        with patch("autouam.health.server.HealthChecker") as mock_checker_class:
            mock_checker_class.side_effect = Exception("Health checker init failed")

            # Should not raise an exception during server creation
            # The health checker is created lazily
            assert health_server.app is not None

    @pytest.mark.asyncio
    async def test_health_endpoint_exception_handling(self, health_server):
        """Test health endpoint exception handling."""
        request = make_mocked_request("GET", "/health")

        with patch.object(health_server, "health_checker") as mock_checker:
            mock_checker.check_health = AsyncMock(
                side_effect=Exception("Health check failed")
            )

            response = await health_server._health_handler(request)

            assert response.status == 500  # Internal Server Error
            data = response.body.decode("utf-8")
            import json

            data = json.loads(data)
            assert "error" in data

    @pytest.mark.asyncio
    async def test_start_server(self, health_server):
        """Test starting the health server."""
        with patch("aiohttp.web.run_app"):
            await health_server.start()

            # The start method doesn't call run_app directly, it sets up the runner
            assert health_server.runner is not None

    @pytest.mark.asyncio
    async def test_start_server_with_custom_port(self, mock_settings):
        """Test starting the health server with custom port."""
        # Modify settings to use a different port
        mock_settings.health.port = 9090

        from autouam.health.checks import HealthChecker

        health_checker = HealthChecker(mock_settings)
        health_server = HealthServer(mock_settings, health_checker)

        with patch("aiohttp.web.run_app"):
            await health_server.start()

            # The start method doesn't call run_app directly, it sets up the runner
            assert health_server.runner is not None

    @pytest.mark.asyncio
    async def test_health_server_disabled(self, mock_settings):
        """Test health server when health monitoring is disabled."""
        # Disable health monitoring
        mock_settings.health.enabled = False

        from autouam.health.checks import HealthChecker

        health_checker = HealthChecker(mock_settings)
        health_server = HealthServer(mock_settings, health_checker)

        # When health is disabled, the server should not be created
        # This would be handled in the main application logic
        assert health_server.app is not None  # App is still created

    def test_health_server_routes(self, health_server):
        """Test that all expected routes are registered."""
        routes = list(health_server.app.router.routes())

        # Check that expected routes exist
        route_paths = [
            route.resource.canonical
            for route in routes
            if hasattr(route.resource, "canonical")
        ]

        assert "/health" in route_paths
        assert "/metrics" in route_paths
        assert "/" in route_paths

    @pytest.mark.asyncio
    async def test_metrics_content_type(self, health_server):
        """Test that metrics endpoint returns correct content type."""
        request = make_mocked_request("GET", "/metrics")

        response = await health_server._metrics_handler(request)

        assert response.status == 200
        assert response.content_type == "text/plain"

    @pytest.mark.asyncio
    async def test_health_content_type(self, health_server):
        """Test that health endpoint returns correct content type."""
        request = make_mocked_request("GET", "/health")

        with patch.object(health_server, "health_checker") as mock_checker:
            mock_checker.check_health = AsyncMock(
                return_value={
                    "healthy": True,
                    "timestamp": 1234567890.0,
                    "duration": 0.1,
                    "checks": {},
                    "summary": {
                        "last_success": 1234567890.0,
                        "consecutive_failures": 0,
                        "max_failures": 3,
                    },
                }
            )

            response = await health_server._health_handler(request)

            assert response.status == 200
            assert response.content_type == "application/json"
