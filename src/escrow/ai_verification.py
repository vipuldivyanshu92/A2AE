"""
AI Verification Engine (HW8).

Two responsibilities:

1. `review_deliverable` — inspects worker agent Bob's deliverable against the
   job spec and returns a structured verdict (accept / reject / needs_review)
   with reasoning and issues.

2. `review_negotiation_trace` — reads the full Alice (task provider /
   requester) <-> Bob (doer) trace, i.e. job spec + finalized contract +
   state-transition audit log + submitted completion packet + downstream
   verification result, and decides whether the lifecycle is internally
   consistent (contract terms actually honored, no policy drift, deliverable
   shape matches what was agreed).

Both methods work in two backends:

- `openai` — uses OpenAI chat completions with a JSON response format when
  `OPENAI_API_KEY` is set. Model is `OPENAI_VERIFIER_MODEL` (default
  `gpt-4o-mini`). This is the intended production path.
- `heuristic` — a deterministic rule-based fallback so the engine remains
  callable for scale tests that can't afford 30+ LLM calls and for CI /
  offline runs. The return shape is identical.

The module is dependency-light (no new packages beyond what's already in
requirements.txt) and has no direct database access — it operates purely on
plain dicts assembled by the API layer from the repository/audit/artifact
stores. That keeps it easy to unit test and to call from external agents
(OpenClaw, etc.) by POSTing a trace payload.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Literal

Verdict = Literal["accept", "reject", "needs_review"]


# ---------------------------------------------------------------------------
# Public dataclass-ish result helpers
# ---------------------------------------------------------------------------


def _make_result(
    *,
    verdict: Verdict,
    score: float,
    reasoning: str,
    issues: list[str],
    backend: str,
    latency_s: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "verdict": verdict,
        "score": round(float(score), 4),
        "reasoning": reasoning,
        "issues": issues,
        "backend": backend,
        "latency_s": round(latency_s, 4),
        "extra": extra or {},
    }


# ---------------------------------------------------------------------------
# Heuristic backend — deterministic, no network
# ---------------------------------------------------------------------------


def _heuristic_review_deliverable(
    *, job_spec: dict[str, Any], deliverable: dict[str, Any], evidence: list[dict[str, Any]]
) -> dict[str, Any]:
    t0 = time.perf_counter()
    issues: list[str] = []
    score = 1.0

    content = deliverable.get("content")
    required_keys = (
        ((job_spec.get("output_schema") or {}).get("definition") or {}).get("required") or []
    )

    if isinstance(content, dict):
        for key in required_keys:
            if key not in content:
                issues.append(f"missing_required_field:{key}")
                score -= 0.4
        if not content:
            issues.append("empty_deliverable_object")
            score -= 0.5
        else:
            # trivially-empty string values also count as low quality
            for k, v in content.items():
                if isinstance(v, str) and not v.strip():
                    issues.append(f"empty_value:{k}")
                    score -= 0.1
    elif isinstance(content, str):
        if not content.strip():
            issues.append("empty_string_deliverable")
            score -= 0.6
        elif len(content.strip()) < 8:
            issues.append("suspiciously_short_deliverable")
            score -= 0.3
    else:
        issues.append("unexpected_deliverable_type")
        score -= 0.3

    # Evidence heuristic — no evidence is not fatal, but boost if present.
    if evidence:
        score = min(1.0, score + 0.05)

    score = max(0.0, min(1.0, score))
    if score >= 0.8 and not issues:
        verdict: Verdict = "accept"
        reasoning = "Deliverable satisfies required schema keys and is non-trivial."
    elif score <= 0.4 or any(i.startswith("missing_required_field") for i in issues):
        verdict = "reject"
        reasoning = "Deliverable violates required schema or is empty."
    else:
        verdict = "needs_review"
        reasoning = "Deliverable has minor issues (shape OK, quality unclear)."

    return _make_result(
        verdict=verdict,
        score=score,
        reasoning=reasoning,
        issues=issues,
        backend="heuristic",
        latency_s=time.perf_counter() - t0,
    )


def _heuristic_review_trace(
    *,
    job_spec: dict[str, Any],
    contract: dict[str, Any] | None,
    audit_log: list[dict[str, Any]],
    deliverable: dict[str, Any] | None,
    evidence: list[dict[str, Any]],
    deterministic_verification: dict[str, Any] | None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    issues: list[str] = []
    score = 1.0

    expected_flow = [
        "created",
        "negotiated",
        "funded",
        "in_progress",
        "submitted",
    ]
    # A state counts as "observed" if it appears as either a `to_status` OR a
    # `from_status` — the initial CREATED insert only shows up as the
    # from_status of the first transition, which is still evidence it happened.
    seen_states: set[str] = set()
    state_rows = [e for e in audit_log if e.get("action") == "state_transition"]
    for e in state_rows:
        if e.get("to_status"):
            seen_states.add(e["to_status"])
        if e.get("from_status"):
            seen_states.add(e["from_status"])

    for expected in expected_flow:
        if expected not in seen_states:
            issues.append(f"missing_state_transition:{expected}")
            score -= 0.1

    if contract is None:
        issues.append("no_finalized_contract")
        score -= 0.3
    else:
        # Dispute policy sanity: must be one of the allowed values.
        dp = contract.get("dispute_policy")
        if dp not in ("retry", "arbitration", "refund"):
            issues.append(f"invalid_dispute_policy:{dp}")
            score -= 0.2
        if not contract.get("doer_id"):
            issues.append("contract_missing_doer_id")
            score -= 0.2

    # If deterministic verification ran, its action should match the contract's dispute_policy.
    if (
        deterministic_verification is not None
        and deterministic_verification.get("verified") is False
        and contract is not None
    ):
        action = deterministic_verification.get("action")
        policy = contract.get("dispute_policy")
        if action != policy:
            issues.append(f"policy_drift:contract={policy}_verify_action={action}")
            score -= 0.3

    # Deliverable shape vs spec
    if deliverable is not None:
        del_review = _heuristic_review_deliverable(
            job_spec=job_spec, deliverable=deliverable, evidence=evidence
        )
        if del_review["verdict"] == "reject":
            issues.extend([f"deliverable:{i}" for i in del_review["issues"]])
            score -= 0.25

    score = max(0.0, min(1.0, score))
    if score >= 0.85 and not issues:
        verdict: Verdict = "accept"
        reasoning = "Full lifecycle honored: negotiation, funding, execution, submit, and policy all consistent."
    elif score <= 0.5:
        verdict = "reject"
        reasoning = "Trace shows missing transitions or policy drift between contract and verification."
    else:
        verdict = "needs_review"
        reasoning = "Trace is mostly consistent but has minor issues worth a human spot-check."

    return _make_result(
        verdict=verdict,
        score=score,
        reasoning=reasoning,
        issues=issues,
        backend="heuristic",
        latency_s=time.perf_counter() - t0,
        extra={
            "seen_states": sorted(seen_states),
            "expected_flow": expected_flow,
        },
    )


# ---------------------------------------------------------------------------
# OpenAI backend
# ---------------------------------------------------------------------------


_DELIVERABLE_SYSTEM = """You are an impartial AI verification engine reviewing a worker agent's deliverable for an escrow-backed task.
You receive: the job spec (including any output_schema requirements), the deliverable content, and any evidence artifacts.
Decide if the deliverable should be accepted, rejected, or flagged for human review.

