"""AutoUAM - Automated Cloudflare Under Attack Mode management."""

try:
    from importlib.metadata import version

    __version__ = version("autouam")
except ImportError:
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
