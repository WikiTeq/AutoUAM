"""AutoUAM - Automated Cloudflare Under Attack Mode management."""

# Read version from VERSION file
try:
    with open("VERSION") as f:
        __version__ = f.read().strip()
except FileNotFoundError:
    # Fallback for when running from installed package
    __version__ = "unknown"
__author__ = "Ike Hecht"
__email__ = "contact@wikiteq.com"

from .config.settings import Settings
from .core.cloudflare import CloudflareClient
from .core.monitor import LoadMonitor
from .core.uam_manager import UAMManager

__all__ = [
    "LoadMonitor",
    "CloudflareClient",
    "UAMManager",
    "Settings",
    "__version__",
]
