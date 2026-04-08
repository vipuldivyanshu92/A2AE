"""Job lifecycle state machine - Task 2.1."""

from enum import Enum


class JobStatus(str, Enum):
    """Job lifecycle states per design."""

    CREATED = "created"
    NEGOTIATED = "negotiated"
    FUNDED = "funded"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    SETTLED = "settled"
    REFUNDED = "refunded"


VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.CREATED: {JobStatus.NEGOTIATED, JobStatus.REFUNDED},
    JobStatus.NEGOTIATED: {JobStatus.FUNDED, JobStatus.REFUNDED},
    JobStatus.FUNDED: {JobStatus.IN_PROGRESS, JobStatus.REFUNDED},
    JobStatus.IN_PROGRESS: {JobStatus.SUBMITTED, JobStatus.REFUNDED},
    JobStatus.SUBMITTED: {JobStatus.VERIFIED, JobStatus.REFUNDED},
    JobStatus.VERIFIED: {JobStatus.SETTLED},
    JobStatus.SETTLED: set(),
    JobStatus.REFUNDED: set(),
}


def can_transition(from_status: JobStatus, to_status: JobStatus) -> bool:
    """Validate state transition."""
    return to_status in VALID_TRANSITIONS.get(from_status, set())


def transition(from_status: JobStatus, to_status: JobStatus) -> JobStatus:
    """Return new status or raise if invalid."""
    if not can_transition(from_status, to_status):
        raise ValueError(
            f"Invalid transition: {from_status.value} -> {to_status.value}"
        )
    return to_status
