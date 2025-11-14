"""AutoUAM - Automated Cloudflare Under Attack Mode management."""


# Read version from package metadata or VERSION file
def _get_package_version() -> str:
    """Get package version from metadata or VERSION file."""
    # Try importlib.metadata (Python 3.8+)
    try:
        from importlib.metadata import version

        return version("autouam")
    except ImportError:
        # Fallback to importlib_metadata backport for older Python 3.8 installations
        try:
            from importlib_metadata import version  # type: ignore[no-redef]

            return version("autouam")
        except ImportError:
            # Fallback to VERSION file for development
            try:
                with open("VERSION") as f:
                    return f.read().strip()
            except FileNotFoundError:
                return "unknown"


__version__ = _get_package_version()
__author__ = "Ike Hecht"
__email__ = "contact@wikiteq.com"

# Imports must come after __version__ to avoid circular dependencies
from .config.settings import Settings  # noqa: E402
from .core.cloudflare import CloudflareClient  # noqa: E402
from .core.monitor import LoadMonitor  # noqa: E402
from .core.uam_manager import UAMManager  # noqa: E402

__all__ = [
    "LoadMonitor",
    "CloudflareClient",
    "UAMManager",
    "Settings",
    "__version__",
]
