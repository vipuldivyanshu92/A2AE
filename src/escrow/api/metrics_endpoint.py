"""Metrics endpoint - Task 8.2."""

from fastapi import APIRouter

from ..metrics import get_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics() -> dict:
    """Expose completion rate, dispute rate, settlement latency."""
    m = get_metrics()
    return {
        "completion_rate": m.completion_rate,
        "dispute_rate": m.dispute_rate,
        "settlement_latency_avg_ms": m.settlement_latency_avg_ms,
        "jobs_settled": m.jobs_settled,
        "jobs_refunded": m.jobs_refunded,
        "jobs_disputed": m.jobs_disputed,
        "verification_failures": m.verification_failures,
    }
