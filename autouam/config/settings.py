"""Configuration settings for AutoUAM."""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class CloudflareConfig(BaseModel):
    """Cloudflare API configuration."""

    api_token: str
    zone_id: str
    email: str | None = None
    base_url: str = "https://api.cloudflare.com/client/v4"


class LoadThresholds(BaseModel):
    """Load average thresholds configuration."""

    upper: float = 2.0
    lower: float = 1.0
    use_relative_thresholds: bool = False
    relative_upper_multiplier: float = 2.0
    relative_lower_multiplier: float = 1.5
    baseline_calculation_hours: int = 24
    baseline_update_interval: int = 3600


class MonitoringConfig(BaseModel):
    """Monitoring configuration."""

    load_thresholds: LoadThresholds = Field(default_factory=LoadThresholds)
    check_interval: int = 60
    minimum_uam_duration: int = 300


class SecurityConfig(BaseModel):
    """Security configuration."""

    regular_mode: str = "essentially_off"


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "json"
    output: str = "file"
    file_path: str | None = "/var/log/autouam.log"
    max_size_mb: int = 100
    max_backups: int = 5


class DeploymentConfig(BaseModel):
    """Deployment configuration."""

    mode: str = "daemon"
    pid_file: str | None = "/var/run/autouam.pid"
    user: str | None = "autouam"
    group: str | None = "autouam"


class HealthConfig(BaseModel):
    """Health monitoring configuration."""

    enabled: bool = True
    port: int = 8080
    endpoint: str = "/health"
    metrics_endpoint: str = "/metrics"


class Settings(BaseSettings):
    """Main settings configuration."""

    cloudflare: CloudflareConfig
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    deployment: DeploymentConfig = Field(default_factory=DeploymentConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)

    model_config = {
        "env_prefix": "AUTOUAM_",
        "env_nested_delimiter": "__",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @classmethod
    def _substitute_env_vars(cls, data: Any) -> Any:
        """Recursively substitute environment variables in configuration data."""
        if isinstance(data, dict):
            return {k: cls._substitute_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls._substitute_env_vars(item) for item in data]
        elif isinstance(data, str) and data.startswith("${") and data.endswith("}"):
            env_var = data[2:-1]
            # Handle default values in format ${VAR:-default}
            if ":-" in env_var:
                var_name, default_value = env_var.split(":-", 1)
                return os.getenv(var_name, default_value)
            else:
                value = os.getenv(env_var)
                if value is None:
                    # Keep the original placeholder if no default and env var not set
                    return data
                return value
        else:
            return data

    @classmethod
    def from_file(cls, config_path: Path) -> "Settings":
        """Load settings from a configuration file."""
        import yaml

        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}

        # Handle environment variable substitution
        config_data = cls._substitute_env_vars(config_data)

        return cls(**config_data)

    def to_dict(self) -> dict[str, Any]:
        """Convert settings to dictionary."""
        return self.model_dump()