Return ONLY a JSON object with these keys:
- verdict: one of "accept" | "reject" | "needs_review"
- score: float in [0, 1] where 1.0 means perfect
- reasoning: short (<= 2 sentences) justification
- issues: list of short strings (machine-readable tags) describing any problems

Be strict about required output_schema keys. If any required key is missing or empty, verdict must be "reject"."""

_TRACE_SYSTEM = """You are an impartial AI verification engine auditing the full negotiation and execution trace of an escrow-backed task between Alice (task provider / requester) and Bob (doer / worker agent).
You receive: the job spec, the finalized contract, the ordered audit log of state transitions, Bob's submitted deliverable + evidence, and the deterministic verification result already produced by the escrow system.

Your job is to flag inconsistencies across the FULL lifecycle, not just the deliverable. In particular:
- Did every expected state transition happen (created -> negotiated -> funded -> in_progress -> submitted)?
- Does the contract's dispute_policy match the action taken by deterministic verification on failure?
- Does the deliverable honor the agreed output_schema and constraints from the contract?
- Are there gaps, missing fields, or suspicious jumps in the trace?

Return ONLY a JSON object with keys:
- verdict: "accept" | "reject" | "needs_review"
- score: float in [0, 1]
- reasoning: <= 2 sentences
- issues: list of short tag strings"""


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _openai_json(system: str, user: str, model: str) -> tuple[dict[str, Any], dict[str, int]]:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    msg = resp.choices[0].message.content or "{}"
    data = json.loads(_strip_json_fence(msg))
    if not isinstance(data, dict):
        raise ValueError("Model did not return a JSON object")
    u = resp.usage
    usage = {
        "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
    }
    return data, usage


def _normalize_llm_result(
    data: dict[str, Any],
    *,
    backend: str,
    latency_s: float,
    usage: dict[str, int] | None,
) -> dict[str, Any]:
    verdict = data.get("verdict", "needs_review")
    if verdict not in ("accept", "reject", "needs_review"):
        verdict = "needs_review"
    try:
        score = float(data.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    issues = data.get("issues") or []
    if not isinstance(issues, list):
        issues = [str(issues)]
    reasoning = str(data.get("reasoning", ""))[:500]
    extra: dict[str, Any] = {}
    if usage:
        extra["usage"] = usage
    return _make_result(
        verdict=verdict,
        score=max(0.0, min(1.0, score)),
        reasoning=reasoning,
        issues=[str(i) for i in issues][:20],
        backend=backend,
        latency_s=latency_s,
        extra=extra,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class AIVerifier:
    """Dual-backend verifier. Pick backend explicitly, or let it auto-detect."""

    def __init__(
        self,
        *,
        backend: Literal["auto", "openai", "heuristic"] = "auto",
        model: str | None = None,
    ) -> None:
        if backend == "auto":
            backend = "openai" if os.environ.get("OPENAI_API_KEY") else "heuristic"
        self.backend = backend
        self.model = model or os.environ.get("OPENAI_VERIFIER_MODEL", "gpt-4o-mini")

    # -- deliverable review --------------------------------------------------

    def review_deliverable(
        self,
        *,
        job_spec: dict[str, Any],
        deliverable: dict[str, Any],
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        evidence = evidence or []
        if self.backend == "heuristic":
            return _heuristic_review_deliverable(
                job_spec=job_spec, deliverable=deliverable, evidence=evidence
            )
        t0 = time.perf_counter()
        try:
            user_payload = json.dumps(
                {
                    "job_spec": job_spec,
                    "deliverable": deliverable,
                    "evidence": evidence,
                },
                default=str,
            )[:12000]
            data, usage = _openai_json(_DELIVERABLE_SYSTEM, user_payload, self.model)
            return _normalize_llm_result(
                data,
                backend=f"openai:{self.model}",
                latency_s=time.perf_counter() - t0,
                usage=usage,
            )
        except Exception as e:
            # On any failure, fall back to heuristic with a breadcrumb.
            fb = _heuristic_review_deliverable(
                job_spec=job_spec, deliverable=deliverable, evidence=evidence
            )
            fb["issues"].append(f"openai_fallback:{type(e).__name__}")
            fb["backend"] = "heuristic_fallback"
            return fb

    # -- full-trace review ---------------------------------------------------

    def review_negotiation_trace(
        self,
        *,
        job_spec: dict[str, Any],
        contract: dict[str, Any] | None,
        audit_log: list[dict[str, Any]],
        deliverable: dict[str, Any] | None,
        evidence: list[dict[str, Any]] | None = None,
        deterministic_verification: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence = evidence or []
        if self.backend == "heuristic":
            return _heuristic_review_trace(
                job_spec=job_spec,
                contract=contract,
                audit_log=audit_log,
                deliverable=deliverable,
                evidence=evidence,
                deterministic_verification=deterministic_verification,
            )
        t0 = time.perf_counter()
        try:
            user_payload = json.dumps(
                {
                    "job_spec": job_spec,
                    "contract": contract,
                    "audit_log": audit_log,
                    "deliverable": deliverable,
                    "evidence": evidence,
                    "deterministic_verification": deterministic_verification,
                },
                default=str,
            )[:14000]
            data, usage = _openai_json(_TRACE_SYSTEM, user_payload, self.model)
            return _normalize_llm_result(
                data,
                backend=f"openai:{self.model}",
                latency_s=time.perf_counter() - t0,
                usage=usage,
            )
        except Exception as e:
            fb = _heuristic_review_trace(
                job_spec=job_spec,
                contract=contract,
                audit_log=audit_log,
                deliverable=deliverable,
                evidence=evidence,
                deterministic_verification=deterministic_verification,
            )
            fb["issues"].append(f"openai_fallback:{type(e).__name__}")
            fb["backend"] = "heuristic_fallback"
            return fb


__all__ = ["AIVerifier"]
