"""CLI commands for AutoUAM."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from ..config.settings import Settings
from ..config.validators import (
    generate_sample_config,
    validate_config,
    validate_config_file,
)
from ..core.uam_manager import UAMManager
from ..health.checks import HealthChecker
from ..health.server import HealthServer
from ..logging.setup import get_logger, setup_logging

console = Console()


def print_error(message: str) -> None:
    """Print error message."""
    console.print(f"[red]Error: {message}[/red]")


def print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[green]✓ {message}[/green]")


def print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[yellow]⚠ {message}[/yellow]")


def print_info(message: str) -> None:
    """Print info message."""
    console.print(f"[blue]ℹ {message}[/blue]")


@click.group()
@click.version_option(version="1.0.0a2", prog_name="autouam")
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Configuration file path"
)
@click.option(
    "--log-level",
    "-l",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Log level",
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without executing"
)
@click.option(
    "--format",
    type=click.Choice(["json", "yaml", "text"]),
    default="text",
    help="Output format",
)
@click.option("--quiet", "-q", is_flag=True, help="Suppress output")
@click.option("--verbose", "-V", is_flag=True, help="Verbose output")
@click.pass_context
def main(
    ctx: click.Context,
    config: Optional[str],
    log_level: str,
    dry_run: bool,
    format: str,
    quiet: bool,
    verbose: bool,
) -> None:
    """AutoUAM - Automated Cloudflare Under Attack Mode management."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["log_level"] = log_level
    ctx.obj["dry_run"] = dry_run
    ctx.obj["format"] = format
    ctx.obj["quiet"] = quiet
    ctx.obj["verbose"] = verbose

    # Setup logging
    if config:
        try:
            settings = Settings.from_file(Path(config))
            setup_logging(settings.logging)
        except Exception as e:
            print_error(f"Failed to load configuration: {e}")
            sys.exit(1)
    else:
        # Use basic logging setup
        from ..config.settings import LoggingConfig

        logging_config = LoggingConfig(
            level=log_level,
            output="stdout",
            format="text",
            file_path="/var/log/autouam.log",
            max_size_mb=100,
            max_backups=5,
        )
        setup_logging(logging_config)


@main.command()
@click.option(
    "--config", "-c", type=click.Path(), required=True, help="Configuration file path"
)
@click.pass_context
def daemon(ctx: click.Context, config: str) -> None:
    """Run AutoUAM as a daemon."""
    config_path = Path(config)

    if not config_path.exists():
        print_error(f"Configuration file not found: {config}")
        sys.exit(1)

    try:
        settings = Settings.from_file(config_path)
        setup_logging(settings.logging)

        logger = get_logger(__name__)
        logger.info("Starting AutoUAM daemon")

        # Validate configuration
        errors = validate_config(settings)
        if errors:
            for error in errors:
                print_error(error)
            sys.exit(1)

        # Create and run UAM manager
        async def run_daemon():
            uam_manager = UAMManager(settings)

            # Start health server if enabled
            health_server = None
            if settings.health.enabled:
                health_checker = HealthChecker(settings)
                await health_checker.initialize()
                health_server = HealthServer(settings, health_checker)
                await health_server.start()
                logger.info("Health server started")

            try:
                await uam_manager.run()
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, shutting down")
            finally:
                uam_manager.stop()
                if health_server:
                    await health_server.stop()
                logger.info("AutoUAM daemon stopped")

        asyncio.run(run_daemon())

    except Exception as e:
        print_error(f"Failed to start daemon: {e}")
        sys.exit(1)


