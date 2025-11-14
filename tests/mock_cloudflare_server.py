"""Mock Cloudflare API server for testing."""

import asyncio
import json

from aiohttp import web


class MockCloudflareServer:
    """Mock Cloudflare API server for testing."""

    def __init__(self, port: int = 8081):
        self.port = port
        self.app = web.Application()
        self.app.router.add_get(
            "/client/v4/zones/{zone_id}/settings/security_level",
            self.get_security_level,
        )
        self.app.router.add_patch(
            "/client/v4/zones/{zone_id}/settings/security_level",
            self.set_security_level,
        )
        self.app.router.add_get("/client/v4/zones/{zone_id}", self.get_zone_info)
        self.app.router.add_get("/client/v4/user/tokens/verify", self.verify_token)

        # State
        self.security_level = "essentially_off"
        self.valid_tokens = {"test_token": "test@example.com"}
        self.rate_limit_counter = 0
        self.rate_limit_reset = 0

    async def get_security_level(self, request: web.Request) -> web.Response:
        """Mock GET security level endpoint."""
        # Check authentication
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return web.json_response(
                {
                    "success": False,
                    "errors": [{"code": 6003, "message": "Invalid request headers"}],
                },
                status=401,
            )

        token = auth_header[7:]  # Remove 'Bearer ' prefix
        if token not in self.valid_tokens:
            return web.json_response(
                {
                    "success": False,
                    "errors": [{"code": 6003, "message": "Invalid API token"}],
                },
                status=403,
            )

        return web.json_response(
            {
                "success": True,
                "result": {
                    "id": "security_level",
                    "value": self.security_level,
                    "modified_on": "2023-01-01T00:00:00Z",
                    "editable": True,
                },
            }
        )

    async def set_security_level(self, request: web.Request) -> web.Response:
        """Mock PATCH security level endpoint."""
        # Check authentication
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return web.json_response(
                {
                    "success": False,
                    "errors": [{"code": 6003, "message": "Invalid request headers"}],
                },
                status=401,
            )

        token = auth_header[7:]  # Remove 'Bearer ' prefix
        if token not in self.valid_tokens:
            return web.json_response(
                {
                    "success": False,
                    "errors": [{"code": 6003, "message": "Invalid API token"}],
                },
                status=403,
            )

        # Check rate limiting
        if self.rate_limit_counter >= 10:
            return web.json_response(
                {
                    "success": False,
                    "errors": [{"code": 1015, "message": "Rate limit exceeded"}],
                },
                status=429,
                headers={"Retry-After": "60"},
            )

        # Parse request body
        try:
            body = await request.json()
            new_level = body.get("value")
        except json.JSONDecodeError:
            return web.json_response(
                {
                    "success": False,
                    "errors": [{"code": 6001, "message": "Invalid JSON"}],
                },
                status=400,
            )

        # Validate security level
        valid_levels = ["essentially_off", "low", "medium", "high", "under_attack"]
        if new_level not in valid_levels:
            return web.json_response(
                {
                    "success": False,
                    "errors": [{"code": 1004, "message": "Invalid security level"}],
                },
                status=400,
            )

        # Update state
        self.security_level = new_level
        self.rate_limit_counter += 1

        return web.json_response(
            {
                "success": True,
                "result": {
                    "id": "security_level",
                    "value": self.security_level,
                    "modified_on": "2023-01-01T00:00:00Z",
                    "editable": True,
                },
            }
        )

    async def verify_token(self, request: web.Request) -> web.Response:
        """Mock token verification endpoint."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return web.json_response(
                {
                    "success": False,
                    "errors": [{"code": 6003, "message": "Invalid request headers"}],
                },
                status=401,
            )

        token = auth_header[7:]  # Remove 'Bearer ' prefix
        if token not in self.valid_tokens:
            return web.json_response(
                {
                    "success": False,
                    "errors": [{"code": 6003, "message": "Invalid API token"}],
                },
                status=403,
            )

        return web.json_response(
            {
                "success": True,
                "result": {
                    "id": "test_token_id",
                    "status": "active",
                    "issued_on": "2023-01-01T00:00:00Z",
                    "modified_on": "2023-01-01T00:00:00Z",
                    "not_before": "2023-01-01T00:00:00Z",
                    "expires_on": "2024-01-01T00:00:00Z",
                },
            }
        )

    async def get_zone_info(self, request: web.Request) -> web.Response:
        """Mock GET zone info endpoint."""
        zone_id = request.match_info["zone_id"]

        # Check authentication
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return web.json_response(
                {
                    "success": False,
                    "errors": [{"code": 6003, "message": "Invalid request headers"}],
                },
                status=401,
            )

        token = auth_header[7:]  # Remove 'Bearer ' prefix
        if token not in self.valid_tokens:
            return web.json_response(
                {
                    "success": False,
                    "errors": [{"code": 6003, "message": "Invalid API token"}],
                },
                status=403,
            )

        return web.json_response(
            {
                "success": True,
                "result": {
                    "id": zone_id,
                    "name": "example.com",
                    "status": "active",
                    "type": "full",
                    "created_on": "2023-01-01T00:00:00Z",
                    "modified_on": "2023-01-01T00:00:00Z",
                },
            }
        )

    async def start(self) -> None:
        """Start the mock server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "localhost", self.port)
        await self.site.start()
        print(f"Mock Cloudflare server running on http://localhost:{self.port}")

    async def stop(self) -> None:
        """Stop the mock server."""
        if hasattr(self, "site"):
            await self.site.stop()
        if hasattr(self, "runner"):
            await self.runner.cleanup()
        await self.app.cleanup()


async def main():
    """Run the mock server."""
    server = MockCloudflareServer()
    await server.start()

    try:
        # Keep the server running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down mock server...")
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
