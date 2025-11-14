"""CLI commands for AutoUAM."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .. import __version__
from ..config.settings import Settings
from ..config.validators import generate_sample_config, validate_config_file
from ..core.uam_manager import UAMManager
from ..health.checks import HealthChecker
from ..health.server import HealthServer
from ..logging.setup import setup_logging

console = Console()

# Global state
_settings: Settings | None = None
_output_format: str = "text"


@click.group()
@click.version_option(version=__version__, prog_name="autouam")
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Configuration file path"
)
@click.option(
    "--log-level",
    "-l",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
)
@click.option("--format", type=click.Choice(["json", "yaml", "text"]), default="text")
def main(config: str | None, log_level: str, format: str) -> None:
    """AutoUAM - Automated Cloudflare Under Attack Mode management."""
    global _settings, _output_format
    _settings = None
    _output_format = format

    if config:
        try:
            _settings = Settings.from_file(Path(config))
            setup_logging(_settings.logging)
        except Exception as e:
            console.print(f"[red]Error: Failed to load configuration: {e}[/red]")
            sys.exit(1)
    else:
        # Basic logging setup
        from ..config.settings import LoggingConfig

        logging_config = LoggingConfig(level=log_level, output="stdout", format="text")
        setup_logging(logging_config)


@main.command()
def daemon() -> None:
    """Run AutoUAM as a daemon."""
    if not _settings:
        console.print(
            "[red]Error: Configuration file is required for daemon mode[/red]"
        )
        sys.exit(1)

    async def run_daemon() -> None:
        uam_manager = UAMManager(_settings)

        # Start health server if enabled
        health_server = None
        if _settings.health.enabled:
            health_checker = HealthChecker(_settings)
            await health_checker.initialize()
            health_server = HealthServer(_settings, health_checker)
            await health_server.start()

        try:
            await uam_manager.run()
        except KeyboardInterrupt:
            console.print("Shutting down...")
        finally:
            uam_manager.stop()
            if health_server:
                await health_server.stop()

    asyncio.run(run_daemon())


@main.command()
def check() -> None:
    """Perform a one-time check."""
    if not _settings:
        console.print("[red]Error: Configuration file is required[/red]")
        sys.exit(1)

    async def run_check() -> None:
        uam_manager = UAMManager(_settings)
        try:
            result = await uam_manager.check_once()
            if _output_format == "json":
                console.print(json.dumps(result, indent=2))
            elif _output_format == "yaml":
                console.print(yaml.dump(result, default_flow_style=False))
            else:
                display_status(result)
        finally:
            uam_manager.stop()

    asyncio.run(run_check())


@main.command()
def enable() -> None:
    """Manually enable Under Attack Mode."""
    if not _settings:
        console.print("[red]Error: Configuration file is required[/red]")
        sys.exit(1)

    async def run_enable() -> None:
        uam_manager = UAMManager(_settings)
        try:
            success = await uam_manager.enable_uam_manual()
            if success:
                console.print("[green]✓ Under Attack Mode enabled[/green]")
            else:
                console.print("[red]✗ Failed to enable Under Attack Mode[/red]")
                sys.exit(1)
        finally:
            uam_manager.stop()

    asyncio.run(run_enable())


@main.command()
def disable() -> None:
    """Manually disable Under Attack Mode."""
    if not _settings:
        console.print("[red]Error: Configuration file is required[/red]")
        sys.exit(1)

    async def run_disable() -> None:
        uam_manager = UAMManager(_settings)
        try:
            success = await uam_manager.disable_uam_manual()
            if success:
                console.print("[green]✓ Under Attack Mode disabled[/green]")
            else:
                console.print("[red]✗ Failed to disable Under Attack Mode[/red]")
                sys.exit(1)
        finally:
            uam_manager.stop()

    asyncio.run(run_disable())


@main.command()
def status() -> None:
    """Show current status."""
    if not _settings:
        console.print("[red]Error: Configuration file is required[/red]")
        sys.exit(1)

    async def run_status() -> None:
        uam_manager = UAMManager(_settings)
        try:
            result = uam_manager.get_status()
            if _output_format == "json":
                console.print(json.dumps(result, indent=2))
            elif _output_format == "yaml":
                console.print(yaml.dump(result, default_flow_style=False))
            else:
                display_status(result)
        finally:
            uam_manager.stop()

    asyncio.run(run_status())


@main.group()
def config() -> None:
    """Configuration management commands."""
    pass


@config.command()
@click.argument("config_path", type=click.Path())
def validate(config_path: str) -> None:
    """Validate configuration file."""
    path = Path(config_path)
    if not path.exists():
        console.print(f"[red]Error: Configuration file not found: {config_path}[/red]")
        sys.exit(1)

    errors = validate_config_file(path)
    if errors:
        console.print("[red]Configuration validation failed:[/red]")
        for error in errors:
            console.print(f"[red]  - {error}[/red]")
        sys.exit(1)
    else:
        console.print("[green]✓ Configuration is valid[/green]")


@config.command()
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def generate(output: str | None) -> None:
    """Generate sample configuration."""
    sample_config = generate_sample_config()

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            yaml.dump(sample_config, f, default_flow_style=False, indent=2)
        console.print(f"[green]✓ Sample configuration written to {output}[/green]")
    else:
        if _output_format == "json":
            console.print(json.dumps(sample_config, indent=2))
        elif _output_format == "yaml":
            console.print(yaml.dump(sample_config, default_flow_style=False))
        else:
            console.print(
                Panel(
                    yaml.dump(sample_config, default_flow_style=False),
                    title="Sample Configuration",
                    border_style="blue",
                )
            )


@config.command()
def show() -> None:
    """Show current configuration."""
    if not _settings:
        console.print("[red]Error: Configuration file is required[/red]")
        sys.exit(1)

    config_dict = _settings.to_dict()
    if _output_format == "json":
        console.print(json.dumps(config_dict, indent=2))
    elif _output_format == "yaml":
        console.print(yaml.dump(config_dict, default_flow_style=False))
    else:
        console.print(
            Panel(
                yaml.dump(config_dict, default_flow_style=False),
                title="Current Configuration",
                border_style="green",
            )
        )


@main.group()
def health() -> None:
    """Health monitoring commands."""
    pass


@health.command(name="check")
def health_check() -> None:
    """Perform health check."""
    if not _settings:
        console.print("[red]Error: Configuration file is required[/red]")
        sys.exit(1)

    async def run_health_check() -> None:
        health_checker = HealthChecker(_settings)
        await health_checker.initialize()
        result = await health_checker.check_health()

        if _output_format == "json":
            console.print(json.dumps(result, indent=2))
        elif _output_format == "yaml":
            console.print(yaml.dump(result, default_flow_style=False))
        else:
            display_health_result(result)

    asyncio.run(run_health_check())


@health.command()
def metrics() -> None:
    """Show metrics."""
    if not _settings:
        console.print("[red]Error: Configuration file is required[/red]")
        sys.exit(1)

    async def run_metrics() -> None:
        health_checker = HealthChecker(_settings)
        await health_checker.initialize()
        metrics_data = health_checker.get_metrics()
        console.print(metrics_data)

    asyncio.run(run_metrics())


def display_status(result: dict[str, Any]) -> None:
    """Display status in a formatted table."""
    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        return

    # System information
    system_table = Table(title="System Information")
    system_table.add_column("Metric", style="cyan")
    system_table.add_column("Value", style="white")

    if "system" in result:
        system = result["system"]
        if "load_average" in system:
            load = system["load_average"]
            system_table.add_row("Load Average (1min)", f"{load['one_minute']:.2f}")
            system_table.add_row("Load Average (5min)", f"{load['five_minute']:.2f}")
            system_table.add_row(
                "Load Average (15min)", f"{load['fifteen_minute']:.2f}"
            )
            system_table.add_row("Normalized Load", f"{load['normalized']:.2f}")

        if "cpu_count" in system:
            system_table.add_row("CPU Count", str(system["cpu_count"]))

    console.print(system_table)

    # UAM State
    state_table = Table(title="UAM State")
    state_table.add_column("Property", style="cyan")
    state_table.add_column("Value", style="white")

    if "state" in result:
        state = result["state"]
        status_text = "Enabled" if state["is_enabled"] else "Disabled"
        status_style = "red" if state["is_enabled"] else "green"

        state_table.add_row("Status", Text(status_text, style=status_style))
        state_table.add_row("Last Check", str(state["last_check"]))
        state_table.add_row("Load Average", f"{state['load_average']:.2f}")
        state_table.add_row("Threshold Used", f"{state['threshold_used']:.2f}")
        state_table.add_row("Reason", state["reason"])

        if state["current_duration"]:
            state_table.add_row("Current Duration", f"{state['current_duration']:.0f}s")

    console.print(state_table)

    # Configuration
    config_table = Table(title="Configuration")
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value", style="white")

    if "config" in result:
        config = result["config"]
        config_table.add_row("Upper Threshold", f"{config['upper_threshold']:.1f}")
        config_table.add_row("Lower Threshold", f"{config['lower_threshold']:.1f}")
        config_table.add_row("Check Interval", f"{config['check_interval']}s")
        config_table.add_row("Minimum Duration", f"{config['minimum_duration']}s")

    console.print(config_table)


def display_health_result(result: dict[str, Any]) -> None:
    """Display health check result."""
    if result["healthy"]:
        console.print("[green]✓ Health check passed[/green]")
    else:
        console.print("[red]✗ Health check failed[/red]")

    console.print(f"Status: {result['status']}")
    console.print(f"Duration: {result['duration']:.3f}s")

    if "checks" in result:
        checks_table = Table(title="Health Checks")
        checks_table.add_column("Check", style="cyan")
        checks_table.add_column("Status", style="white")
        checks_table.add_column("Details", style="white")

        for check_name, check_result in result["checks"].items():
            status = "✓" if check_result.get("healthy", False) else "✗"
            status_style = "green" if check_result.get("healthy", False) else "red"
            details = check_result.get("status", "")

            checks_table.add_row(
                check_name.replace("_", " ").title(),
                Text(status, style=status_style),
                details,
            )

        console.print(checks_table)


if __name__ == "__main__":
    main()
