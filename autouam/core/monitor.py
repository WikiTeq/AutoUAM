"""Load average monitoring for AutoUAM."""

import os
import statistics
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple

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


class LoadBaseline:
    """Calculate and maintain load average baseline."""

    def __init__(self, max_samples: int = 1440):  # 24 hours at 1-minute intervals
        """Initialize baseline calculator."""
        self.logger = get_logger(__name__)
        self.samples: deque[Tuple[float, float]] = deque(maxlen=max_samples)
        self.last_update: float = 0.0
        self.baseline: Optional[float] = None

    def add_sample(self, normalized_load: float, timestamp: float) -> None:
        """Add a new load sample."""
        self.samples.append((normalized_load, timestamp))
        self.logger.debug(
            "Added load sample", load=normalized_load, timestamp=timestamp
        )

    def calculate_baseline(self, hours: int = 24) -> Optional[float]:
        """Calculate baseline from recent samples."""
        if not self.samples:
            self.logger.warning("No samples available for baseline calculation")
            return None

        # Filter samples from the last N hours
        cutoff_time = time.time() - (hours * 3600)
        recent_samples = [load for load, ts in self.samples if ts >= cutoff_time]

        if not recent_samples:
            self.logger.warning(f"No samples in last {hours} hours for baseline")
            return None

        # Check if we have enough samples for quantile calculation
        if len(recent_samples) < 2:
            self.logger.warning("Need at least 2 samples for baseline calculation")
            return None

        # Calculate baseline as 95th percentile (to handle occasional spikes)
        # Use a smaller n value if we don't have enough samples
        n_quantiles = min(20, len(recent_samples))
        quantile_index = min(
            18, n_quantiles - 1
        )  # 95th percentile or closest available

        try:
            baseline = statistics.quantiles(recent_samples, n=n_quantiles)[
                quantile_index
            ]
        except (ValueError, IndexError) as e:
            self.logger.warning(
                f"Failed to calculate quantile: {e}, using mean instead"
            )
            baseline = statistics.mean(recent_samples)

        self.baseline = baseline
        self.last_update = time.time()

        self.logger.info(
            "Baseline calculated",
            baseline=baseline,
            samples_count=len(recent_samples),
            hours=hours,
            min_load=min(recent_samples),
            max_load=max(recent_samples),
            avg_load=statistics.mean(recent_samples),
        )

        return baseline

    def get_baseline(self) -> Optional[float]:
        """Get current baseline value."""
        return self.baseline

    def should_update_baseline(self, interval_seconds: int) -> bool:
        """Check if baseline should be updated."""
        return time.time() - self.last_update >= interval_seconds


