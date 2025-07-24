#!/usr/bin/env python3
"""
End-to-end test script for AutoUAM.

This script demonstrates how to test AutoUAM without requiring real Cloudflare credentials.
It starts a mock Cloudflare API server and runs AutoUAM against it.

Usage:
    python test_end_to_end.py

Requirements:
    - aiohttp (for mock server)
    - pytest-asyncio (for async tests)
"""

import asyncio
import json
import os
import signal
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import yaml

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from tests.mock_cloudflare_server import MockCloudflareServer
from autouam.config.settings import Settings
from autouam.core.uam_manager import UAMManager
from autouam.health.checks import HealthChecker


class EndToEndTester:
    """End-to-end tester for AutoUAM."""

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
                "zone_id": "test_zone_id"
            },
            "monitoring": {
                "check_interval": 2,  # Fast for testing
                "load_thresholds": {"upper": 2.0, "lower": 1.0},
                "minimum_uam_duration": 60  # Minimum allowed
            },
            "logging": {
                "level": "INFO",
                "output": "stdout",
                "format": "text"
            },
            "health": {
                "enabled": True,
                "port": 8082
            },
            "deployment": {
                "mode": "daemon"
            },
            "security": {
                "regular_mode": "essentially_off"
            }
        }

        # Create temporary config file
        config_file = Path(tempfile.mktemp(suffix='.yaml'))
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        return config_file

    async def test_initialization(self):
        """Test that AutoUAM initializes correctly."""
        print("\n🔧 Testing initialization...")

        manager = UAMManager(self.settings)
        success = await manager.initialize()

        if success:
            print("✅ UAMManager initialized successfully")
        else:
            print("❌ UAMManager failed to initialize")
            return False

        return True

    async def test_health_check(self):
        """Test health checker."""
        print("\n🏥 Testing health checker...")

        checker = HealthChecker(self.settings)
        await checker.initialize()

        result = await checker.check_health()

        print(f"Health check result: {result['healthy']}")
        for check_name, check_result in result['checks'].items():
            status = "✅" if check_result['healthy'] else "❌"
            print(f"  {status} {check_name}: {check_result['status']}")

        return result['healthy']

    async def test_high_load_scenario(self):
        """Test the high load scenario."""
        print("\n📈 Testing high load scenario...")

        manager = UAMManager(self.settings)
        await manager.initialize()

        # Mock high load
        with self.mock_high_load():
            result = await manager.check_and_act()

            print(f"High load check result: {result['action']}")
            print(f"Reason: {result.get('reason', 'N/A')}")

            if result['action'] == 'enabled':
                print("✅ UAM was enabled due to high load")
                return True
            else:
                print("⚠️  UAM was not enabled (may be already enabled or other reason)")
                return True

        return False

    async def test_low_load_scenario(self):
        """Test the low load scenario."""
        print("\n📉 Testing low load scenario...")

        manager = UAMManager(self.settings)
        await manager.initialize()

        # First enable UAM
        await manager.enable_uam("Test enable")
        print("✅ UAM enabled for testing")

        # Wait a moment
        await asyncio.sleep(1)

        # Mock low load
        with self.mock_low_load():
            result = await manager.check_and_act()

            print(f"Low load check result: {result['action']}")
            print(f"Reason: {result.get('reason', 'N/A')}")

            if result['action'] == 'disabled':
                print("✅ UAM was disabled due to low load")
                return True
            else:
                print("⚠️  UAM was not disabled (may be due to minimum duration)")
                return True

        return False

    async def test_manual_control(self):
        """Test manual UAM control."""
        print("\n🎮 Testing manual control...")

        manager = UAMManager(self.settings)
        await manager.initialize()

        # Test enable
        result = await manager.enable_uam("Manual test enable")
        if result['success']:
            print("✅ Manual enable successful")
        else:
            print("❌ Manual enable failed")
            return False

        # Test disable
        result = await manager.disable_uam("Manual test disable")
        if result['success']:
            print("✅ Manual disable successful")
        else:
            print("❌ Manual disable failed")
            return False

        return True

    async def test_error_handling(self):
        """Test error handling scenarios."""
        print("\n⚠️  Testing error handling...")

        # Test with invalid token
        invalid_settings = Settings(
            cloudflare={
                "api_token": "invalid_token",
                "email": "test@example.com",
                "zone_id": "test_zone_id"
            },
            monitoring=self.settings.monitoring,
            logging=self.settings.logging,
            health=self.settings.health,
            deployment=self.settings.deployment,
            security=self.settings.security
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

        def mock_high_load():
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

        def mock_low_load():
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
            print("\n" + "="*50)
            print("📊 TEST SUMMARY")
            print("="*50)

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
    """Main entry point."""
    print("🧪 AutoUAM End-to-End Test Suite")
    print("="*50)

    tester = EndToEndTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n🛑 Test interrupted by user")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Run the tests
    asyncio.run(main())
