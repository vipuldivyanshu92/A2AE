"""Mocked payments adapter for v0 - Task 4.1."""

import uuid

from .adapter import HoldResult, PaymentsAdapter, RefundResult, ReleaseResult


class MockedPaymentsAdapter(PaymentsAdapter):
    """In-memory mocked implementation."""

    def __init__(self) -> None:
        self._holds: dict[str, dict] = {}

    def hold(self, job_id: str, amount: str, currency: str = "default") -> HoldResult:
        hold_id = str(uuid.uuid4())
        self._holds[hold_id] = {"job_id": job_id, "amount": amount, "currency": currency}
        return HoldResult(hold_id=hold_id)

    def release(self, job_id: str, hold_id: str, amount: str) -> ReleaseResult:
        if hold_id in self._holds and self._holds[hold_id]["job_id"] == job_id:
            del self._holds[hold_id]
        return ReleaseResult()

    def refund(self, job_id: str, hold_id: str, amount: str) -> RefundResult:
        if hold_id in self._holds and self._holds[hold_id]["job_id"] == job_id:
            del self._holds[hold_id]
        return RefundResult()
