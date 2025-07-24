"""Load average monitoring for AutoUAM."""

import os
import time
from dataclasses import dataclass

from ..logging.setup import get_logger


@dataclass
class LoadAverage:
    """Load average data structure."""

    one_minute: float
    five_minute: float
    fifteen_minute: float
    running_processes: int
    total_processes: int
    last_pid: int
    timestamp: float

    @property
    def average(self) -> float:
        """Get the primary load average (5-minute)."""
        return self.five_minute


class LoadMonitor:
    """Monitor system load average on Linux systems."""

    def __init__(self):
        """Initialize the load monitor."""
        self.logger = get_logger(__name__)
        self._validate_platform()

    def _validate_platform(self) -> None:
        """Validate that we're running on a supported platform."""
        if not os.path.exists("/proc/loadavg"):
            raise RuntimeError("Load monitoring requires Linux with /proc/loadavg")

        self.logger.info("Load monitor initialized for Linux platform")

    def get_load_average(self) -> LoadAverage:
        """Get current load average from /proc/loadavg."""
        try:
            with open("/proc/loadavg", "r") as f:
                content = f.read().strip()

            # Parse /proc/loadavg format: "1.23 4.56 7.89 12/34 56789"
            parts = content.split()

            if len(parts) < 5:
                raise ValueError(f"Invalid /proc/loadavg format: {content}")

            # Load averages (1min, 5min, 15min)
            one_minute = float(parts[0])
            five_minute = float(parts[1])
            fifteen_minute = float(parts[2])

            # Process counts (running/total)
            process_parts = parts[3].split("/")
            if len(process_parts) != 2:
                raise ValueError(f"Invalid process count format: {parts[3]}")

            running_processes = int(process_parts[0])
            total_processes = int(process_parts[1])

            # Last PID
            last_pid = int(parts[4])

            load_avg = LoadAverage(
                one_minute=one_minute,
                five_minute=five_minute,
                fifteen_minute=fifteen_minute,
                running_processes=running_processes,
                total_processes=total_processes,
                last_pid=last_pid,
                timestamp=time.time(),
            )

            self.logger.debug(
                "Load average retrieved",
                one_minute=one_minute,
                five_minute=five_minute,
                fifteen_minute=fifteen_minute,
                running_processes=running_processes,
                total_processes=total_processes,
            )

            return load_avg

        except (IOError, OSError) as e:
            self.logger.error("Failed to read /proc/loadavg", error=str(e))
            raise
        except (ValueError, IndexError) as e:
            self.logger.error("Failed to parse /proc/loadavg", error=str(e))
            raise

    def get_cpu_count(self) -> int:
        """Get the number of CPU cores."""
        try:
            with open("/proc/cpuinfo", "r") as f:
                content = f.read()

            # Count processor entries
            cpu_count = content.count("processor")

            if cpu_count == 0:
                # Fallback: try to read from /proc/stat
                with open("/proc/stat", "r") as f:
                    lines = f.readlines()

                cpu_count = sum(
                    1 for line in lines if line.startswith("cpu") and line != "cpu\n"
                )

            self.logger.debug("CPU count determined", cpu_count=cpu_count)
            return cpu_count

        except (IOError, OSError) as e:
            self.logger.warning(
                "Failed to determine CPU count, assuming 1", error=str(e)
            )
            return 1

    def get_normalized_load(self) -> float:
        """Get load average normalized by CPU count."""
        load_avg = self.get_load_average()
        cpu_count = self.get_cpu_count()

        normalized = load_avg.average / cpu_count

        self.logger.debug(
            "Normalized load calculated",
            raw_load=load_avg.average,
            cpu_count=cpu_count,
            normalized_load=normalized,
        )

        return normalized

    def is_high_load(self, threshold: float) -> bool:
        """Check if current load is above threshold."""
        normalized_load = self.get_normalized_load()
        is_high = normalized_load > threshold

        self.logger.info(
            "Load threshold check",
            normalized_load=normalized_load,
            threshold=threshold,
            is_high=is_high,
        )

        return is_high

    def is_low_load(self, threshold: float) -> bool:
        """Check if current load is below threshold."""
        normalized_load = self.get_normalized_load()
        is_low = normalized_load < threshold

        self.logger.info(
            "Load threshold check",
            normalized_load=normalized_load,
            threshold=threshold,
            is_low=is_low,
        )

        return is_low

    def get_system_info(self) -> dict:
        """Get system information for monitoring."""
        try:
            load_avg = self.get_load_average()
            cpu_count = self.get_cpu_count()

            return {
                "load_average": {
                    "one_minute": load_avg.one_minute,
                    "five_minute": load_avg.five_minute,
                    "fifteen_minute": load_avg.fifteen_minute,
                    "normalized": load_avg.average / cpu_count,
                },
                "processes": {
                    "running": load_avg.running_processes,
                    "total": load_avg.total_processes,
                },
                "cpu_count": cpu_count,
                "timestamp": load_avg.timestamp,
            }

        except Exception as e:
            self.logger.error("Failed to get system info", error=str(e))
            return {
                "error": str(e),
                "timestamp": time.time(),
            }
