#!/usr/bin/env python3
"""
Drive the escrow API with multiple labeled agent identities (request/doer roles).

Designed for small-scale system experiments: point ESCROW_API_BASE at a shared server
(e.g. cloud-hosted API) and set INSTANCE_LABEL to distinguish cloud VMs.

Requires: pip install httpx (already in project requirements.txt).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_BASE = os.environ.get("ESCROW_API_BASE", "http://127.0.0.1:8000")
DEFAULT_INSTANCE = os.environ.get("INSTANCE_LABEL", "local")


def _idem() -> str:
    return str(uuid.uuid4())


@dataclass
class FlowResult:
    experiment: str
    arm: str
    agent_id: str
    job_id: str | None
    ok: bool
    verify_passed: bool | None
    verify_action: str | None
    settled: bool
    error: str | None = None
    elapsed_s: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


def _headers(idem: str, instance_label: str) -> dict[str, str]:
    return {
        "Idempotency-Key": idem,
        "Content-Type": "application/json",
        "X-Experiment-Instance": instance_label,
    }


def task_request(
    *,
    task_description: str,
    strict_required_keys: list[str] | None,
    rubric_required_score: float | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "max_budget": "100",
        "task_description": task_description,
        "callback_url": None,
    }
    if strict_required_keys:
        body["output_schema"] = {
            "type": "json-schema",
            "definition": {"required": strict_required_keys},
        }
    else:
        body["output_schema"] = {"type": "json-schema", "definition": {}}
    if rubric_required_score is not None:
        body["evaluation_rubric"] = {
            "criteria": [],
            "required_score": rubric_required_score,
        }
    return body


def run_job_flow(
    client: httpx.Client,
    base: str,
    instance_label: str,
    *,
    experiment: str,
    arm: str,
    agent_id: str,
    spec: dict[str, Any],
    deliverable_content: dict[str, Any],
    dispute_policy: str | None,
    expect_verify_pass: bool,
    settle_if_verified: bool,
) -> FlowResult:
    t0 = time.perf_counter()
    job_id = None
    try:
        r = client.post(
            f"{base}/jobs",
            json=spec,
            headers=_headers(_idem(), instance_label),
            timeout=60.0,
        )
        r.raise_for_status()
        job_id = r.json()["job_id"]

        accept_body: dict[str, Any] = {"doer_id": agent_id}
        if dispute_policy:
            accept_body["dispute_policy"] = dispute_policy
        r = client.post(
            f"{base}/jobs/{job_id}/handshake/accept",
            json=accept_body,
            headers=_headers(_idem(), instance_label),
            timeout=60.0,
        )
        r.raise_for_status()

        r = client.post(
            f"{base}/jobs/{job_id}/fund",
            headers=_headers(_idem(), instance_label),
            timeout=60.0,
        )
        r.raise_for_status()

        r = client.post(f"{base}/jobs/{job_id}/start", timeout=60.0)
        r.raise_for_status()

        packet = {
            "deliverable": {"content": deliverable_content, "mime_type": "application/json"},
            "evidence": [],
        }
        r = client.post(
            f"{base}/jobs/{job_id}/submit",
            json=packet,
            headers=_headers(_idem(), instance_label),
            timeout=60.0,
        )
        r.raise_for_status()

        r = client.post(f"{base}/jobs/{job_id}/verify", timeout=60.0)
        r.raise_for_status()
        vj = r.json()
        verified = bool(vj.get("verified"))
        action = vj.get("action")

        settled = False
        if verified and settle_if_verified:
            r = client.post(
                f"{base}/jobs/{job_id}/settle",
                headers=_headers(_idem(), instance_label),
                timeout=60.0,
            )
            r.raise_for_status()
            settled = True

        ok = verified == expect_verify_pass and (not settle_if_verified or settled == expect_verify_pass)
        return FlowResult(
            experiment=experiment,
            arm=arm,
            agent_id=agent_id,
            job_id=job_id,
            ok=ok,
            verify_passed=verified,
            verify_action=action,
            settled=settled,
            error=None,
            elapsed_s=time.perf_counter() - t0,
            extra={"raw_verify": vj},
        )
    except Exception as e:
        return FlowResult(
            experiment=experiment,
            arm=arm,
            agent_id=agent_id,
            job_id=job_id,
            ok=False,
            verify_passed=None,
            verify_action=None,
            settled=False,
            error=str(e),
            elapsed_s=time.perf_counter() - t0,
        )


def exp1_verification_strictness(
    client: httpx.Client,
    base: str,
    instance_label: str,
    doer_ids: list[str] | None = None,
) -> list[FlowResult]:
    """
    Arm A: required output key 'result'; deliverable omits it -> expect verify fail.
    Arm B: no required keys; same bad-shaped payload -> deterministic check passes.

    If `doer_ids` is set, it must be length 6: slots 0-2 = strict arm, 3-5 = loose arm.
    """
    if doer_ids is not None:
        strict = doer_ids[0:3]
        loose = doer_ids[3:6]
    else:
        strict = [f"doer-{instance_label}-exp1A-{i + 1}" for i in range(3)]
        loose = [f"doer-{instance_label}-exp1B-{i + 1}" for i in range(3)]

    results: list[FlowResult] = []
    for agent in strict:
        results.append(
            run_job_flow(
                client,
                base,
                instance_label,
                experiment="exp1_verification_strictness",
                arm="strict_schema",
                agent_id=agent,
                spec=task_request(
                    task_description=f"{agent} strict schema",
                    strict_required_keys=["result"],
                ),
                deliverable_content={"answer": "wrong-shape"},
                dispute_policy=None,
                expect_verify_pass=False,
                settle_if_verified=False,
            )
        )
    for agent in loose:
        results.append(
            run_job_flow(
                client,
                base,
                instance_label,
                experiment="exp1_verification_strictness",
                arm="loose_schema",
                agent_id=agent,
                spec=task_request(
                    task_description=f"{agent} loose schema",
                    strict_required_keys=None,
                ),
                deliverable_content={"answer": "any-shape"},
                dispute_policy=None,
                expect_verify_pass=True,
                settle_if_verified=True,
            )
        )
    return results


def exp2_dispute_policy(
    client: httpx.Client,
    base: str,
    instance_label: str,
    doer_ids: list[str] | None = None,
) -> list[FlowResult]:
    """
    On verification failure, API should echo contract dispute_policy as action.

    If `doer_ids` is set (len 6): slots 0-2 = refund arm, 3-5 = arbitration arm.
    """
    if doer_ids is not None:
        refund_ids = doer_ids[0:3]
        arb_ids = doer_ids[3:6]
    else:
        refund_ids = [f"doer-{instance_label}-exp2-refund-{i + 1}" for i in range(3)]
        arb_ids = [f"doer-{instance_label}-exp2-arbitration-{i + 1}" for i in range(3)]

    results: list[FlowResult] = []
    for policy, pool in (("refund", refund_ids), ("arbitration", arb_ids)):
        for agent in pool:
            results.append(
                run_job_flow(
                    client,
                    base,
                    instance_label,
                    experiment="exp2_dispute_policy",
                    arm=policy,
                    agent_id=agent,
                    spec=task_request(
                        task_description=f"{agent} policy={policy}",
                        strict_required_keys=["result"],
                    ),
                    deliverable_content={},
                    dispute_policy=policy,
                    expect_verify_pass=False,
                    settle_if_verified=False,
                )
            )
    for r in results:
        r.ok = (
            r.error is None
            and r.verify_passed is False
            and r.verify_action == r.arm
        )
    return results


def exp3_parallelism(
    client: httpx.Client,
    base: str,
    instance_label: str,
    doer_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Six independent happy-path jobs: sequential wall time vs parallel wall time."""

    pool = (
        doer_ids
        if doer_ids is not None
        else [f"doer-{instance_label}-exp3-{i + 1}" for i in range(6)]
    )

    def one(i: int) -> FlowResult:
        agent = pool[i]
        return run_job_flow(
            client,
            base,
            instance_label,
            experiment="exp3_coordination_latency",
            arm="happy_path",
            agent_id=agent,
            spec=task_request(
                task_description=f"{agent} happy path",
                strict_required_keys=["result"],
            ),
            deliverable_content={"result": "ok"},
            dispute_policy="refund",
            expect_verify_pass=True,
            settle_if_verified=True,
        )

    t_seq_start = time.perf_counter()
    sequential: list[FlowResult] = []
    for i in range(6):
        sequential.append(one(i))
    t_seq = time.perf_counter() - t_seq_start

    t_par_start = time.perf_counter()
    parallel: list[FlowResult] = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(one, i) for i in range(6)]
        for f in as_completed(futs):
            parallel.append(f.result())
    t_par = time.perf_counter() - t_par_start

    def success_rate(rows: list[FlowResult]) -> float:
        return sum(1 for r in rows if r.ok and r.settled) / max(len(rows), 1)

    return {
        "sequential_wall_s": round(t_seq, 3),
        "parallel_wall_s": round(t_par, 3),
        "sequential_success_rate": success_rate(sequential),
        "parallel_success_rate": success_rate(parallel),
        "sequential_results": [r.__dict__ for r in sequential],
        "parallel_results": [r.__dict__ for r in parallel],
        "speedup": round(t_seq / t_par, 2) if t_par > 0 else None,
    }