@main.command()
@click.option("--config", "-c", type=click.Path(), help="Configuration file path")
@click.pass_context
def check(ctx: click.Context, config: Optional[str]) -> None:
    """Perform a one-time check."""
    config_path = Path(config) if config else None

    try:
        if config_path and config_path.exists():
            settings = Settings.from_file(config_path)
        else:
            # Use environment variables
            settings = Settings()  # type: ignore[call-arg]

        setup_logging(settings.logging)

        async def run_check():
            uam_manager = UAMManager(settings)
            if not await uam_manager.initialize():
                print_error("Failed to initialize UAM manager")
                sys.exit(1)

            result = await uam_manager.check_once()

            if ctx.obj["format"] == "json":
                console.print(json.dumps(result, indent=2))
            elif ctx.obj["format"] == "yaml":
                console.print(yaml.dump(result, default_flow_style=False))
            else:
                display_status(result)

        asyncio.run(run_check())

    except Exception as e:
        print_error(f"Check failed: {e}")
        sys.exit(1)


@main.command()
@click.option("--config", "-c", type=click.Path(), help="Configuration file path")
@click.pass_context
def enable(ctx: click.Context, config: Optional[str]) -> None:
    """Manually enable Under Attack Mode."""
    config_path = Path(config) if config else None

    try:
        if config_path and config_path.exists():
            settings = Settings.from_file(config_path)
        else:
            print_error("Configuration file is required for this command")
            sys.exit(1)

        setup_logging(settings.logging)

        async def run_enable():
            uam_manager = UAMManager(settings)
            if not await uam_manager.initialize():
                print_error("Failed to initialize UAM manager")
                sys.exit(1)

            success = await uam_manager.enable_uam_manual()

            if success:
                print_success("Under Attack Mode enabled")
            else:
                print_error("Failed to enable Under Attack Mode")
                sys.exit(1)

        asyncio.run(run_enable())

    except Exception as e:
        print_error(f"Enable failed: {e}")
        sys.exit(1)


@main.command()
@click.option("--config", "-c", type=click.Path(), help="Configuration file path")
@click.pass_context
def disable(ctx: click.Context, config: Optional[str]) -> None:
    """Manually disable Under Attack Mode."""
    config_path = Path(config) if config else None

    try:
        if config_path and config_path.exists():
            settings = Settings.from_file(config_path)
        else:
            print_error("Configuration file is required for this command")
            sys.exit(1)

        setup_logging(settings.logging)

        async def run_disable():
            uam_manager = UAMManager(settings)
            if not await uam_manager.initialize():
                print_error("Failed to initialize UAM manager")
                sys.exit(1)

            success = await uam_manager.disable_uam_manual()

            if success:
                print_success("Under Attack Mode disabled")
            else:
                print_error("Failed to disable Under Attack Mode")
                sys.exit(1)

        asyncio.run(run_disable())

    except Exception as e:
        print_error(f"Disable failed: {e}")
        sys.exit(1)


@main.command()
@click.option("--config", "-c", type=click.Path(), help="Configuration file path")
@click.pass_context
def status(ctx: click.Context, config: Optional[str]) -> None:
    """Show current status."""
    config_path = Path(config) if config else None

    try:
        if config_path and config_path.exists():
            settings = Settings.from_file(config_path)
        else:
            print_error("Configuration file is required for this command")
            sys.exit(1)

        setup_logging(settings.logging)

        async def run_status():
            uam_manager = UAMManager(settings)
            if not await uam_manager.initialize():
                print_error("Failed to initialize UAM manager")
                sys.exit(1)

            result = uam_manager.get_status()

            if ctx.obj["format"] == "json":
                console.print(json.dumps(result, indent=2))
            elif ctx.obj["format"] == "yaml":
                console.print(yaml.dump(result, default_flow_style=False))
            else:
                display_status(result)

        asyncio.run(run_status())

    except Exception as e:
        print_error(f"Status check failed: {e}")
        sys.exit(1)


@main.group()
def config() -> None:
    """Configuration management commands."""
    pass


