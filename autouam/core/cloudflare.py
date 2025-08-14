"""Cloudflare API client for AutoUAM."""

import asyncio
import time
from typing import Any, Dict, List, Optional

import aiohttp
from aiohttp import ClientTimeout

from ..logging.setup import get_logger


class CloudflareError(Exception):
    """Base exception for Cloudflare API errors."""

    pass


class CloudflareAuthError(CloudflareError):
    """Authentication error with Cloudflare API."""

    pass


class CloudflareRateLimitError(CloudflareError):
    """Rate limit exceeded error."""

    pass


class CloudflareAPIError(CloudflareError):
    """General API error."""

    pass


class CloudflareClient:
    """Async Cloudflare API client with rate limiting and retry logic."""

    def __init__(
        self,
        api_token: str,
        zone_id: str,
        timeout: int = 30,
        base_url: str = "https://api.cloudflare.com/client/v4",
    ):
        """Initialize the Cloudflare client."""
        self.api_token = api_token
        self.zone_id = zone_id
        self.timeout = timeout
        self.base_url = base_url
        self.logger = get_logger(__name__)

        # Rate limiting
        self.requests_per_minute = 1200  # Cloudflare's default limit
        self.request_times: List[float] = []

        # Session management
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self) -> None:
        """Ensure HTTP session is created."""
        if self._session is None or self._session.closed:
            # Close any existing session properly
            if self._session and not self._session.closed:
                await self._session.close()

            timeout = ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                    "User-Agent": "AutoUAM/1.0.0a5",
                },
                connector=aiohttp.TCPConnector(limit=10, limit_per_host=5),
            )

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _rate_limit_check(self) -> None:
        """Check and enforce rate limiting."""
        now = time.time()

        # Remove requests older than 1 minute
        self.request_times = [t for t in self.request_times if now - t < 60]

        if len(self.request_times) >= self.requests_per_minute:
            # Wait until we can make another request
            wait_time = 60 - (now - self.request_times[0])
            if wait_time > 0:
                self.logger.warning(
                    "Rate limit reached, waiting",
                    wait_time=wait_time,
                    requests_in_window=len(self.request_times),
                )
                await asyncio.sleep(wait_time)

        self.request_times.append(now)

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Make an HTTP request with retry logic."""
        await self._ensure_session()

        # Type guard to ensure session is not None
        if self._session is None:
            raise RuntimeError("Session was not created properly")

        session = self._session
        url = f"{self.base_url}{endpoint}"

        for attempt in range(max_retries + 1):
            try:
                await self._rate_limit_check()

                self.logger.debug(
                    "Making API request",
                    method=method,
                    url=url,
                    attempt=attempt + 1,
                )

                async with session.request(method, url, json=data) as response:
                    response_data = await response.json()

                    if response.status == 200:
                        if response_data.get("success"):
                            self.logger.debug(
                                "API request successful", endpoint=endpoint
                            )
                            return response_data
                        else:
                            errors = response_data.get("errors", [])
                            error_msg = "; ".join(
                                [e.get("message", "Unknown error") for e in errors]
                            )
                            raise CloudflareAPIError(f"API request failed: {error_msg}")

                    elif response.status == 401:
                        raise CloudflareAuthError(
                            "Authentication failed - check API token"
                        )

                    elif response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        self.logger.warning(
                            "Rate limit exceeded",
                            retry_after=retry_after,
                            attempt=attempt + 1,
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    elif response.status >= 500:
                        # Server error, retry with exponential backoff
                        if attempt < max_retries:
                            wait_time = 2**attempt
                            self.logger.warning(
                                "Server error, retrying",
                                status=response.status,
                                wait_time=wait_time,
                                attempt=attempt + 1,
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            raise CloudflareAPIError(f"Server error: {response.status}")

                    else:
                        raise CloudflareAPIError(
                            f"HTTP {response.status}: {response.reason}"
                        )

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                # If session is closed, recreate it for next attempt
                if self._session and self._session.closed:
                    self.logger.warning(
                        "Session was closed, recreating for next attempt"
                    )
                    self._session = None

                if attempt < max_retries:
                    wait_time = 2**attempt
                    self.logger.warning(
                        "Network error, retrying",
                        error=str(e),
                        wait_time=wait_time,
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise CloudflareAPIError(
                        f"Network error after {max_retries} retries: {e}"
                    )

        raise CloudflareAPIError(f"Request failed after {max_retries} retries")

    async def get_zone_settings(self) -> Dict[str, Any]:
        """Get current zone settings."""
        endpoint = f"/zones/{self.zone_id}/settings/security_level"
        return await self._make_request("GET", endpoint)

    async def update_security_level(self, level: str) -> Dict[str, Any]:
        """Update zone security level."""
        endpoint = f"/zones/{self.zone_id}/settings/security_level"
        data = {"value": level}

        self.logger.info(
            "Updating security level",
            zone_id=self.zone_id,
            new_level=level,
        )

        return await self._make_request("PATCH", endpoint, data)

    async def enable_under_attack_mode(self) -> Dict[str, Any]:
        """Enable Under Attack Mode."""
        return await self.update_security_level("under_attack")

    async def disable_under_attack_mode(
        self, regular_mode: str = "essentially_off"
    ) -> Dict[str, Any]:
        """Disable Under Attack Mode and set to regular mode."""
        return await self.update_security_level(regular_mode)

    async def get_zone_info(self) -> Dict[str, Any]:
        """Get zone information."""
        endpoint = f"/zones/{self.zone_id}"
        return await self._make_request("GET", endpoint)

    async def test_connection(self) -> bool:
        """Test API connection and authentication."""
        try:
            await self.get_zone_info()
            self.logger.info("Cloudflare API connection test successful")
            return True
        except Exception as e:
            self.logger.error("Cloudflare API connection test failed", error=str(e))
            return False

    async def get_current_security_level(self) -> str:
        """Get current security level."""
        try:
            response = await self.get_zone_settings()
            security_level = response.get("result", {}).get("value", "unknown")

            self.logger.debug(
                "Current security level retrieved",
                security_level=security_level,
            )

            return security_level
        except Exception as e:
            self.logger.error("Failed to get current security level", error=str(e))
            # Re-raise the exception to maintain the original behavior
            raise
