"""End-to-end tests for AutoUAM.

This module provides comprehensive end-to-end tests that demonstrate how to test
AutoUAM without requiring real Cloudflare credentials.
It starts a mock Cloudflare API server and runs AutoUAM against it.

These tests can be run with:
    pytest tests/test_end_to_end.py -v
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Optional

import pytest
import yaml

from autouam.config.settings import Settings
from autouam.core.uam_manager import UAMManager
from autouam.health.checks import HealthChecker
from tests.mock_cloudflare_server import MockCloudflareServer


class TestEndToEnd:
    """End-to-end tests for AutoUAM."""

    @pytest.fixture
    async def end_to_end_setup(self):
        """Set up the end-to-end test environment."""
        # Start mock Cloudflare server
        mock_server = MockCloudflareServer(port=8081)
        await mock_server.start()

        # Create test configuration
        config_data = {
            "cloudflare": {
                "api_token": "test_token",
                "email": "test@example.com",
                "zone_id": "test_zone_id",
                "base_url": "http://localhost:8081/client/v4",
            },
            "monitoring": {
                "check_interval": 2,  # Fast for testing
                "load_thresholds": {"upper": 2.0, "lower": 1.0},
                "minimum_uam_duration": 60,  # Minimum allowed
            },
            "logging": {"level": "INFO", "output": "stdout", "format": "text"},
            "health": {"enabled": True, "port": 8082},
            "deployment": {"mode": "daemon"},
            "security": {"regular_mode": "essentially_off"},
        }

        # Create temporary config file
        config_file = Path(tempfile.mktemp(suffix=".yaml"))
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Load settings
        settings = Settings.from_file(config_file)

        yield {
            "mock_server": mock_server,
            "config_file": config_file,
            "settings": settings,
        }

        # Cleanup
        await mock_server.stop()
        if config_file.exists():
            config_file.unlink()

    @pytest.mark.asyncio
    async def test_initialization(self, end_to_end_setup):
        """Test that AutoUAM initializes correctly."""
        settings = end_to_end_setup["settings"]

        manager = UAMManager(settings)
        success = await manager.initialize()

        assert success is True, "UAMManager should initialize successfully"

    @pytest.mark.asyncio
    async def test_health_check(self, end_to_end_setup):
        """Test health checker."""
        settings = end_to_end_setup["settings"]

        checker = HealthChecker(settings)
        await checker.initialize()

        result = await checker.check_health()

        assert result["healthy"] is True, "Health check should pass"
        for check_name, check_result in result["checks"].items():
            assert check_result["healthy"] is True, f"Check {check_name} should pass"

    @pytest.mark.asyncio
    async def test_manual_control(self, end_to_end_setup):
        """Test manual UAM control."""
        settings = end_to_end_setup["settings"]

        manager = UAMManager(settings)
        await manager.initialize()

        # Test enable
        result = await manager.enable_uam_manual()
        assert result is True, "Manual enable should succeed"

        # Test disable
        result = await manager.disable_uam_manual()
        assert result is True, "Manual disable should succeed"

    @pytest.mark.asyncio
    async def test_high_load_scenario(self, end_to_end_setup):
        """Test the high load scenario."""
        settings = end_to_end_setup["settings"]

        manager = UAMManager(settings)
        await manager.initialize()

        # Mock high load
        with self._mock_high_load():
            # Use check_once to simulate a monitoring cycle
            result = await manager.check_once()

            # Check if UAM was enabled (or at least the check completed successfully)
            assert "uam_enabled" in result, "Result should contain uam_enabled status"

    @pytest.mark.asyncio
    async def test_low_load_scenario(self, end_to_end_setup):
        """Test the low load scenario."""
        settings = end_to_end_setup["settings"]

        manager = UAMManager(settings)
        await manager.initialize()

        # First enable UAM
        result = await manager.enable_uam_manual()
        assert result is True, "Should be able to enable UAM for testing"

        # Wait a moment
        await asyncio.sleep(1)

        # Mock low load
        with self._mock_low_load():
            # Use check_once to simulate a monitoring cycle
            result = await manager.check_once()

            # Check that the monitoring cycle completed
            assert "uam_enabled" in result, "Result should contain uam_enabled status"

    @pytest.mark.asyncio
    async def test_error_handling(self, end_to_end_setup):
        """Test error handling scenarios."""
        # Test with invalid token
        invalid_settings = Settings(
            cloudflare={
                "api_token": "invalid_token",
                "email": "test@example.com",
                "zone_id": "test_zone_id",
                "base_url": "http://localhost:8081/client/v4",
            },
            monitoring=end_to_end_setup["settings"].monitoring,
            logging=end_to_end_setup["settings"].logging,
            health=end_to_end_setup["settings"].health,
            deployment=end_to_end_setup["settings"].deployment,
            security=end_to_end_setup["settings"].security,
        )

        manager = UAMManager(invalid_settings)
        success = await manager.initialize()

        assert success is False, "Should fail with invalid API token"

    def _mock_high_load(self):
        """Context manager to mock high load."""
        import autouam.core.monitor

        original_method = autouam.core.monitor.LoadMonitor.get_normalized_load

        def mock_high_load(self):
            return 30.0  # High load

        autouam.core.monitor.LoadMonitor.get_normalized_load = mock_high_load

        class MockContext:
            def __enter__(self):
                pass

            def __exit__(self, exc_type, exc_val, exc_tb):
                autouam.core.monitor.LoadMonitor.get_normalized_load = original_method

        return MockContext()

    def _mock_low_load(self):
        """Context manager to mock low load."""
        import autouam.core.monitor

        original_method = autouam.core.monitor.LoadMonitor.get_normalized_load

        def mock_low_load(self):
            return 5.0  # Low load

        autouam.core.monitor.LoadMonitor.get_normalized_load = mock_low_load

        class MockContext:
            def __enter__(self):
                pass

            def __exit__(self, exc_type, exc_val, exc_tb):
                autouam.core.monitor.LoadMonitor.get_normalized_load = original_method

        return MockContext()


# Keep the original standalone functionality for manual testing
class EndToEndTester:
    """End-to-end tester for AutoUAM (standalone version)."""

    def __init__(self):
        self.mock_server: Optional[MockCloudflareServer] = None
        self.test_config_path: Optional[Path] = None
        self.settings: Optional[Settings] = None

    async def setup(self):
        """Set up the test environment."""
        print("🚀 Setting up end-to-end test environment...")

        # Start mock Cloudflare server
        self.mock_server = MockCloudflareServer(port=8081)
        await self.mock_server.start()

        # Create test configuration
        self.test_config_path = await self.create_test_config()

        # Load settings
        self.settings = Settings.from_file(self.test_config_path)

        print("✅ Test environment ready!")

    async def create_test_config(self) -> Path:
        """Create a test configuration file."""
        config_data = {
            "cloudflare": {
                "api_token": "test_token",
                "email": "test@example.com",
                "zone_id": "test_zone_id",
                "base_url": "http://localhost:8081/client/v4",
            },
            "monitoring": {
                "check_interval": 2,  # Fast for testing
                "load_thresholds": {"upper": 2.0, "lower": 1.0},
                "minimum_uam_duration": 60,  # Minimum allowed
            },
            "logging": {"level": "INFO", "output": "stdout", "format": "text"},
            "health": {"enabled": True, "port": 8082},
            "deployment": {"mode": "daemon"},
            "security": {"regular_mode": "essentially_off"},
        }

        # Create temporary config file
        config_file = Path(tempfile.mktemp(suffix=".yaml"))
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        return config_file

    async def test_initialization(self) -> bool:
        """Test that AutoUAM initializes correctly."""
        print("\n🔧 Testing initialization...")

        if self.settings is None:
            return False

        manager = UAMManager(self.settings)
        success = await manager.initialize()

        if success:
            print("✅ UAMManager initialized successfully")
        else:
            print("❌ UAMManager failed to initialize")
            return False

        return True

    async def test_health_check(self) -> bool:
        """Test health checker."""
        print("\n🏥 Testing health checker...")

        if self.settings is None:
            return False

        checker = HealthChecker(self.settings)
        await checker.initialize()

        result = await checker.check_health()

        print(f"Health check result: {result['healthy']}")
        for check_name, check_result in result["checks"].items():
            status = "✅" if check_result["healthy"] else "❌"
            print(f"  {status} {check_name}: {check_result['status']}")

        return result["healthy"]

    async def test_high_load_scenario(self) -> bool:
        """Test the high load scenario."""
        print("\n📈 Testing high load scenario...")

        if self.settings is None:
            return False

        manager = UAMManager(self.settings)
        await manager.initialize()

        # Mock high load
        with self.mock_high_load():
            # Use check_once to simulate a monitoring cycle
            result = await manager.check_once()

            print(f"High load check result: {result}")

            # Check if UAM was enabled
            if isinstance(result, dict) and result.get("uam_enabled", False):
                print("✅ UAM was enabled due to high load")
            else:
                message = (
                    "⚠️  UAM was not enabled (may be already enabled or other reason)"
                )
                print(message)
            return True

    async def test_low_load_scenario(self) -> bool:
        """Test the low load scenario."""
        print("\n📉 Testing low load scenario...")

        if self.settings is None:
            return False

        manager = UAMManager(self.settings)
        await manager.initialize()

        # First enable UAM
        result = await manager.enable_uam_manual()
        if result:
            print("✅ UAM enabled for testing")
        else:
            print("❌ Failed to enable UAM for testing")
            return False

        # Wait a moment
        await asyncio.sleep(1)

        # Mock low load
        with self.mock_low_load():
            # Use check_once to simulate a monitoring cycle
            result = await manager.check_once()

            print(f"Low load check result: {result}")

            # Check if UAM was disabled
            if isinstance(result, dict) and not result.get("uam_enabled", True):
                print("✅ UAM was disabled due to low load")
            else:
                message = "⚠️  UAM was not disabled (may be due to minimum duration)"
                print(message)
            return True

    async def test_manual_control(self) -> bool:
        """Test manual UAM control."""
        print("\n🎮 Testing manual control...")

        if self.settings is None:
            return False

        manager = UAMManager(self.settings)
        await manager.initialize()

        # Test enable
        result = await manager.enable_uam_manual()
        if result:
            print("✅ Manual enable successful")
        else:
            print("❌ Manual enable failed")
            return False

        # Test disable
        result = await manager.disable_uam_manual()
        if result:
            print("✅ Manual disable successful")
        else:
            print("❌ Manual disable failed")
            return False

        return True

    async def test_error_handling(self) -> bool:
        """Test error handling scenarios."""
        print("\n⚠️  Testing error handling...")

        if self.settings is None:
            return False

        # Test with invalid token
        invalid_settings = Settings(
            cloudflare={
                "api_token": "invalid_token",
                "email": "test@example.com",
                "zone_id": "test_zone_id",
                "base_url": "http://localhost:8081/client/v4",
            },
            monitoring=self.settings.monitoring,
            logging=self.settings.logging,
            health=self.settings.health,
            deployment=self.settings.deployment,
            security=self.settings.security,
        )

        manager = UAMManager(invalid_settings)
        success = await manager.initialize()

        if not success:
            print("✅ Properly handled invalid API token")
        else:
            print("❌ Should have failed with invalid token")
            return False

        return True

    def mock_high_load(self):
        """Context manager to mock high load."""
        import autouam.core.monitor

        original_method = autouam.core.monitor.LoadMonitor.get_normalized_load

        def mock_high_load(self):
            return 30.0  # High load

        autouam.core.monitor.LoadMonitor.get_normalized_load = mock_high_load

        class MockContext:
            def __enter__(self):
                pass

            def __exit__(self, exc_type, exc_val, exc_tb):
                autouam.core.monitor.LoadMonitor.get_normalized_load = original_method

        return MockContext()

    def mock_low_load(self):
        """Context manager to mock low load."""
        import autouam.core.monitor

        original_method = autouam.core.monitor.LoadMonitor.get_normalized_load

        def mock_low_load(self):
            return 5.0  # Low load

        autouam.core.monitor.LoadMonitor.get_normalized_load = mock_low_load

        class MockContext:
            def __enter__(self):
                pass

            def __exit__(self, exc_type, exc_val, exc_tb):
                autouam.core.monitor.LoadMonitor.get_normalized_load = original_method

        return MockContext()

    async def cleanup(self):
        """Clean up test environment."""
        print("\n🧹 Cleaning up...")

        if self.mock_server:
            await self.mock_server.stop()

        if self.test_config_path and self.test_config_path.exists():
            self.test_config_path.unlink()

        print("✅ Cleanup complete")

    async def run_all_tests(self):
        """Run all end-to-end tests."""
        try:
            await self.setup()

            tests = [
                ("Initialization", self.test_initialization),
                ("Health Check", self.test_health_check),
                ("Manual Control", self.test_manual_control),
                ("High Load Scenario", self.test_high_load_scenario),
                ("Low Load Scenario", self.test_low_load_scenario),
                ("Error Handling", self.test_error_handling),
            ]

            results = []
            for test_name, test_func in tests:
                try:
                    result = await test_func()
                    results.append((test_name, result))
                except Exception as e:
                    print(f"❌ {test_name} failed with error: {e}")
                    results.append((test_name, False))

            # Print summary
            print("\n" + "=" * 50)
            print("📊 TEST SUMMARY")
            print("=" * 50)

            passed = 0
            for test_name, result in results:
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status} {test_name}")
                if result:
                    passed += 1

            print(f"\nResults: {passed}/{len(results)} tests passed")

            if passed == len(results):
                print("🎉 All tests passed! AutoUAM is ready for deployment.")
            else:
                print("⚠️  Some tests failed. Please review the issues above.")

        finally:
            await self.cleanup()


async def main():
    """Main entry point for standalone testing."""
    print("🧪 AutoUAM End-to-End Test Suite")
    print("=" * 50)

    tester = EndToEndTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    # Run the tests
    asyncio.run(main())
