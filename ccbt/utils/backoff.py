"""Backoff utilities for retry policies."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class ExponentialBackoff:
    """Simple exponential backoff with optional jitter."""

    base_delay: float = 1.0
    multiplier: float = 2.0
    max_delay: float = 60.0
    jitter: float = 0.1 

    def next_delay(self, retries: int) -> float:
        """Calculate the next delay for given retry count (0-based)."""
        delay = self.base_delay * (self.multiplier ** max(0, retries))
        delay = min(delay, self.max_delay)
        if self.jitter > 0:
            jitter_amt = delay * self.jitter
            delay = max(0.0, delay - jitter_amt) + random.random() * (2 * jitter_amt)
        return delay
