"""AutoUAM - Automated Cloudflare Under Attack Mode management."""

__version__ = "0.1.0"
__author__ = "AutoUAM Team"
__email__ = "admin@example.com"

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
