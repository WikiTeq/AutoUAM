"""Load average monitoring for AutoUAM."""

import os
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Tuple

from ..logging.setup import get_logger


@dataclass
class LoadAverage:
    """Load average data structure."""

    one_minute: float
    five_minute: float
    fifteen_minute: float
    timestamp: float

    @property
    def average(self) -> float:
        """Get the primary load average (5-minute)."""
        return self.five_minute


class LoadBaseline:
    """Calculate and maintain load average baseline."""

    def __init__(self, max_samples: int = 1440):  # 24 hours at 1-minute intervals
        self.logger = get_logger(__name__)
        self.samples: Deque[Tuple[float, float]] = deque(maxlen=max_samples)
        self.last_update: float = 0.0
        self.baseline: float | None = None

    def add_sample(self, normalized_load: float, timestamp: float) -> None:
        """Add a new load sample."""
        self.samples.append((normalized_load, timestamp))

    def calculate_baseline(self, hours: int = 24) -> float | None:
        """Calculate baseline from recent samples."""
        if not self.samples:
            return None

        # Filter samples from the last N hours
        cutoff_time = time.time() - (hours * 3600)
        recent_samples = [load for load, ts in self.samples if ts >= cutoff_time]

        if len(recent_samples) < 2:
            return None

        # Use 95th percentile as baseline (handles spikes better than mean)
        sorted_samples = sorted(recent_samples)
        index = int(len(sorted_samples) * 0.95)
        baseline = sorted_samples[min(index, len(sorted_samples) - 1)]

        self.baseline = baseline
        self.last_update = time.time()

        self.logger.info(
            f"Baseline calculated: {baseline:.2f} from {len(recent_samples)} samples"
        )
        return baseline

    def get_baseline(self) -> float | None:
        """Get current baseline value."""
        return self.baseline

    def should_update_baseline(self, interval_seconds: int) -> bool:
        """Check if baseline should be updated."""
        return time.time() - self.last_update >= interval_seconds


class LoadMonitor:
    """Monitor system load average."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.baseline = LoadBaseline()

    def get_load_average(self) -> LoadAverage:
        """Get current load average."""
        try:
            load_avgs = os.getloadavg()
            return LoadAverage(
                one_minute=load_avgs[0],
                five_minute=load_avgs[1],
                fifteen_minute=load_avgs[2],
                timestamp=time.time(),
            )
        except OSError as e:
            self.logger.error(f"Failed to get load average: {e}")
            raise

    def get_cpu_count(self) -> int:
        """Get the number of CPU cores."""
        cpu_count = os.cpu_count()
        return cpu_count if cpu_count and cpu_count > 0 else 1

    def get_normalized_load(self) -> float:
        """Get load average normalized by CPU count."""
        load_avg = self.get_load_average()
        cpu_count = self.get_cpu_count()
        normalized = load_avg.average / cpu_count

        # Add to baseline for historical tracking
        self.baseline.add_sample(normalized, load_avg.timestamp)

        return normalized

    def is_high_load(
        self,
        threshold: float,
        use_relative: bool = False,
        relative_multiplier: float = 2.0,
    ) -> bool:
        """Check if current load is above threshold."""
        normalized_load = self.get_normalized_load()

        if use_relative and (baseline := self.baseline.get_baseline()) is not None:
            threshold = baseline * relative_multiplier

        return normalized_load > threshold

    def is_low_load(
        self,
        threshold: float,
        use_relative: bool = False,
        relative_multiplier: float = 1.5,
    ) -> bool:
        """Check if current load is below threshold."""
        normalized_load = self.get_normalized_load()

        if use_relative and (baseline := self.baseline.get_baseline()) is not None:
            threshold = baseline * relative_multiplier

        return normalized_load < threshold

    def get_system_info(self) -> dict:
        """Get system information for monitoring."""
        load_avg = self.get_load_average()
        cpu_count = self.get_cpu_count()
        normalized_load = load_avg.average / cpu_count

        info = {
            "load_average": {
                "one_minute": load_avg.one_minute,
                "five_minute": load_avg.five_minute,
                "fifteen_minute": load_avg.fifteen_minute,
                "normalized": normalized_load,
            },
            "cpu_count": cpu_count,
            "timestamp": load_avg.timestamp,
        }

        if (baseline := self.baseline.get_baseline()) is not None:
            info["baseline"] = {
                "value": baseline,
                "ratio_to_baseline": normalized_load / baseline if baseline > 0 else 0,
                "samples_count": len(self.baseline.samples),
            }

        return info
