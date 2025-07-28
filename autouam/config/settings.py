"""Configuration settings for AutoUAM."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class CloudflareConfig(BaseModel):
    """Cloudflare API configuration."""

    api_token: str = Field(..., description="Cloudflare API token")
    zone_id: str = Field(..., description="Cloudflare zone ID")
    email: Optional[str] = Field(
        None, description="Cloudflare account email (for reference only)"
    )
    base_url: Optional[str] = Field(
        "https://api.cloudflare.com/client/v4",
        description="Cloudflare API base URL (for testing)",
    )

    @field_validator("api_token")
    @classmethod
    def validate_api_token(cls, v: str) -> str:
        """Validate API token format."""
        if not v or len(v) < 10:
            raise ValueError("API token must be at least 10 characters long")
        return v

    @field_validator("zone_id")
    @classmethod
    def validate_zone_id(cls, v: str) -> str:
        """Validate zone ID format."""
        if not v or len(v) < 10:
            raise ValueError("Zone ID must be at least 10 characters long")
        return v


class LoadThresholds(BaseModel):
    """Load average thresholds configuration."""

    upper: float = Field(2.0, description="Enable UAM when load > this value")
    lower: float = Field(1.0, description="Disable UAM when load < this value")

    # New relative threshold options
    use_relative_thresholds: bool = Field(
        False,
        description=(
            "Use relative thresholds based on historical baseline "
            "instead of absolute values"
        ),
    )
    relative_upper_multiplier: float = Field(
        2.0, description="Enable UAM when load > baseline * this multiplier"
    )
    relative_lower_multiplier: float = Field(
        1.5, description="Disable UAM when load < baseline * this multiplier"
    )
    baseline_calculation_hours: int = Field(
        24, description="Hours of historical data to use for baseline calculation"
    )
    baseline_update_interval: int = Field(
        3600, description="Seconds between baseline recalculations"
    )

    @field_validator("upper", "lower")
    @classmethod
    def validate_thresholds(cls, v: float) -> float:
        """Validate threshold values."""
        if v <= 0:
            raise ValueError("Thresholds must be positive")
        return v

    @field_validator("lower")
    @classmethod
    def validate_lower_threshold(cls, v: float, info: Any) -> float:
        """Ensure lower threshold is less than upper threshold."""
        # Get the upper value from the model info
        upper_value = info.data.get("upper") if info.data else None
        if upper_value is not None and v >= upper_value:
            raise ValueError("Lower threshold must be less than upper threshold")
        return v

    @field_validator("relative_upper_multiplier", "relative_lower_multiplier")
    @classmethod
    def validate_relative_multipliers(cls, v: float) -> float:
        """Validate relative multiplier values."""
        if v <= 0:
            raise ValueError("Relative multipliers must be positive")
        return v

    @field_validator("baseline_calculation_hours")
    @classmethod
    def validate_baseline_hours(cls, v: int) -> int:
        """Validate baseline calculation hours."""
        if v < 1 or v > 168:  # 1 hour to 1 week
            raise ValueError("Baseline calculation hours must be between 1 and 168")
        return v

    @field_validator("baseline_update_interval")
    @classmethod
    def validate_baseline_interval(cls, v: int) -> int:
        """Validate baseline update interval."""
        if v < 60:  # At least 1 minute
            raise ValueError("Baseline update interval must be at least 60 seconds")
        return v


class MonitoringConfig(BaseModel):
    """Monitoring configuration."""

    load_thresholds: LoadThresholds = Field(
        default_factory=LoadThresholds  # type: ignore[arg-type]
    )
    check_interval: int = Field(60, description="Check interval in seconds")
    minimum_uam_duration: int = Field(
        300, description="Minimum UAM duration in seconds"
    )

    @field_validator("check_interval")
    @classmethod
    def validate_check_interval(cls, v: int) -> int:
        """Validate check interval."""
        if v < 1:
            raise ValueError("Check interval must be at least 1 second")
        return v

    @field_validator("minimum_uam_duration")
    @classmethod
    def validate_minimum_duration(cls, v: int) -> int:
        """Validate minimum UAM duration."""
        if v < 60:
            raise ValueError("Minimum UAM duration must be at least 60 seconds")
        return v


class SecurityConfig(BaseModel):
    """Security configuration."""

    regular_mode: str = Field("essentially_off", description="Normal security level")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field("INFO", description="Log level")
    format: str = Field("json", description="Log format (json, text)")
    output: str = Field("file", description="Log output (file, stdout, syslog)")
    file_path: Optional[str] = Field(
        "/var/log/autouam.log", description="Log file path"
    )
    max_size_mb: int = Field(100, description="Maximum log file size in MB")
    max_backups: int = Field(5, description="Maximum number of log backups")

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v.upper()

    @field_validator("format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate log format."""
        valid_formats = ["json", "text"]
        if v.lower() not in valid_formats:
            raise ValueError(f"Log format must be one of: {', '.join(valid_formats)}")
        return v.lower()

    @field_validator("output")
    @classmethod
    def validate_log_output(cls, v: str) -> str:
        """Validate log output."""
        valid_outputs = ["file", "stdout", "syslog"]
        if v.lower() not in valid_outputs:
            raise ValueError(f"Log output must be one of: {', '.join(valid_outputs)}")
        return v.lower()


