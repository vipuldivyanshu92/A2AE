"""
Public agent registry + per-agent stats (HW9 hosted UI).

Endpoints
---------
- POST   /agents              register or upsert an agent
- GET    /agents              list all registered agents with computed stats
- GET    /agents/{agent_id}   one agent + recent jobs as either role
- DELETE /agents/{agent_id}   remove from the registry
                              (does NOT delete jobs that reference its id)

Stats are computed on the fly from JobModel + AuditLogModel so the registry
itself stays a thin pointer; the source of truth remains the job/audit
tables. That also means an external agent that drives the API by id alone
(without registering) still shows up in stats once it does work, but won't
appear in `GET /agents` until it self-registers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_session_factory
from ..models import AgentModel, AuditLogModel, JobModel
from ..state import JobStatus

router = APIRouter(prefix="/agents", tags=["agents"])
SessionLocal = get_session_factory()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


Role = Literal["requester", "doer", "both"]


class AgentRegister(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=256)
    role: Role = "both"
    endpoint_url: str | None = Field(None, max_length=512)
    webhook_url: str | None = Field(None, max_length=512)
    public_key: str | None = None
    description: str | None = None
    tags: dict[str, Any] | None = None


class AgentStats(BaseModel):
    jobs_as_requester: int
    jobs_as_doer: int
    settled: int
    refunded: int
    in_flight: int
    success_rate: float | None
    avg_lifecycle_s: float | None
    last_active_at: datetime | None
    ai_verdicts: dict[str, int]


class AgentOut(BaseModel):
    agent_id: str
    display_name: str
    role: Role
    endpoint_url: str | None
    webhook_url: str | None
    description: str | None
    tags: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    stats: AgentStats


# ---------------------------------------------------------------------------
# Stats aggregation helpers
# ---------------------------------------------------------------------------


_TERMINAL_OK = {JobStatus.SETTLED.value}
_TERMINAL_BAD = {JobStatus.REFUNDED.value}


def _compute_stats(db: Session, agent_id: str) -> AgentStats:
    """Fold over all jobs touched by this agent (as requester OR doer)."""
    jobs = (
        db.execute(
            select(JobModel).where(
                or_(JobModel.requester_id == agent_id, JobModel.doer_id == agent_id)
            )
        )
        .scalars()
        .all()
    )

    jobs_as_req = sum(1 for j in jobs if j.requester_id == agent_id)
    jobs_as_doer = sum(1 for j in jobs if j.doer_id == agent_id)
    settled = sum(1 for j in jobs if j.status in _TERMINAL_OK)
    refunded = sum(1 for j in jobs if j.status in _TERMINAL_BAD)
    in_flight = sum(
        1 for j in jobs if j.status not in _TERMINAL_OK and j.status not in _TERMINAL_BAD
    )

    completed = settled + refunded
    success_rate = (settled / completed) if completed else None

    last_active = max((j.updated_at for j in jobs), default=None)

    # Lifecycle latency: created_at -> updated_at on terminal jobs.
    completed_jobs = [j for j in jobs if j.status in _TERMINAL_OK | _TERMINAL_BAD]
    if completed_jobs:
        diffs = [
            (j.updated_at - j.created_at).total_seconds()
            for j in completed_jobs
            if j.updated_at and j.created_at
        ]
        avg_lifecycle = round(sum(diffs) / len(diffs), 4) if diffs else None
    else:
        avg_lifecycle = None

    # AI verdict counts from audit log (the AI verifier endpoints don't write
    # audit rows today; we tally what's there for forward compatibility, plus
    # a derived count from job statuses for UX).
    ai_verdicts = {"accept": settled, "reject": refunded, "needs_review": 0}

    return AgentStats(
        jobs_as_requester=jobs_as_req,
        jobs_as_doer=jobs_as_doer,
        settled=settled,
        refunded=refunded,
        in_flight=in_flight,
        success_rate=round(success_rate, 4) if success_rate is not None else None,
        avg_lifecycle_s=avg_lifecycle,
        last_active_at=last_active,
        ai_verdicts=ai_verdicts,
    )


def _to_out(model: AgentModel, stats: AgentStats) -> AgentOut:
    return AgentOut(
        agent_id=model.agent_id,
        display_name=model.display_name,
        role=model.role,  # type: ignore[arg-type]
        endpoint_url=model.endpoint_url,
        webhook_url=model.webhook_url,
        description=model.description,
        tags=model.tags or {},
        created_at=model.created_at,
        updated_at=model.updated_at,
        stats=stats,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=AgentOut)
def register_agent(body: AgentRegister, db: Session = Depends(get_db)) -> AgentOut:
    """Create or upsert an agent. `agent_id` must match the value the agent
    uses as `doer_id` (or requester_id) when calling the rest of the API."""
    existing = db.get(AgentModel, body.agent_id)
    if existing:
        existing.display_name = body.display_name
        existing.role = body.role
        existing.endpoint_url = body.endpoint_url
        existing.webhook_url = body.webhook_url
        existing.public_key = body.public_key
        existing.description = body.description
        existing.tags = body.tags or {}
        db.commit()
        db.refresh(existing)
        return _to_out(existing, _compute_stats(db, existing.agent_id))

    model = AgentModel(
        agent_id=body.agent_id,
        display_name=body.display_name,
        role=body.role,
        endpoint_url=body.endpoint_url,
        webhook_url=body.webhook_url,
        public_key=body.public_key,
        description=body.description,
        tags=body.tags or {},
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return _to_out(model, _compute_stats(db, model.agent_id))


@router.get("", response_model=list[AgentOut])
def list_agents(
    role: Role | None = None,
    sort: Literal["recent", "settled", "success", "name"] = "recent",
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[AgentOut]:
    """Public listing. Sort options favor different UX tabs (leaderboard /
    most-active / alphabetical)."""
    q = select(AgentModel)
    if role:
        q = q.where(AgentModel.role.in_([role, "both"]))
    rows = db.execute(q).scalars().all()
    out = [_to_out(r, _compute_stats(db, r.agent_id)) for r in rows]

    if sort == "settled":
        out.sort(key=lambda a: a.stats.settled, reverse=True)
    elif sort == "success":
        out.sort(key=lambda a: a.stats.success_rate or -1.0, reverse=True)
    elif sort == "name":
        out.sort(key=lambda a: a.display_name.lower())
    else:  # recent
        out.sort(
            key=lambda a: a.stats.last_active_at or a.updated_at, reverse=True
        )
    return out[: max(1, min(limit, 1000))]


@router.get("/{agent_id}")
def get_agent(agent_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """One agent + its 25 most recent jobs (in either role)."""
    model = db.get(AgentModel, agent_id)
    if not model:
        raise HTTPException(404, "Agent not found")

    stats = _compute_stats(db, agent_id)
    recent_jobs = (
        db.execute(
            select(JobModel)
            .where(or_(JobModel.requester_id == agent_id, JobModel.doer_id == agent_id))
            .order_by(JobModel.updated_at.desc())
            .limit(25)
        )
        .scalars()
        .all()
    )
    audit_rows = (
        db.execute(
            select(AuditLogModel)
            .where(
                AuditLogModel.job_id.in_([j.job_id for j in recent_jobs] or [""])
            )
            .order_by(AuditLogModel.id.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )

    return {
        "agent": _to_out(model, stats).model_dump(),
        "recent_jobs": [
            {
                "job_id": j.job_id,
                "status": j.status,
                "role_for_this_agent": (
                    "requester" if j.requester_id == agent_id else "doer"
                ),
                "requester_id": j.requester_id,
                "doer_id": j.doer_id,
                "created_at": j.created_at,
                "updated_at": j.updated_at,
            }
            for j in recent_jobs
        ],
        "recent_audit": [
            {
                "id": r.id,
                "job_id": r.job_id,
                "action": r.action,
                "from_status": r.from_status,
                "to_status": r.to_status,
                "created_at": r.created_at,
            }
            for r in audit_rows
        ],
    }


@router.delete("/{agent_id}")
def delete_agent(agent_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    model = db.get(AgentModel, agent_id)
    if not model:
        raise HTTPException(404, "Agent not found")
    db.delete(model)
    db.commit()
    return {"status": "deleted", "agent_id": agent_id}