@config.command()
@click.argument("config_path", type=click.Path())
@click.pass_context
def validate(ctx: click.Context, config_path: str) -> None:
    """Validate configuration file."""
    path = Path(config_path)

    if not path.exists():
        print_error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    errors = validate_config_file(path)

    if errors:
        print_error("Configuration validation failed:")
        for error in errors:
            print_error(f"  - {error}")
        sys.exit(1)
    else:
        print_success("Configuration is valid")


@config.command()
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.pass_context
def generate(ctx: click.Context, output: Optional[str]) -> None:
    """Generate sample configuration."""
    sample_config = generate_sample_config()

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            yaml.dump(sample_config, f, default_flow_style=False, indent=2)

        print_success(f"Sample configuration written to {output}")
    else:
        if ctx.obj["format"] == "json":
            console.print(json.dumps(sample_config, indent=2))
        elif ctx.obj["format"] == "yaml":
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
@click.option("--config", "-c", type=click.Path(), help="Configuration file path")
@click.pass_context
def show(ctx: click.Context, config: Optional[str]) -> None:
    """Show current configuration."""
    try:
        if config:
            settings = Settings.from_file(Path(config))
        else:
            print_error("Configuration file is required for this command")
            sys.exit(1)

        config_dict = settings.to_dict()

        if ctx.obj["format"] == "json":
            console.print(json.dumps(config_dict, indent=2))
        elif ctx.obj["format"] == "yaml":
            console.print(yaml.dump(config_dict, default_flow_style=False))
        else:
            console.print(
                Panel(
                    yaml.dump(config_dict, default_flow_style=False),
                    title="Current Configuration",
                    border_style="green",
                )
            )

    except Exception as e:
        print_error(f"Failed to show configuration: {e}")
        sys.exit(1)


@main.group()
def health() -> None:
    """Health monitoring commands."""
    pass


@health.command()
@click.option("--config", "-c", type=click.Path(), help="Configuration file path")
@click.pass_context
def health_check(ctx: click.Context, config: Optional[str]) -> None:
    """Perform health check."""
    config_path = Path(config) if config else None

    try:
        if config_path and config_path.exists():
            settings = Settings.from_file(config_path)
        else:
            print_error("Configuration file is required for this command")
            sys.exit(1)

        setup_logging(settings.logging)

        async def run_health_check():
            health_checker = HealthChecker(settings)
            await health_checker.initialize()

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Performing health check...", total=None)
                result = await health_checker.check_health()
                progress.update(task, completed=True)

            if ctx.obj["format"] == "json":
                console.print(json.dumps(result, indent=2))
            elif ctx.obj["format"] == "yaml":
                console.print(yaml.dump(result, default_flow_style=False))
            else:
                display_health_result(result)

        asyncio.run(run_health_check())

    except Exception as e:
        print_error(f"Health check failed: {e}")
        sys.exit(1)


@health.command()
@click.option("--config", "-c", type=click.Path(), help="Configuration file path")
@click.pass_context
def metrics(ctx: click.Context, config: Optional[str]) -> None:
    """Show metrics."""
    config_path = Path(config) if config else None

    try:
        if config_path and config_path.exists():
            settings = Settings.from_file(config_path)
        else:
            print_error("Configuration file is required for this command")
            sys.exit(1)

        setup_logging(settings.logging)

        async def run_metrics():
            health_checker = HealthChecker(settings)
            await health_checker.initialize()

            metrics_data = health_checker.get_metrics()
            console.print(metrics_data)

        asyncio.run(run_metrics())

    except Exception as e:
        print_error(f"Failed to get metrics: {e}")
        sys.exit(1)


def display_status(result: dict) -> None:
    """Display status in a formatted table."""
    if "error" in result:
        print_error(result["error"])
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

        if "processes" in system:
            processes = system["processes"]
            system_table.add_row("Running Processes", str(processes["running"]))
            system_table.add_row("Total Processes", str(processes["total"]))

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


def display_health_result(result: dict) -> None:
    """Display health check result."""
    if result["healthy"]:
        print_success("Health check passed")
    else:
        print_error("Health check failed")

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