class DeploymentConfig(BaseModel):
    """Deployment configuration."""

    mode: str = Field("daemon", description="Deployment mode (daemon, oneshot, lambda)")
    pid_file: Optional[str] = Field("/var/run/autouam.pid", description="PID file path")
    user: Optional[str] = Field("autouam", description="User to run as")
    group: Optional[str] = Field("autouam", description="Group to run as")

    @field_validator("mode")
    @classmethod
    def validate_deployment_mode(cls, v: str) -> str:
        """Validate deployment mode."""
        valid_modes = ["daemon", "oneshot", "lambda"]
        if v.lower() not in valid_modes:
            raise ValueError(
                f"Deployment mode must be one of: {', '.join(valid_modes)}"
            )
        return v.lower()


class HealthConfig(BaseModel):
    """Health monitoring configuration."""

    enabled: bool = Field(True, description="Enable health monitoring")
    port: int = Field(8080, description="Health server port")
    endpoint: str = Field("/health", description="Health endpoint")
    metrics_endpoint: str = Field("/metrics", description="Metrics endpoint")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port number."""
        if v < 1 or v > 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


class Settings(BaseSettings):
    """Main settings configuration."""

    cloudflare: CloudflareConfig
    monitoring: MonitoringConfig = Field(
        default_factory=MonitoringConfig  # type: ignore[arg-type]
    )
    security: SecurityConfig = Field(
        default_factory=SecurityConfig  # type: ignore[arg-type]
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig  # type: ignore[arg-type]
    )
    deployment: DeploymentConfig = Field(
        default_factory=DeploymentConfig  # type: ignore[arg-type]
    )
    health: HealthConfig = Field(default_factory=HealthConfig)  # type: ignore[arg-type]

    model_config = {
        "env_prefix": "AUTOUAM_",
        "env_nested_delimiter": "__",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @classmethod
    def customise_sources(
        cls,
        init_settings: Any,
        env_settings: Any,
        file_secret_settings: Any,
    ) -> Any:
        """Customize configuration sources."""
        return (
            init_settings,
            env_settings,
            file_secret_settings,
        )

    @classmethod
    def from_file(cls, config_path: Path) -> "Settings":
        """Load settings from a configuration file."""
        import yaml

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)

        # Handle environment variable substitution
        config_data = cls._substitute_env_vars(config_data)

        return cls(**config_data)

    @staticmethod
    def _substitute_env_vars(data: Any) -> Any:
        """Recursively substitute environment variables in configuration data."""
        if isinstance(data, dict):
            return {k: Settings._substitute_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [Settings._substitute_env_vars(item) for item in data]
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return self.model_dump()

    def validate_config(self) -> None:
        """Validate all settings."""
        # Additional cross-field validation can be added here
        pass
