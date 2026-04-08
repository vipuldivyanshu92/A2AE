"""Submit and verify endpoints - Tasks 6.2, 6.3, 6.4, 6.5."""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..artifact_storage import ArtifactStorage
from ..db import get_session_factory
from ..repository import JobRepository
from ..schemas.completion_packet import CompletionPacket, Deliverable, EvidenceArtifact
from ..schemas.job_spec import JobSpec
from ..state import JobStatus
from ..verification import apply_contract_policy, verify_deterministic, verify_rubric

router = APIRouter(prefix="/jobs", tags=["jobs"])
SessionLocal = get_session_factory()


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


@router.post("/{job_id}/submit")
def submit_completion(
    job_id: str,
    body: CompletionPacket,
    db: Session = Depends(get_db),
    idempotency_key: str = Depends(require_idempotency_key),
) -> dict:
    """
    Task 6.2: Submit completion packet. Stores deliverable + evidence, marks SUBMITTED.
    """
    op_key = f"{idempotency_key}:submit:{job_id}"
    from ..repository import IdempotencyRepository
    idem_repo = IdempotencyRepository(db)
    existing = idem_repo.get(op_key)
    if existing:
        return existing.response_json or {}

    job_repo = JobRepository(db)
    job = job_repo.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if JobStatus(job.status) != JobStatus.IN_PROGRESS:
        raise HTTPException(400, f"Cannot submit in status {job.status}")

    storage = ArtifactStorage(db)
    deliverable_json = body.deliverable.model_dump()
    evidence_list = [e.model_dump() for e in body.evidence]
    storage.store(job_id, deliverable_json, evidence_list)

    job_repo.transition_status(job_id, JobStatus.SUBMITTED)

    try:
        idem_repo.set(op_key, "submit", job_id, {"status": "submitted", "job_id": job_id})
    except Exception:
        db.rollback()
        raise

    return {"status": "submitted", "job_id": job_id}


@router.post("/{job_id}/verify")
def verify_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Tasks 6.3-6.5: Run verification. If pass -> VERIFIED. If fail -> apply policy.
    """
    job_repo = JobRepository(db)
    job = job_repo.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if JobStatus(job.status) != JobStatus.SUBMITTED:
        raise HTTPException(400, f"Cannot verify in status {job.status}")

    storage = ArtifactStorage(db)
    packet_model = storage.get(job_id)
    if not packet_model:
        raise HTTPException(400, "No completion packet found")

    deliverable = Deliverable(**packet_model.deliverable_json)
    evidence = [
        EvidenceArtifact(**a) for a in packet_model.evidence_json.get("artifacts", [])
    ]
    packet = CompletionPacket(deliverable=deliverable, evidence=evidence)

    spec = JobSpec(**job.job_spec_json)
    contract = job.job_contract_json or {}
    dispute_policy = contract.get("dispute_policy", "refund")

    passed, err = verify_deterministic(packet, spec)
    if not passed:
        from ..metrics import get_metrics
        get_metrics().record_verification_failure()
        action = apply_contract_policy(dispute_policy)
        return {"verified": False, "error": err, "action": action}

    if spec.evaluation_rubric:
        passed, score = verify_rubric(packet, spec.evaluation_rubric.model_dump())
        if not passed:
            from ..metrics import get_metrics
            get_metrics().record_verification_failure()
            action = apply_contract_policy(dispute_policy)
            return {"verified": False, "score": score, "action": action}

    job_repo.transition_status(job_id, JobStatus.VERIFIED)
    return {"verified": True, "job_id": job_id}
