"""AutoUAM - Automated Cloudflare Under Attack Mode management."""

__version__ = "1.0.0a5"
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
