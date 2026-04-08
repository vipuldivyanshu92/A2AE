"""Settlement endpoint - Tasks 7.1, 7.2, 7.3."""

import asyncio

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from ..audit import AuditLogger
from ..db import get_session_factory
from ..ledger_service import LedgerService
from ..metrics import get_metrics
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


async def _deliver_callback(
    url: str,
    job_id: str,
    status: str,
    payload: dict,
    max_retries: int = 5,
) -> None:
    """
    Task 7.2, 7.3: Deliver callback with exponential backoff retries.
    """
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    json={"job_id": job_id, "status": status, **payload},
                    timeout=30.0,
                )
                if 200 <= resp.status_code < 300:
                    return
        except Exception:
            pass
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff


@router.post("/{job_id}/settle")
def settle_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    idempotency_key: str = Depends(require_idempotency_key),
) -> dict:
    """
    Task 7.1: Atomic settlement - release payment, ledger entries, idempotent.
    Task 7.2: Trigger callback to requester.
    """
    op_key = f"{idempotency_key}:settle:{job_id}"
    idem_repo = IdempotencyRepository(db)
    existing = idem_repo.get(op_key)
    if existing:
        return existing.response_json or {}

    job_repo = JobRepository(db)
    job = job_repo.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if JobStatus(job.status) != JobStatus.VERIFIED:
        raise HTTPException(400, f"Cannot settle in status {job.status}")
    if not job.hold_id:
        raise HTTPException(400, "No hold to release")

    contract = job.job_contract_json or {}
    amount = contract.get("agreed_amount", "0")
    doer_id = job.doer_id or "unknown"

    ledger = LedgerService(db)
    result = payments.release(job_id, job.hold_id, amount)
    if not result.success:
        raise HTTPException(500, "Release failed")

    ledger.record_release(job_id, amount, job.hold_id, doer_id, idempotency_key)
    job_repo.transition_status(job_id, JobStatus.SETTLED)

    audit = AuditLogger(db)
    audit.log(job_id, "settlement", "verified", "settled", {"amount": amount})
    get_metrics().record_settlement()

    response = {"status": "settled", "job_id": job_id}
    idem_repo.set(op_key, "settle", job_id, response)

    if job.callback_url:
        background_tasks.add_task(
            _deliver_callback,
            job.callback_url,
            job_id,
            "settled",
            {"amount": amount},
        )

    return response


@router.post("/{job_id}/refund")
def refund_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    idempotency_key: str = Depends(require_idempotency_key),
) -> dict:
    """Refund job - releases funds back to requester. Triggers callback."""
    op_key = f"{idempotency_key}:refund:{job_id}"
    idem_repo = IdempotencyRepository(db)
    existing = idem_repo.get(op_key)
    if existing:
        return existing.response_json or {}

    job_repo = JobRepository(db)
    job = job_repo.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if JobStatus(job.status) == JobStatus.SETTLED:
        raise HTTPException(400, "Job already settled")
    if JobStatus(job.status) == JobStatus.REFUNDED:
        raise HTTPException(400, "Job already refunded")

    if job.hold_id:
        contract = job.job_contract_json or {}
        amount = contract.get("agreed_amount", "0")
        ledger = LedgerService(db)
        result = payments.refund(job_id, job.hold_id, amount)
        if result.success:
            ledger.record_refund(
                job_id, amount, job.hold_id, job.requester_id, idempotency_key
            )

    job_repo.transition_status(job_id, JobStatus.REFUNDED)

    audit = AuditLogger(db)
    audit.log(job_id, "refund", job.status, "refunded", {})
    get_metrics().record_refund()

    response = {"status": "refunded", "job_id": job_id}
    idem_repo.set(op_key, "refund", job_id, response)

    if job.callback_url:
        background_tasks.add_task(
            _deliver_callback,
            job.callback_url,
            job_id,
            "refunded",
            {},
        )

    return response
