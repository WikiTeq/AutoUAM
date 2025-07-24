"""Terraform integration for AutoUAM."""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from ..config.settings import Settings
from ..core.uam_manager import UAMManager
from ..logging.setup import get_logger


class TerraformProvider:
    """Terraform external data source provider."""

    def __init__(self, config: Settings):
        """Initialize Terraform provider."""
        self.config = config
        self.logger = get_logger(__name__)
        self.uam_manager: Optional[UAMManager] = None

    async def initialize(self) -> bool:
        """Initialize the provider."""
        try:
            self.uam_manager = UAMManager(self.config)
            return await self.uam_manager.initialize()
        except Exception as e:
            self.logger.error("Failed to initialize Terraform provider", error=str(e))
            return False

    async def get_zone_status(self) -> Dict[str, Any]:
        """Get zone status for Terraform."""
        if not self.uam_manager:
            if not await self.initialize():
                return {"error": "Failed to initialize provider"}
            assert self.uam_manager is not None  # initialize() sets uam_manager

        try:
            status = self.uam_manager.get_status()
            return {
                "zone_id": self.config.cloudflare.zone_id,
                "uam_enabled": status["state"]["is_enabled"],
                "load_average": status["system"]["load_average"]["normalized"],
                "last_check": status["state"]["last_check"],
                "reason": status["state"]["reason"],
            }
        except Exception as e:
            self.logger.error("Failed to get zone status", error=str(e))
            return {"error": str(e)}

    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get system metrics for Terraform."""
        if not self.uam_manager:
            if not await self.initialize():
                return {"error": "Failed to initialize provider"}
            assert self.uam_manager is not None  # initialize() sets uam_manager

        try:
            status = self.uam_manager.get_status()
            return {
                "cpu_count": status["system"]["cpu_count"],
                "load_average": {
                    "one_minute": status["system"]["load_average"]["one_minute"],
                    "five_minute": status["system"]["load_average"]["five_minute"],
                    "fifteen_minute": status["system"]["load_average"][
                        "fifteen_minute"
                    ],
                    "normalized": status["system"]["load_average"]["normalized"],
                },
                "processes": status["system"]["processes"],
                "uam_state": status["state"],
            }
        except Exception as e:
            self.logger.error("Failed to get system metrics", error=str(e))
            return {"error": str(e)}

    async def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status for Terraform external data source."""
        if not self.uam_manager:
            if not await self.initialize():
                return {"error": "Failed to initialize provider"}
            assert self.uam_manager is not None  # initialize() sets uam_manager

        try:
            status = self.uam_manager.get_status()
            return {
                "zone_id": self.config.cloudflare.zone_id,
                "uam_enabled": status["state"]["is_enabled"],
                "load_average": status["system"]["load_average"]["normalized"],
                "last_check": status["state"]["last_check"],
                "reason": status["state"]["reason"],
                "cpu_count": status["system"]["cpu_count"],
                "system_metrics": {
                    "one_minute": status["system"]["load_average"]["one_minute"],
                    "five_minute": status["system"]["load_average"]["five_minute"],
                    "fifteen_minute": status["system"]["load_average"][
                        "fifteen_minute"
                    ],
                    "normalized": status["system"]["load_average"]["normalized"],
                },
                "processes": status["system"]["processes"],
                "config": {
                    "upper_threshold": self.config.monitoring.load_thresholds.upper,
                    "lower_threshold": self.config.monitoring.load_thresholds.lower,
                    "check_interval": self.config.monitoring.check_interval,
                    "minimum_duration": self.config.monitoring.minimum_uam_duration,
                },
            }
        except Exception as e:
            self.logger.error("Failed to get status", error=str(e))
            return {"error": str(e)}

    async def execute_query(self, query: str) -> Dict[str, Any]:
        """Execute a query and return results."""
        if query == "zone_status":
            return await self.get_zone_status()
        elif query == "system_metrics":
            return await self.get_system_metrics()
        else:
            return {"error": f"Unknown query: {query}"}


def main() -> None:
    """Main entry point for Terraform external data source."""
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Usage: terraform-provider <input_file>"}))
        sys.exit(1)

    input_file = Path(sys.argv[1])

    if not input_file.exists():
        print(json.dumps({"error": f"Input file not found: {input_file}"}))
        sys.exit(1)

    try:
        # Read input from Terraform
        with open(input_file, "r") as f:
            terraform_input = json.load(f)

        # Extract configuration
        config_data = terraform_input.get("config", {})
        query = terraform_input.get("query", "zone_status")

        # Create settings from config data
        settings = Settings(**config_data)

        # Initialize provider
        provider = TerraformProvider(settings)

        # Execute query
        import asyncio

        result = asyncio.run(provider.execute_query(query))

        # Return result in Terraform format
        terraform_output = {
            "result": result,
        }

        print(json.dumps(terraform_output))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
