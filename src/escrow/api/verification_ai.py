"""
AI Verification Engine endpoints (HW8).

- GET  /jobs/{job_id}/trace        -> full Alice<->Bob trace (spec, contract, audit, deliverable, evidence)
- POST /jobs/{job_id}/verify_ai    -> AI review of Bob's deliverable
- POST /jobs/{job_id}/verify_trace -> AI review of the entire negotiation + execution trace

These are read-only with respect to job state; they never mutate status. The
separate deterministic `/verify` endpoint remains the gate for state
transitions. This keeps the AI engine a pure auditor that can be run at any
point (including after `verified` / `settled`).
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai_verification import AIVerifier
from ..artifact_storage import ArtifactStorage
from ..db import get_session_factory
from ..models import AuditLogModel
from ..repository import JobRepository
from ..schemas.completion_packet import CompletionPacket, Deliverable, EvidenceArtifact
from ..schemas.job_spec import JobSpec
from ..verification import apply_contract_policy, verify_deterministic

router = APIRouter(prefix="/jobs", tags=["ai-verification"])
SessionLocal = get_session_factory()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Trace assembly
# ---------------------------------------------------------------------------


def _load_trace(db: Session, job_id: str) -> dict[str, Any]:
    job = JobRepository(db).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    audit_rows = (
        db.execute(
            select(AuditLogModel)
            .where(AuditLogModel.job_id == job_id)
            .order_by(AuditLogModel.id)
        )
        .scalars()
        .all()
    )
    audit_log = [
        {
            "id": row.id,
            "action": row.action,
            "from_status": row.from_status,
            "to_status": row.to_status,
            "details": row.details or {},
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in audit_rows
    ]

    packet_model = ArtifactStorage(db).get(job_id)
    deliverable = packet_model.deliverable_json if packet_model else None
    evidence = (
        packet_model.evidence_json.get("artifacts", []) if packet_model else []
    )

    return {
        "job_id": job.job_id,
        "status": job.status,
        "requester_id": job.requester_id,
        "doer_id": job.doer_id,
        "job_spec": job.job_spec_json,
        "contract": job.job_contract_json,
        "audit_log": audit_log,
        "deliverable": deliverable,
        "evidence": evidence,
    }


def _run_deterministic_snapshot(
    job_spec_json: dict[str, Any],
    deliverable_json: dict[str, Any] | None,
    evidence_list: list[dict[str, Any]],
    contract: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Run the deterministic verifier fresh against the stored packet.

    Returns a {verified, error?, action?} dict in the same shape as the real
    `/verify` response, without mutating state. Used when callers want the
    trace reviewer to know what the deterministic gate would have said.
    """
    if deliverable_json is None:
        return None
    try:
        spec = JobSpec(**job_spec_json)
        deliverable = Deliverable(**deliverable_json)
        evidence = [EvidenceArtifact(**a) for a in evidence_list]
        packet = CompletionPacket(deliverable=deliverable, evidence=evidence)
    except Exception as e:  # pragma: no cover - defensive
        return {"verified": False, "error": f"packet_load_error:{e}"}
    passed, err = verify_deterministic(packet, spec)
    dispute_policy = (contract or {}).get("dispute_policy", "refund")
    if not passed:
        return {
            "verified": False,
            "error": err,
            "action": apply_contract_policy(dispute_policy),
        }
    return {"verified": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{job_id}/trace")
def get_trace(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return the full Alice<->Bob negotiation + execution trace."""
    return _load_trace(db, job_id)


class AIVerifyBody(BaseModel):
    backend: Literal["auto", "openai", "heuristic"] = Field(
        "auto",
        description="Force a backend. `auto` uses openai if OPENAI_API_KEY is set, else heuristic.",
    )
    model: str | None = Field(
        None, description="Optional OpenAI model override (default gpt-4o-mini or OPENAI_VERIFIER_MODEL)."
    )


@router.post("/{job_id}/verify_ai")
def verify_ai(
    job_id: str,
    body: AIVerifyBody | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """AI review of Bob's deliverable against the job spec."""
    trace = _load_trace(db, job_id)
    if trace["deliverable"] is None:
        raise HTTPException(400, "No completion packet submitted for this job yet")
    body = body or AIVerifyBody()
    verifier = AIVerifier(backend=body.backend, model=body.model)
    result = verifier.review_deliverable(
        job_spec=trace["job_spec"],
        deliverable=trace["deliverable"],
        evidence=trace["evidence"],
    )
    return {"job_id": job_id, "kind": "deliverable_review", **result}


@router.post("/{job_id}/verify_trace")
def verify_trace(
    job_id: str,
    body: AIVerifyBody | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """AI audit of the full negotiation + execution trace."""
    trace = _load_trace(db, job_id)
    body = body or AIVerifyBody()
    verifier = AIVerifier(backend=body.backend, model=body.model)
    det = _run_deterministic_snapshot(
        job_spec_json=trace["job_spec"],
        deliverable_json=trace["deliverable"],
        evidence_list=trace["evidence"],
        contract=trace["contract"],
    )
    result = verifier.review_negotiation_trace(
        job_spec=trace["job_spec"],
        contract=trace["contract"],
        audit_log=trace["audit_log"],
        deliverable=trace["deliverable"],
        evidence=trace["evidence"],
        deterministic_verification=det,
    )
    return {
        "job_id": job_id,
        "kind": "trace_review",
        "deterministic_snapshot": det,
        **result,
    }
