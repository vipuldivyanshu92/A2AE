"""Payments adapter interface - Task 4.1."""

from abc import ABC, abstractmethod


class HoldResult:
    """Result of hold operation."""

    def __init__(self, hold_id: str, success: bool = True) -> None:
        self.hold_id = hold_id
        self.success = success


class ReleaseResult:
    """Result of release operation."""

    def __init__(self, success: bool = True) -> None:
        self.success = success


class RefundResult:
    """Result of refund operation."""

    def __init__(self, success: bool = True) -> None:
        self.success = success


class PaymentsAdapter(ABC):
    """Abstract payments adapter - hold, release, refund."""

    @abstractmethod
    def hold(self, job_id: str, amount: str, currency: str = "default") -> HoldResult:
        """Create escrow hold."""
        ...

    @abstractmethod
    def release(self, job_id: str, hold_id: str, amount: str) -> ReleaseResult:
        """Release funds from hold to doer."""
        ...

    @abstractmethod
    def refund(self, job_id: str, hold_id: str, amount: str) -> RefundResult:
        """Refund funds to requester."""
        ...
