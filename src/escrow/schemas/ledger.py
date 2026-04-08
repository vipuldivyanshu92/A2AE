"""Ledger entry schema for holds, releases, refunds, fees."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class LedgerEntryType(str, Enum):
    """Task 1.4: Ledger entry types."""

    HOLD = "hold"
    RELEASE = "release"
    REFUND = "refund"
    FEE = "fee"


class LedgerEntry(BaseModel):
    """
    Double-entry ledger entry.
    Task 1.4: Schema for holds, releases, refunds, and fees.
    """

    entry_id: str = Field(...)
    job_id: str = Field(...)
    entry_type: LedgerEntryType = Field(...)
    amount: str = Field(..., description="Amount in smallest unit")
    currency: str = Field("default")
    debit_account: str = Field(...)
    credit_account: str = Field(...)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reference: str | None = Field(None)
    idempotency_key: str | None = Field(None)
