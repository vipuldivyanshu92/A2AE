"""Fund endpoint - Task 4.3, 4.4."""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session_factory
from ..ledger_service import LedgerService
from ..payments import MockedPaymentsAdapter
from ..repository import IdempotencyRepository, JobRepository
from ..state import JobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])
SessionLocal = get_session_factory()
payments = MockedPaymentsAdapter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_idempotency_key(
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> str:
    if not idempotency_key:
        raise HTTPException(400, "Idempotency-Key header required")
    return idempotency_key


@router.post("/{job_id}/fund")
def fund_job(
    job_id: str,
    db: Session = Depends(get_db),
    idempotency_key: str = Depends(require_idempotency_key),
) -> dict:
    """
    Task 4.3: Fund escrow. Creates hold and ledger entry.
    Only allowed when job is NEGOTIATED.
    """
    op_key = f"{idempotency_key}:fund:{job_id}"
    idem_repo = IdempotencyRepository(db)
    existing = idem_repo.get(op_key)
    if existing:
        return existing.response_json or {}

    job_repo = JobRepository(db)
    job = job_repo.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if JobStatus(job.status) != JobStatus.NEGOTIATED:
        raise HTTPException(400, f"Cannot fund job in status {job.status}")
    if not job.job_contract_json:
        raise HTTPException(400, "Terms not finalized; complete handshake first")

    contract = job.job_contract_json
    amount = contract.get("agreed_amount", "0")

    result = payments.hold(job_id, amount)
    if not result.success:
        raise HTTPException(500, "Hold failed")

    ledger = LedgerService(db)
    ledger.record_hold(job_id, amount, result.hold_id, idempotency_key)

    job_repo.update_hold_id(job_id, result.hold_id)
    job_repo.transition_status(job_id, JobStatus.FUNDED)

    response = {"status": "funded", "job_id": job_id}
    try:
        idem_repo.set(op_key, "fund", job_id, response)
    except Exception:
        db.rollback()
        raise

    return response