class LoadMonitor:
    """Monitor system load average on Linux systems."""

    def __init__(self):
        """Initialize the load monitor."""
        self.logger = get_logger(__name__)
        self.baseline = LoadBaseline()
        self._validate_platform()

        # Performance caching
        self._cpu_count_cache = None
        self._cpu_count_cache_time = 0.0
        self._cpu_count_cache_ttl = 300.0  # Cache CPU count for 5 minutes

    def _validate_platform(self) -> None:
        """Validate that we're running on a supported platform."""
        import platform

        system = platform.system().lower()

        if system == "linux":
            # Check if os.getloadavg() is available (should be on Linux/Unix)
            try:
                os.getloadavg()
                self.logger.info("Load monitor initialized for Linux platform")
            except OSError:
                raise RuntimeError(
                    "Load monitoring requires a platform that supports "
                    "os.getloadavg(). This may indicate a containerized "
                    "environment or non-standard Linux distribution."
                )
        elif system == "darwin":
            # macOS supports os.getloadavg()
            try:
                os.getloadavg()
                self.logger.info("Load monitor initialized for macOS platform")
            except OSError:
                raise RuntimeError(
                    f"Load monitoring is not supported on {system}. "
                    "os.getloadavg() is not available."
                )
        elif system == "windows":
            raise RuntimeError(
                f"Load monitoring is not supported on {system}. "
                "Windows does not support os.getloadavg()."
            )
        else:
            # Try to use os.getloadavg() for other Unix-like systems
            try:
                os.getloadavg()
                self.logger.info(f"Load monitor initialized for {system} platform")
            except OSError:
                raise RuntimeError(
                    f"Load monitoring is not supported on {system}. "
                    "os.getloadavg() is not available."
                )

    def update_baseline(self, hours: int = 24) -> None:
        """Update the load baseline."""
        self.baseline.calculate_baseline(hours)

    def get_load_average(self) -> LoadAverage:
        """Get current load average using os.getloadavg()."""
        try:
            # Use os.getloadavg() which is the standard cross-platform way
            # Returns (1min, 5min, 15min) load averages
            load_avgs = os.getloadavg()
            one_minute = float(load_avgs[0])
            five_minute = float(load_avgs[1])
            fifteen_minute = float(load_avgs[2])

            # Get process counts from /proc/loadavg for additional info
            # This is optional metadata, not critical for load average
            running_processes = 0
            total_processes = 0
            last_pid = 0

            try:
                with open("/proc/loadavg", "r") as f:
                    content = f.read().strip()
                    parts = content.split()
                    if len(parts) >= 5:
                        # Process counts (running/total)
                        process_parts = parts[3].split("/")
                        if len(process_parts) == 2:
                            running_processes = int(process_parts[0])
                            total_processes = int(process_parts[1])
                        # Last PID
                        last_pid = int(parts[4])
            except (IOError, OSError, ValueError, IndexError):
                # If /proc/loadavg is not available, use defaults
                # This is fine since we already have the load averages
                # from os.getloadavg()
                pass

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

        except OSError as e:
            self.logger.error("Failed to get load average", error=str(e))
            raise

    def get_cpu_count(self) -> int:
        """Get the number of CPU cores using os.cpu_count()."""
        current_time = time.time()

        # Return cached CPU count if still valid
        if (
            self._cpu_count_cache is not None
            and current_time - self._cpu_count_cache_time < self._cpu_count_cache_ttl
        ):
            return self._cpu_count_cache

        # Use os.cpu_count() which is the standard cross-platform way
        cpu_count = os.cpu_count()

        if cpu_count is None:
            # Fallback: try /proc/cpuinfo for Linux if os.cpu_count() returns None
            try:
                with open("/proc/cpuinfo", "r") as f:
                    content = f.read()
                    cpu_count = content.count("processor")
                    if cpu_count == 0:
                        # Fallback: try to read from /proc/stat
                        with open("/proc/stat", "r") as f:
                            lines = f.readlines()
                        cpu_count = sum(
                            1
                            for line in lines
                            if line.startswith("cpu") and line != "cpu\n"
                        )
            except (IOError, OSError):
                pass

        # Final fallback if all methods fail
        if cpu_count is None or cpu_count == 0:
            self.logger.warning(
                "Failed to determine CPU count, assuming 1",
                cpu_count_from_os=os.cpu_count(),
            )
            cpu_count = 1

        # Cache the CPU count
        self._cpu_count_cache = cpu_count
        self._cpu_count_cache_time = current_time

        self.logger.debug("CPU count determined", cpu_count=cpu_count)
        return cpu_count

    def get_normalized_load(self) -> float:
        """Get load average normalized by CPU count."""
        load_avg = self.get_load_average()
        cpu_count = self.get_cpu_count()

        normalized = load_avg.average / cpu_count

        # Add to baseline for historical tracking
        self.baseline.add_sample(normalized, load_avg.timestamp)

        self.logger.debug(
            "Normalized load calculated",
            raw_load=load_avg.average,
            cpu_count=cpu_count,
            normalized_load=normalized,
        )

        return normalized

    def is_high_load(
        self,
        threshold: float,
        use_relative: bool = False,
        relative_multiplier: float = 2.0,
    ) -> bool:
        """Check if current load is above threshold."""
        normalized_load = self.get_normalized_load()

        baseline = self.baseline.get_baseline()
        if use_relative and baseline is not None:
            relative_threshold = baseline * relative_multiplier
            is_high = normalized_load > relative_threshold

            self.logger.info(
                "Relative load threshold check",
                normalized_load=normalized_load,
                baseline=baseline,
                relative_threshold=relative_threshold,
                multiplier=relative_multiplier,
                is_high=is_high,
            )
        else:
            is_high = normalized_load > threshold

            self.logger.info(
                "Absolute load threshold check",
                normalized_load=normalized_load,
                threshold=threshold,
                is_high=is_high,
            )

        return is_high

    def is_low_load(
        self,
        threshold: float,
        use_relative: bool = False,
        relative_multiplier: float = 1.5,
    ) -> bool:
        """Check if current load is below threshold."""
        normalized_load = self.get_normalized_load()

        baseline = self.baseline.get_baseline()
        if use_relative and baseline is not None:
            relative_threshold = baseline * relative_multiplier
            is_low = normalized_load < relative_threshold

            self.logger.info(
                "Relative load threshold check",
                normalized_load=normalized_load,
                baseline=baseline,
                relative_threshold=relative_threshold,
                multiplier=relative_multiplier,
                is_low=is_low,
            )
        else:
            is_low = normalized_load < threshold

            self.logger.info(
                "Absolute load threshold check",
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
            normalized_load = load_avg.average / cpu_count
            baseline = self.baseline.get_baseline()

            info = {
                "load_average": {
                    "one_minute": load_avg.one_minute,
                    "five_minute": load_avg.five_minute,
                    "fifteen_minute": load_avg.fifteen_minute,
                    "normalized": normalized_load,
                },
                "processes": {
                    "running": load_avg.running_processes,
                    "total": load_avg.total_processes,
                },
                "cpu_count": cpu_count,
                "timestamp": load_avg.timestamp,
            }

            if baseline is not None:
                info["baseline"] = {
                    "value": baseline,
                    "ratio_to_baseline": (
                        normalized_load / baseline if baseline > 0 else 0
                    ),
                    "last_update": self.baseline.last_update,
                    "samples_count": len(self.baseline.samples),
                }

            return info

        except Exception as e:
            self.logger.error("Failed to get system info", error=str(e))
            return {
                "error": str(e),
                "timestamp": time.time(),
            }
