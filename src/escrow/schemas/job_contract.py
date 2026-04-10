"""Job Contract schema - finalized terms from handshake."""

from datetime import datetime

from pydantic import BaseModel, Field

from .job_spec import JobSpec


class JobContract(BaseModel):
    """
    Job Contract - finalized terms after doer handshake (accept/counteroffer).
    Task 1.2: Terms are immutable once NEGOTIATED.
    """

    job_id: str = Field(...)
    job_spec: JobSpec = Field(...)
    requester_id: str = Field(...)
    doer_id: str = Field(...)
    agreed_amount: str = Field(..., description="Payment amount in smallest unit")
    agreed_deadline: datetime | None = Field(None)
    callback_url: str | None = Field(None)
    dispute_policy: str = Field("refund", description="retry | arbitration | refund")
    finalized_at: datetime = Field(default_factory=datetime.utcnow)


class HandshakeAccept(BaseModel):
    """Doer accepts the Job Spec terms."""

    doer_id: str = Field(...)
    dispute_policy: str | None = Field(
        None,
        description="retry | arbitration | refund; defaults to refund if omitted or invalid",
    )


class HandshakeCounteroffer(BaseModel):
    """Doer proposes different terms."""

    doer_id: str = Field(...)
    counter_amount: str | None = Field(None)
    counter_deadline: datetime | None = Field(None)
    notes: str | None = Field(None)
    dispute_policy: str | None = Field(
        None,
        description="retry | arbitration | refund; defaults to refund if omitted or invalid",
    )
