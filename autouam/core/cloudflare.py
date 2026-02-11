"""Cloudflare API client for AutoUAM."""

import asyncio

import aiohttp

from .. import __version__
from ..logging.setup import get_logger

# Max retries for transient network errors (e.g. Broken pipe)
MAX_REQUEST_RETRIES = 3
# Backoff base seconds: 1, 2, 4
RETRY_BACKOFF_BASE = 1


class CloudflareError(Exception):
    """Base exception for Cloudflare API errors."""

    pass


def _is_retryable_error(exc: BaseException) -> bool:
    """True if the error is transient and retrying with a new connection may help."""
    if isinstance(exc, (BrokenPipeError, ConnectionError)):
        return True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) == 32:
        return True  # errno 32 is EPIPE (Broken pipe)
    if isinstance(
        exc,
        (
            aiohttp.ClientError,
            aiohttp.ServerDisconnectedError,
            aiohttp.ClientConnectorError,
            ConnectionResetError,
        ),
    ):
        return True
    # aiohttp wraps OSError in ClientOSError
    if type(exc).__name__ == "ClientOSError" and getattr(exc, "os_error", None):
        return _is_retryable_error(exc.os_error)
    return False


class CloudflareClient:
    """Cloudflare API client."""

    def __init__(self, api_token: str, zone_id: str):
        self.api_token = api_token
        self.zone_id = zone_id
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.logger = get_logger(__name__)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            if self._session:
                await self._session.close()
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                    "User-Agent": f"AutoUAM/{__version__}",
                }
            )
        return self._session

    async def _close_session(self) -> None:
        """Close and clear the session so next request uses a fresh connection."""
        if self._session:
            await self._session.close()
            self._session = None

    async def _request(self, method: str, endpoint: str, data=None) -> dict:
        """Make an API request with retries on transient errors (e.g. Broken pipe)."""
        url = f"{self.base_url}{endpoint}"
        last_exc = None

        for attempt in range(1, MAX_REQUEST_RETRIES + 1):
            try:
                session = await self._get_session()
                async with session.request(method, url, json=data) as response:
                    result = await response.json()

                    if not result.get("success"):
                        errors = result.get("errors", [])
                        error_msg = "; ".join(
                            e.get("message", "Unknown error") for e in errors
                        )
                        raise CloudflareError(f"API request failed: {error_msg}")

                    return result
            except CloudflareError:
                raise
            except Exception as e:
                last_exc = e
                if _is_retryable_error(e) and attempt < MAX_REQUEST_RETRIES:
                    wait_time = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                    self.logger.warning(
                        "Network error, retrying",
                        extra={
                            "error": str(e),
                            "attempt": attempt,
                            "wait_time": wait_time,
                        },
                    )
                    await self._close_session()
                    await asyncio.sleep(wait_time)
                else:
                    raise

        raise last_exc

    async def close(self) -> None:
        """Close the session."""
        if self._session:
            await self._session.close()

    async def get_zone_settings(self) -> dict:
        """Get current zone settings."""
        endpoint = f"/zones/{self.zone_id}/settings/security_level"
        return await self._request("GET", endpoint)

    async def update_security_level(self, level: str) -> dict:
        """Update zone security level."""
        endpoint = f"/zones/{self.zone_id}/settings/security_level"
        data = {"value": level}
        return await self._request("PATCH", endpoint, data)

    async def enable_under_attack_mode(self) -> dict:
        """Enable Under Attack Mode."""
        return await self.update_security_level("under_attack")

    async def disable_under_attack_mode(
        self, regular_mode: str = "essentially_off"
    ) -> dict:
        """Disable Under Attack Mode."""
        return await self.update_security_level(regular_mode)

    async def get_zone_info(self) -> dict:
        """Get zone information."""
        endpoint = f"/zones/{self.zone_id}"
        return await self._request("GET", endpoint)

    async def test_connection(self) -> bool:
        """Test API connection."""
        try:
            await self.get_zone_info()
            return True
        except Exception:
            return False

    async def get_current_security_level(self) -> str:
        """Get current security level."""
        response = await self.get_zone_settings()
        return response.get("result", {}).get("value", "unknown")
