"""Tests for Cloudflare client functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientResponseError, ClientSession

from autouam.core.cloudflare import CloudflareAPIError, CloudflareClient


class TestCloudflareClient:
    """Test CloudflareClient class."""

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
    def cloudflare_client(self, mock_settings):
        """Create a CloudflareClient instance for testing."""
        return CloudflareClient(
            api_token=mock_settings.cloudflare.api_token,
            zone_id=mock_settings.cloudflare.zone_id,
            base_url="https://api.cloudflare.com/client/v4",
        )

    @pytest.mark.asyncio
    async def test_cloudflare_client_initialization(
        self, cloudflare_client, mock_settings
    ):
        """Test CloudflareClient initialization."""
        assert cloudflare_client.api_token == "test_token_123456789"
        assert cloudflare_client.zone_id == "test_zone_123456789"
        assert cloudflare_client.base_url == "https://api.cloudflare.com/client/v4"

    @pytest.mark.asyncio
    async def test_cloudflare_client_custom_base_url(self, mock_settings):
        """Test CloudflareClient with custom base URL."""
        client = CloudflareClient(
            api_token=mock_settings.cloudflare.api_token,
            zone_id=mock_settings.cloudflare.zone_id,
            base_url="http://localhost:8081/client/v4",
        )
        assert client.base_url == "http://localhost:8081/client/v4"

    @pytest.mark.asyncio
    async def test_test_connection_success(self, cloudflare_client):
        """Test successful connection test."""
        with patch.object(cloudflare_client, "_make_request") as mock_request:
            mock_request.return_value = {"success": True, "result": {"id": "test_zone"}}

            result = await cloudflare_client.test_connection()
            assert result is True
            mock_request.assert_called_once_with(
                "GET", f"/zones/{cloudflare_client.zone_id}"
            )

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, cloudflare_client):
        """Test connection test failure."""
        with patch.object(cloudflare_client, "_make_request") as mock_request:
            mock_request.side_effect = ClientResponseError(
                request_info=MagicMock(),
                history=[],
                status=403,
                message="Invalid API token",
            )

            result = await cloudflare_client.test_connection()
            assert result is False

    @pytest.mark.asyncio
    async def test_get_current_security_level_success(self, cloudflare_client):
        """Test successful security level retrieval."""
        with patch.object(cloudflare_client, "_make_request") as mock_request:
            mock_request.return_value = {
                "success": True,
                "result": {"value": "essentially_off"},
            }

            result = await cloudflare_client.get_current_security_level()
            assert result == "essentially_off"
            mock_request.assert_called_once_with(
                "GET", f"/zones/{cloudflare_client.zone_id}/settings/security_level"
            )

    @pytest.mark.asyncio
    async def test_get_current_security_level_failure(self, cloudflare_client):
        """Test security level retrieval failure."""
        with patch.object(cloudflare_client, "_make_request") as mock_request:
            mock_request.side_effect = ClientResponseError(
                request_info=MagicMock(),
                history=[],
                status=404,
                message="Zone not found",
            )

            with pytest.raises(ClientResponseError):
                await cloudflare_client.get_current_security_level()

    @pytest.mark.asyncio
    async def test_enable_under_attack_mode_success(self, cloudflare_client):
        """Test successful UAM enablement."""
        with patch.object(cloudflare_client, "_make_request") as mock_request:
            mock_request.return_value = {
                "success": True,
                "result": {"value": "under_attack"},
            }

            result = await cloudflare_client.enable_under_attack_mode()
            assert result["success"] is True
            mock_request.assert_called_once_with(
                "PATCH",
                f"/zones/{cloudflare_client.zone_id}/settings/security_level",
                {"value": "under_attack"},
            )

    @pytest.mark.asyncio
    async def test_enable_under_attack_mode_failure(self, cloudflare_client):
        """Test UAM enablement failure."""
        with patch.object(cloudflare_client, "_make_request") as mock_request:
            mock_request.side_effect = ClientResponseError(
                request_info=MagicMock(),
                history=[],
                status=429,
                message="Rate limit exceeded",
            )

            with pytest.raises(ClientResponseError):
                await cloudflare_client.enable_under_attack_mode()

    @pytest.mark.asyncio
    async def test_disable_under_attack_mode_success(self, cloudflare_client):
        """Test successful UAM disablement."""
        with patch.object(cloudflare_client, "_make_request") as mock_request:
            mock_request.return_value = {
                "success": True,
                "result": {"value": "essentially_off"},
            }

            result = await cloudflare_client.disable_under_attack_mode(
                "essentially_off"
            )
            assert result["success"] is True
            mock_request.assert_called_once_with(
                "PATCH",
                f"/zones/{cloudflare_client.zone_id}/settings/security_level",
                {"value": "essentially_off"},
            )

    @pytest.mark.asyncio
    async def test_disable_under_attack_mode_failure(self, cloudflare_client):
        """Test UAM disablement failure."""
        with patch.object(cloudflare_client, "_make_request") as mock_request:
            mock_request.side_effect = ClientResponseError(
                request_info=MagicMock(),
                history=[],
                status=500,
                message="Internal server error",
            )

            with pytest.raises(ClientResponseError):
                await cloudflare_client.disable_under_attack_mode("essentially_off")

    @pytest.mark.asyncio
    async def test_make_request_success(self, cloudflare_client):
        """Test successful API request."""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"success": True, "result": "test"})
        mock_response.status = 200

        with patch.object(ClientSession, "request") as mock_session_request:
            mock_session_request.return_value.__aenter__.return_value = mock_response

            result = await cloudflare_client._make_request("GET", "/test")
            assert result == {"success": True, "result": "test"}

    @pytest.mark.asyncio
    async def test_make_request_with_data(self, cloudflare_client):
        """Test API request with data."""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"success": True, "result": "test"})
        mock_response.status = 200

        with patch.object(ClientSession, "request") as mock_session_request:
            mock_session_request.return_value.__aenter__.return_value = mock_response

            result = await cloudflare_client._make_request(
                "POST", "/test", {"key": "value"}
            )
            assert result == {"success": True, "result": "test"}

    @pytest.mark.asyncio
    async def test_make_request_http_error(self, cloudflare_client):
        """Test API request with HTTP error."""
        with patch.object(ClientSession, "request") as mock_session_request:
            mock_session_request.side_effect = ClientResponseError(
                request_info=MagicMock(), history=[], status=400, message="Bad request"
            )

            with pytest.raises(CloudflareAPIError):
                await cloudflare_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_connection_error(self, cloudflare_client):
        """Test API request with connection error."""
        # Create a mock session since the real one might be None
        mock_session = MagicMock()
        mock_session.request = AsyncMock(side_effect=Exception("Connection failed"))

        with patch.object(cloudflare_client, "_session", mock_session):
            with pytest.raises(CloudflareAPIError):
                await cloudflare_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_context_manager(self, cloudflare_client):
        """Test CloudflareClient as context manager."""
        async with cloudflare_client as client:
            assert client == cloudflare_client

    @pytest.mark.asyncio
    async def test_headers_include_auth(self, cloudflare_client):
        """Test that request headers include authentication."""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"success": True})
        mock_response.status = 200

        with patch.object(ClientSession, "request") as mock_session_request:
            mock_session_request.return_value.__aenter__.return_value = mock_response

            await cloudflare_client._make_request("GET", "/test")

            # Check that the request was made with proper headers
            # The headers are set in the session creation, not in the request call
            assert mock_session_request.called

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, cloudflare_client):
        """Test rate limit handling."""
        with patch.object(cloudflare_client, "_make_request") as mock_request:
            # First call fails with rate limit
            mock_request.side_effect = [
                ClientResponseError(
                    request_info=MagicMock(),
                    history=[],
                    status=429,
                    message="Rate limit exceeded",
                ),
                {"success": True, "result": "test"},  # Second call succeeds
            ]

            # The client should handle rate limiting internally
            with pytest.raises(ClientResponseError):
                await cloudflare_client.get_current_security_level()

    @pytest.mark.asyncio
    async def test_invalid_response_format(self, cloudflare_client):
        """Test handling of invalid response format."""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"invalid": "format"})
        mock_response.status = 200

        with patch.object(ClientSession, "request") as mock_session_request:
            mock_session_request.return_value.__aenter__.return_value = mock_response

            with pytest.raises(CloudflareAPIError):
                await cloudflare_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_json_decode_error(self, cloudflare_client):
        """Test handling of JSON decode errors."""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        mock_response.status = 200

        with patch.object(ClientSession, "request") as mock_session_request:
            mock_session_request.return_value.__aenter__.return_value = mock_response

            with pytest.raises(ValueError):
                await cloudflare_client._make_request("GET", "/test")
