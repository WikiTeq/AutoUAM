"""AutoUAM - Automated Cloudflare Under Attack Mode management."""

__version__ = "0.1.0"
__author__ = "AutoUAM Team"
__email__ = "admin@example.com"

from .core.monitor import LoadMonitor
from .core.cloudflare import CloudflareClient
from .core.uam_manager import UAMManager
from .config.settings import Settings

__all__ = [
    "LoadMonitor",
    "CloudflareClient",
    "UAMManager",
    "Settings",
    "__version__",
]