def exp4_failure_recovery(
    client: httpx.Client,
    base: str,
    instance_label: str,
    doer_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Verify failure on bad deliverable, then POST /refund; expect terminal status refunded.
    """
    agent = doer_ids[0] if doer_ids else f"doer-{instance_label}-exp4-recover"
    t0 = time.perf_counter()
    steps: list[str] = []
    job_id: str | None = None
    try:
        spec = task_request(
            task_description=f"{agent} failure recovery",
            strict_required_keys=["result"],
        )
        r = client.post(
            f"{base}/jobs",
            json=spec,
            headers=_headers(_idem(), instance_label),
            timeout=60.0,
        )
        r.raise_for_status()
        job_id = r.json()["job_id"]
        steps.append("created")

        r = client.post(
            f"{base}/jobs/{job_id}/handshake/accept",
            json={"doer_id": agent, "dispute_policy": "refund"},
            headers=_headers(_idem(), instance_label),
            timeout=60.0,
        )
        r.raise_for_status()
        steps.append("negotiated")

        r = client.post(
            f"{base}/jobs/{job_id}/fund",
            headers=_headers(_idem(), instance_label),
            timeout=60.0,
        )
        r.raise_for_status()
        steps.append("funded")

        r = client.post(f"{base}/jobs/{job_id}/start", timeout=60.0)
        r.raise_for_status()
        steps.append("in_progress")

        packet = {
            "deliverable": {"content": {}, "mime_type": "application/json"},
            "evidence": [],
        }
        r = client.post(
            f"{base}/jobs/{job_id}/submit",
            json=packet,
            headers=_headers(_idem(), instance_label),
            timeout=60.0,
        )
        r.raise_for_status()
        steps.append("submitted")

        r = client.post(f"{base}/jobs/{job_id}/verify", timeout=60.0)
        r.raise_for_status()
        vj = r.json()
        verified = bool(vj.get("verified"))
        steps.append(f"verify:verified={verified}")
        if verified:
            return {
                "experiment": "exp4_failure_recovery",
                "arm": "verify_fail_then_refund",
                "agent_id": agent,
                "job_id": job_id,
                "ok": False,
                "steps": steps,
                "error": "Expected verification failure",
                "elapsed_s": time.perf_counter() - t0,
            }

        r = client.get(f"{base}/jobs/{job_id}", timeout=30.0)
        r.raise_for_status()
        st_after = r.json().get("status")
        steps.append(f"status_after_verify:{st_after}")

        r = client.post(
            f"{base}/jobs/{job_id}/refund",
            headers=_headers(_idem(), instance_label),
            timeout=60.0,
        )
        r.raise_for_status()
        steps.append("refund_posted")

        r = client.get(f"{base}/jobs/{job_id}", timeout=30.0)
        r.raise_for_status()
        final = r.json().get("status")
        steps.append(f"final_status:{final}")

        ok = final == "refunded"
        return {
            "experiment": "exp4_failure_recovery",
            "arm": "verify_fail_then_refund",
            "agent_id": agent,
            "job_id": job_id,
            "ok": ok,
            "steps": steps,
            "final_status": final,
            "verify_response": vj,
            "elapsed_s": round(time.perf_counter() - t0, 3),
        }
    except Exception as e:
        return {
            "experiment": "exp4_failure_recovery",
            "arm": "verify_fail_then_refund",
            "agent_id": agent,
            "job_id": job_id,
            "ok": False,
            "steps": steps,
            "error": str(e),
            "elapsed_s": time.perf_counter() - t0,
        }


def _collect_experiments(
    client: httpx.Client,
    base: str,
    instance_label: str,
    only: str,
    doer_ids: list[str] | None,
    *,
    include_llm: bool,
    llm_trials_per_arm: int = 3,
) -> dict[str, Any]:
    ex: dict[str, Any] = {}

    if only == "4":
        ex["exp4_failure_recovery"] = exp4_failure_recovery(
            client, base, instance_label, doer_ids
        )
        return ex
    if only == "5":
        if include_llm:
            from experiments.llm_escrow_agent import run_exp5_llm_memory_ab

            ex["exp5_llm_memory_ab"] = run_exp5_llm_memory_ab(
                base=base,
                instance_label=instance_label,
                trials_per_arm=llm_trials_per_arm,
                httpx_client=client,
            )
        else:
            ex["exp5_llm_memory_ab"] = {
                "skipped": True,
                "reason": "Set include_llm=true and OPENAI_API_KEY to run exp5 from the API.",
            }
        return ex

    if only in ("1", "all"):
        ex["exp1_verification_strictness"] = [
            r.__dict__
            for r in exp1_verification_strictness(
                client, base, instance_label, doer_ids
            )
        ]
    if only in ("2", "all"):
        ex["exp2_dispute_policy"] = [
            r.__dict__
            for r in exp2_dispute_policy(client, base, instance_label, doer_ids)
        ]
    if only in ("3", "all"):
        ex["exp3_coordination_latency"] = exp3_parallelism(
            client, base, instance_label, doer_ids
        )
    if only in ("4", "all"):
        ex["exp4_failure_recovery"] = exp4_failure_recovery(
            client, base, instance_label, doer_ids
        )
    if only in ("5", "all"):
        if include_llm:
            from experiments.llm_escrow_agent import run_exp5_llm_memory_ab

            ex["exp5_llm_memory_ab"] = run_exp5_llm_memory_ab(
                base=base,
                instance_label=instance_label,
                trials_per_arm=llm_trials_per_arm,
                httpx_client=client,
            )
        else:
            ex["exp5_llm_memory_ab"] = {
                "skipped": True,
                "reason": "include_llm=false (enable in dashboard or API body to run real OpenAI agent).",
            }

    return ex


def _aggregate_trial_results(trial_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize repeated trials for success rates and latency."""

    def mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    exp1_rates: list[float] = []
    exp2_rates: list[float] = []
    exp4_ok: list[float] = []
    speedups: list[float] = []
    seq_walls: list[float] = []
    par_walls: list[float] = []
    e5_rich: list[float] = []
    e5_min: list[float] = []

    for tr in trial_results:
        ex = tr.get("experiments") or {}
        e1 = ex.get("exp1_verification_strictness")
        if isinstance(e1, list) and e1:
            exp1_rates.append(sum(1 for r in e1 if r.get("ok")) / len(e1))
        e2 = ex.get("exp2_dispute_policy")
        if isinstance(e2, list) and e2:
            exp2_rates.append(sum(1 for r in e2 if r.get("ok")) / len(e2))
        e4 = ex.get("exp4_failure_recovery")
        if isinstance(e4, dict) and "ok" in e4:
            exp4_ok.append(1.0 if e4.get("ok") else 0.0)
        e3 = ex.get("exp3_coordination_latency")
        if isinstance(e3, dict):
            sp = e3.get("speedup")
            if isinstance(sp, (int, float)):
                speedups.append(float(sp))
            if e3.get("sequential_wall_s") is not None:
                seq_walls.append(float(e3["sequential_wall_s"]))
            if e3.get("parallel_wall_s") is not None:
                par_walls.append(float(e3["parallel_wall_s"]))
        e5 = ex.get("exp5_llm_memory_ab")
        if isinstance(e5, dict) and not e5.get("skipped") and isinstance(e5.get("arms"), dict):
            arms = e5["arms"]
            mr = arms.get("memory_rich")
            mm = arms.get("memory_minimal")
            if isinstance(mr, dict) and mr.get("settled_rate") is not None:
                e5_rich.append(float(mr["settled_rate"]))
            if isinstance(mm, dict) and mm.get("settled_rate") is not None:
                e5_min.append(float(mm["settled_rate"]))

    return {
        "trial_count": len(trial_results),
        "exp1_mean_ok_rate": round(mean(exp1_rates), 4) if exp1_rates else None,
        "exp2_mean_policy_match_rate": round(mean(exp2_rates), 4) if exp2_rates else None,
        "exp4_refund_success_rate": round(mean(exp4_ok), 4) if exp4_ok else None,
        "exp3_mean_speedup": round(mean(speedups), 4) if speedups else None,
        "exp3_mean_sequential_wall_s": round(mean(seq_walls), 4) if seq_walls else None,
        "exp3_mean_parallel_wall_s": round(mean(par_walls), 4) if par_walls else None,
        "total_trial_wall_s": round(
            sum(float(tr.get("wall_s") or 0) for tr in trial_results), 3
        ),
        "exp5_mean_settled_rate_memory_rich": round(mean(e5_rich), 4) if e5_rich else None,
        "exp5_mean_settled_rate_memory_minimal": round(mean(e5_min), 4) if e5_min else None,
    }


def run_experiments(
    *,
    base: str,
    instance_label: str,
    only: str = "all",
    doer_ids: list[str] | None = None,
    trials: int = 1,
    include_llm: bool = False,
    llm_trials_per_arm: int = 3,
) -> dict[str, Any]:
    """Execute selected experiments; optional repeated trials and LLM memory experiment (exp5)."""
    base = base.rstrip("/")
    trials = max(1, min(trials, 50))

    trial_results: list[dict[str, Any]] = []

    with httpx.Client() as client:
        client.get(f"{base}/health", timeout=10.0).raise_for_status()
        for t in range(trials):
            t0 = time.perf_counter()
            experiments = _collect_experiments(
                client,
                base,
                instance_label,
                only,
                doer_ids,
                include_llm=include_llm,
                llm_trials_per_arm=llm_trials_per_arm,
            )
            trial_results.append(
                {
                    "trial_index": t,
                    "wall_s": round(time.perf_counter() - t0, 3),
                    "experiments": experiments,
                }
            )

    last_ex = trial_results[-1]["experiments"] if trial_results else {}

    out: dict[str, Any] = {
        "api_base": base,
        "instance_label": instance_label,
        "simulated": False,
        "doer_ids": doer_ids,
        "trials": trials,
        "include_llm": include_llm,
        "llm_trials_per_arm": llm_trials_per_arm,
        "trial_results": trial_results,
        "experiments": last_ex,
        "aggregate": _aggregate_trial_results(trial_results) if trials > 1 else None,
    }
    return out


def _fake_job_id() -> str:
    return str(uuid.uuid4())


def run_experiments_dry_run(
    *,
    base_url: str,
    instance_label: str,
    only: str = "all",
    doer_ids: list[str] | None = None,
    trials: int = 1,
    include_llm: bool = False,
    llm_trials_per_arm: int = 3,
) -> dict[str, Any]:
    """
    Same JSON shape as run_experiments, without HTTP calls — for UI demos and previews.
    Values illustrate expected outcomes from a correctly behaving API.
    """
    base_url = base_url.rstrip("/")
    strict = (
        doer_ids[0:3]
        if doer_ids
        else [f"doer-{instance_label}-exp1A-{i + 1}" for i in range(3)]
    )
    loose = (
        doer_ids[3:6]
        if doer_ids
        else [f"doer-{instance_label}-exp1B-{i + 1}" for i in range(3)]
    )
    refund_ids = (
        doer_ids[0:3]
        if doer_ids
        else [f"doer-{instance_label}-exp2-refund-{i + 1}" for i in range(3)]
    )
    arb_ids = (
        doer_ids[3:6]
        if doer_ids
        else [f"doer-{instance_label}-exp2-arbitration-{i + 1}" for i in range(3)]
    )
    pool3 = (
        doer_ids if doer_ids else [f"doer-{instance_label}-exp3-{i + 1}" for i in range(6)]
    )

    trials = max(1, min(int(trials), 50))

    out: dict[str, Any] = {
        "api_base": base_url,
        "instance_label": instance_label,
        "simulated": True,
        "doer_ids": doer_ids,
        "trials": trials,
        "include_llm": include_llm,
        "llm_trials_per_arm": llm_trials_per_arm,
        "experiments": {},
    }

    if only in ("1", "all"):
        rows: list[dict[str, Any]] = []
        for agent in strict:
            jid = _fake_job_id()
            rows.append(
                {
                    "experiment": "exp1_verification_strictness",
                    "arm": "strict_schema",
                    "agent_id": agent,
                    "job_id": jid,
                    "ok": True,
                    "verify_passed": False,
                    "verify_action": "refund",
                    "settled": False,
                    "error": None,
                    "elapsed_s": 0.02,
                    "extra": {
                        "raw_verify": {
                            "verified": False,
                            "error": "Missing required field: result",
                            "action": "refund",
                        }
                    },
                }
            )
        for agent in loose:
            jid = _fake_job_id()
            rows.append(
                {
                    "experiment": "exp1_verification_strictness",
                    "arm": "loose_schema",
                    "agent_id": agent,
                    "job_id": jid,
                    "ok": True,
                    "verify_passed": True,
                    "verify_action": None,
                    "settled": True,
                    "error": None,
                    "elapsed_s": 0.02,
                    "extra": {"raw_verify": {"verified": True, "job_id": jid}},
                }
            )
        out["experiments"]["exp1_verification_strictness"] = rows

    if only in ("2", "all"):
        rows2: list[dict[str, Any]] = []
        for policy, pool in (("refund", refund_ids), ("arbitration", arb_ids)):
            for agent in pool:
                jid = _fake_job_id()
                rows2.append(
                    {
                        "experiment": "exp2_dispute_policy",
                        "arm": policy,
                        "agent_id": agent,
                        "job_id": jid,
                        "ok": True,
                        "verify_passed": False,
                        "verify_action": policy,
                        "settled": False,
                        "error": None,
                        "elapsed_s": 0.015,
                        "extra": {
                            "raw_verify": {
                                "verified": False,
                                "error": "Missing required field: result",
                                "action": policy,
                            }
                        },
                    }
                )
        out["experiments"]["exp2_dispute_policy"] = rows2

    if only in ("3", "all"):
        seq_results = []
        par_results = []
        for i, agent in enumerate(pool3):
            jid = _fake_job_id()
            row = {
                "experiment": "exp3_coordination_latency",
                "arm": "happy_path",
                "agent_id": agent,
                "job_id": jid,
                "ok": True,
                "verify_passed": True,
                "verify_action": None,
                "settled": True,
                "error": None,
                "elapsed_s": 0.02,
                "extra": {"raw_verify": {"verified": True, "job_id": jid}},
            }
            seq_results.append(dict(row))
            par_results.append(dict(row))
        out["experiments"]["exp3_coordination_latency"] = {
            "sequential_wall_s": 0.12,
            "parallel_wall_s": 0.05,
            "sequential_success_rate": 1.0,
            "parallel_success_rate": 1.0,
            "sequential_results": seq_results,
            "parallel_results": par_results,
            "speedup": 2.4,
        }

    if only in ("4", "all"):
        ag4 = doer_ids[0] if doer_ids else f"doer-{instance_label}-exp4-recover"
        out["experiments"]["exp4_failure_recovery"] = {
            "experiment": "exp4_failure_recovery",
            "arm": "verify_fail_then_refund",
            "agent_id": ag4,
            "job_id": _fake_job_id(),
            "ok": True,
            "steps": [
                "created",
                "negotiated",
                "funded",
                "in_progress",
                "submitted",
                "verify:verified=False",
                "status_after_verify:submitted",
                "refund_posted",
                "final_status:refunded",
            ],
            "final_status": "refunded",
            "elapsed_s": 0.04,
        }

    if only in ("5", "all"):
        out["experiments"]["exp5_llm_memory_ab"] = {
            "skipped": True,
            "reason": "Dry run does not call OpenAI",
            "preview": {
                "memory_rich": "High-detail system prompt reminding schema",
                "memory_minimal": "Minimal system prompt",
            },
        }

    snap = copy.deepcopy(out["experiments"])
    out["trial_results"] = [
        {
            "trial_index": i,
            "wall_s": 0.01,
            "experiments": copy.deepcopy(snap),
        }
        for i in range(trials)
    ]
    out["aggregate"] = _aggregate_trial_results(out["trial_results"]) if trials > 1 else None

    return out


def get_experiment_plan() -> dict[str, Any]:
    """Static plan for dashboards and documentation."""
    return {
        "version": 2,
        "agent_count_per_wave": 6,
        "doer_id_slotting": {
            "description": "When passing doer_ids[0..5] from the UI, indices map across experiments.",
            "slot_0_2": "Exp1 strict schema arm; exp2 refund arm; exp3 jobs 0-2 (sequential/parallel batch).",
            "slot_3_5": "Exp1 loose schema arm; exp2 arbitration arm; exp3 jobs 3-5.",
        },
        "experiments": [
            {
                "id": "exp1_verification_strictness",
                "title": "Verification strictness",
                "summary": "Compare strict output_schema (required key result) vs loose schema with the same deliverable shape.",
                "arms": [
                    {
                        "name": "strict_schema",
                        "agents": 3,
                        "expected_verify": False,
                        "note": "Deliverable has answer but not result — deterministic failure.",
                    },
                    {
                        "name": "loose_schema",
                        "agents": 3,
                        "expected_verify": True,
                        "note": "No required keys — same payload verifies and settles.",
                    },
                ],
                "pipeline": [
                    "POST /jobs",
                    "POST /jobs/{id}/handshake/accept",
                    "POST /jobs/{id}/fund",
                    "POST /jobs/{id}/start",
                    "POST /jobs/{id}/submit",
                    "POST /jobs/{id}/verify",
                    "POST /jobs/{id}/settle (loose arm only)",
                ],
            },
            {
                "id": "exp2_dispute_policy",
                "title": "Handshake dispute policy",
                "summary": "On verification failure, verify response action should match handshake dispute_policy.",
                "arms": [
                    {"name": "refund", "agents": 3, "expected_action": "refund"},
                    {"name": "arbitration", "agents": 3, "expected_action": "arbitration"},
                ],
                "pipeline": [
                    "Same as exp1 through verify; no settle on expected failure.",
                ],
            },
            {
                "id": "exp3_coordination_latency",
                "title": "Sequential vs parallel happy paths",
                "summary": "Six full lifecycles run back-to-back vs six concurrent threads.",
                "arms": [{"name": "happy_path", "agents": 6}],
                "pipeline": ["Full lifecycle including settle for each agent."],
                "metrics": ["sequential_wall_s", "parallel_wall_s", "speedup", "success rates"],
            },
            {
                "id": "exp4_failure_recovery",
                "title": "Failure recovery",
                "summary": "Bad deliverable → verify fails → POST /refund → job ends in refunded.",
                "arms": [{"name": "verify_fail_then_refund", "agents": 1}],
                "pipeline": [
                    "Full path to submitted + failed verify",
                    "GET /jobs/{id} (still submitted)",
                    "POST /jobs/{id}/refund",
                    "GET /jobs/{id} → refunded",
                ],
            },
            {
                "id": "exp5_llm_memory_ab",
                "title": "Memory strategy A vs B (real LLM)",
                "summary": "OpenAI produces deliverable JSON: rich system prompt vs minimal; measure settle rate + token usage/cost estimate.",
                "arms": [
                    {"name": "memory_rich", "agents": "N trials (configurable)"},
                    {"name": "memory_minimal", "agents": "N trials"},
                ],
                "pipeline": [
                    "Requires OPENAI_API_KEY and include_llm=true",
                    "Each trial: chat completion → escrow happy path with model output as deliverable",
                ],
                "metrics": ["settled_rate per arm", "prompt_tokens", "completion_tokens", "estimated_usd"],
            },
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Run escrow agent experiments")
    p.add_argument("--base", default=DEFAULT_BASE, help="Escrow API base URL")
    p.add_argument(
        "--only",
        choices=("1", "2", "3", "4", "5", "all"),
        default="all",
        help="Run a single experiment number",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulated JSON only (no HTTP)",
    )
    p.add_argument("--trials", type=int, default=1, help="Repeat suite (1-50); aggregate stats")
    p.add_argument(
        "--include-llm",
        action="store_true",
        help="Include exp5 (OpenAI); requires OPENAI_API_KEY",
    )
    p.add_argument(
        "--llm-trials-per-arm",
        type=int,
        default=3,
        help="Trials per memory arm for exp5",
    )
    args = p.parse_args()
    instance = os.environ.get("INSTANCE_LABEL", DEFAULT_INSTANCE)

    if args.dry_run:
        out = run_experiments_dry_run(
            base_url=args.base.rstrip("/"),
            instance_label=instance,
            only=args.only,
            trials=args.trials,
            include_llm=args.include_llm,
            llm_trials_per_arm=args.llm_trials_per_arm,
        )
    else:
        out = run_experiments(
            base=args.base.rstrip("/"),
            instance_label=instance,
            only=args.only,
            trials=args.trials,
            include_llm=args.include_llm,
            llm_trials_per_arm=args.llm_trials_per_arm,
        )

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
