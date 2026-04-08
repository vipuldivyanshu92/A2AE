"""Metrics - Task 8.2: completion rate, dispute rate, settlement latency."""

import time
from dataclasses import dataclass, field


@dataclass
class Metrics:
    """In-memory metrics for v0."""

    jobs_created: int = 0
    jobs_settled: int = 0
    jobs_refunded: int = 0
    jobs_disputed: int = 0
    verification_failures: int = 0
    _settlement_latencies: list[float] = field(default_factory=list)

    @property
    def completion_rate(self) -> float:
        """Settled / (Settled + Refunded + Disputed)."""
        total = self.jobs_settled + self.jobs_refunded + self.jobs_disputed
        if total == 0:
            return 1.0
        return self.jobs_settled / total

    @property
    def dispute_rate(self) -> float:
        """Disputed / total completed."""
        total = self.jobs_settled + self.jobs_refunded + self.jobs_disputed
        if total == 0:
            return 0.0
        return self.jobs_disputed / total

    @property
    def settlement_latency_avg_ms(self) -> float:
        """Average settlement latency in ms."""
        if not self._settlement_latencies:
            return 0.0
        return sum(self._settlement_latencies) / len(self._settlement_latencies) * 1000

    def record_settlement(self, start_time: float | None = None) -> None:
        self.jobs_settled += 1
        if start_time is not None:
            self._settlement_latencies.append(time.time() - start_time)

    def record_refund(self) -> None:
        self.jobs_refunded += 1

    def record_dispute(self) -> None:
        self.jobs_disputed += 1

    def record_verification_failure(self) -> None:
        self.verification_failures += 1


_metrics = Metrics()


def get_metrics() -> Metrics:
    return _metrics
