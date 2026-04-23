#!/usr/bin/env python3
"""
HW8 scale experiment: drive N >= 30 doer agents against the escrow API from
multiple simulated cloud instances and measure what actually breaks under
load.

Design choices
--------------
- Each "instance" is a concurrent worker pool with its own `httpx.Client`
  (its own connection pool) and its own `INSTANCE_LABEL` — the exact same
  shape the runner takes when you `scp` this script to several cloud VMs
  and point `ESCROW_API_BASE` at a shared API host. Running many instances
  locally lets one machine produce the same concurrency / connection-churn
  pattern that shows up in real multi-VM deployments.
- Each agent runs the full lifecycle: POST /jobs -> /handshake/accept ->
  /fund -> /start -> /submit -> /verify -> (/settle or /refund) and then
  the HW8 AI verification engine: /verify_ai + /verify_trace.
- A fraction of agents intentionally submit a bad-shaped deliverable
  (`--bad-rate`, default 0.2) to exercise the failure / policy / refund
  path at scale so we see both the happy and unhappy queues mix.

What gets measured
------------------
Per run:
- total agents, total jobs created, completed lifecycles
- success counts per outcome (settled, refunded, verify_failed, http_error)
- latency percentiles (p50 / p95 / p99 / max) for end-to-end lifecycle
- latency percentiles for AI verification calls (deliverable + trace)
- per-instance breakdown (throughput + error rate per "cloud VM")
- HTTP error distribution (status codes + exception types)
- wall-clock throughput (jobs / second)

All of this is written to `experiments/results/<date>_scale-<N>.json`.

CLI
---
    python experiments/scale_experiment.py \
        --base http://127.0.0.1:8765 \
        --agents 30 \
        --instances 3 \
        --bad-rate 0.2 \
        --ai-backend auto

Use `--ai-backend heuristic` for fast offline AI verification (no OpenAI
key needed). Use `--ai-backend openai` to hit the real LLM verifier (costs
tokens; recommended for smaller `--ai-sample` fractions).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx


DEFAULT_BASE = os.environ.get("ESCROW_API_BASE", "http://127.0.0.1:8000")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    instance_label: str
    agent_id: str
    job_id: str | None
    outcome: str  # settled | refunded | verify_failed | http_error | exception
    verify_passed: bool | None
    verify_action: str | None
    settled: bool
    refunded: bool
    lifecycle_s: float
    ai_deliverable: dict[str, Any] | None = None
    ai_deliverable_s: float | None = None
    ai_trace: dict[str, Any] | None = None
    ai_trace_s: float | None = None
    http_status: int | None = None
    error: str | None = None


@dataclass
class InstanceSummary:
    label: str
    agents: int
    settled: int = 0
    refunded: int = 0
    verify_failed: int = 0
    http_errors: int = 0
    exceptions: int = 0
    wall_s: float = 0.0


@dataclass
class ScaleReport:
    started_at: str
    ended_at: str
    base_url: str
    total_agents: int
    instances: int
    bad_rate: float
    ai_backend: str
    ai_sample_rate: float
    wall_s: float
    throughput_jobs_per_s: float
    counts: dict[str, int] = field(default_factory=dict)
    lifecycle_latency_s: dict[str, float] = field(default_factory=dict)
    ai_deliverable_latency_s: dict[str, float] = field(default_factory=dict)
    ai_trace_latency_s: dict[str, float] = field(default_factory=dict)
    http_error_breakdown: dict[str, int] = field(default_factory=dict)
    exception_breakdown: dict[str, int] = field(default_factory=dict)
    per_instance: list[dict[str, Any]] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _idem() -> str:
    return str(uuid.uuid4())


def _headers(idem: str, instance_label: str) -> dict[str, str]:
    return {
        "Idempotency-Key": idem,
        "Content-Type": "application/json",
        "X-Experiment-Instance": instance_label,
    }


def _post_retry(
    client: httpx.Client,
    url: str,
    *,
    json_body: Any | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    retries: int = 2,
    backoff: float = 0.15,
) -> httpx.Response:
    """Minimal retry wrapper — surfaces the server/client pressure that
    shows up at scale (connection resets, pool exhaustion, transient 5xx)
    without completely hiding it. Retries only on transport errors + 5xx.
    """
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = client.post(url, json=json_body, headers=headers, timeout=timeout)
            if r.status_code < 500:
                return r
            last_exc = httpx.HTTPStatusError(
                f"{r.status_code} {r.text[:200]}", request=r.request, response=r
            )
        except httpx.RequestError as e:
            last_exc = e
        if attempt < retries:
            time.sleep(backoff * (attempt + 1))
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# Agent lifecycle
# ---------------------------------------------------------------------------


_STRICT_SPEC = {
    "max_budget": "100",
    "output_schema": {"type": "json-schema", "definition": {"required": ["result"]}},
}


def _spec_for_agent(agent_id: str) -> dict[str, Any]:
    body = dict(_STRICT_SPEC)
    body["task_description"] = f"{agent_id} scale happy path"
    body["callback_url"] = None
    return body


def _run_one_agent(
    client: httpx.Client,
    base: str,
    *,
    instance_label: str,
    agent_id: str,
    submit_bad: bool,
    ai_backend: str,
    run_ai_trace: bool,
) -> AgentResult:
    t0 = time.perf_counter()
    job_id: str | None = None
    outcome = "exception"
    http_status: int | None = None
    verify_passed: bool | None = None
    verify_action: str | None = None
    settled = False
    refunded = False
    error: str | None = None
    try:
        # ---- Create --------------------------------------------------
        r = _post_retry(
            client,
            f"{base}/jobs",
            json_body=_spec_for_agent(agent_id),
            headers=_headers(_idem(), instance_label),
        )
        http_status = r.status_code
        r.raise_for_status()
        job_id = r.json()["job_id"]

        # ---- Handshake -----------------------------------------------
        r = _post_retry(
            client,
            f"{base}/jobs/{job_id}/handshake/accept",
            json_body={"doer_id": agent_id, "dispute_policy": "refund"},
            headers=_headers(_idem(), instance_label),
        )
        r.raise_for_status()

        # ---- Fund ----------------------------------------------------
        r = _post_retry(
            client,
            f"{base}/jobs/{job_id}/fund",
            headers=_headers(_idem(), instance_label),
        )
        r.raise_for_status()

        # ---- Start ---------------------------------------------------
        r = _post_retry(client, f"{base}/jobs/{job_id}/start")
        r.raise_for_status()

        # ---- Submit --------------------------------------------------
        deliverable_content: dict[str, Any]
        if submit_bad:
            deliverable_content = {"answer": f"{agent_id}-wrong-shape"}
        else:
            deliverable_content = {"result": f"ok from {agent_id}"}
        packet = {
            "deliverable": {"content": deliverable_content, "mime_type": "application/json"},
            "evidence": [],
        }
        r = _post_retry(
            client,
            f"{base}/jobs/{job_id}/submit",
            json_body=packet,
            headers=_headers(_idem(), instance_label),
        )
        r.raise_for_status()

        # ---- Verify (deterministic gate) -----------------------------
        r = _post_retry(client, f"{base}/jobs/{job_id}/verify")
        r.raise_for_status()
        vj = r.json()
        verify_passed = bool(vj.get("verified"))
        verify_action = vj.get("action")

        if verify_passed:
            r = _post_retry(
                client,
                f"{base}/jobs/{job_id}/settle",
                headers=_headers(_idem(), instance_label),
            )
            r.raise_for_status()
            settled = True
            outcome = "settled"
        else:
            r = _post_retry(
                client,
                f"{base}/jobs/{job_id}/refund",
                headers=_headers(_idem(), instance_label),
            )
            r.raise_for_status()
            refunded = True
            outcome = "refunded" if submit_bad else "verify_failed"

    except httpx.HTTPStatusError as e:
        outcome = "http_error"
        http_status = e.response.status_code if e.response else http_status
        error = f"{http_status}:{(e.response.text[:200] if e.response else '')}"
    except httpx.RequestError as e:
        outcome = "http_error"
        error = f"request_error:{type(e).__name__}:{e}"
    except Exception as e:  # pragma: no cover - defensive
        outcome = "exception"
        error = f"{type(e).__name__}:{e}"

    lifecycle_s = time.perf_counter() - t0

    # ---- AI verification layer (HW8) ----------------------------------
    ai_deliverable: dict[str, Any] | None = None
    ai_deliverable_s: float | None = None
    ai_trace: dict[str, Any] | None = None
    ai_trace_s: float | None = None
    if job_id and outcome in ("settled", "refunded", "verify_failed"):
        try:
            t_ai = time.perf_counter()
            r = _post_retry(
                client,
                f"{base}/jobs/{job_id}/verify_ai",
                json_body={"backend": ai_backend},
                headers={"Content-Type": "application/json"},
                retries=1,
            )
            ai_deliverable_s = time.perf_counter() - t_ai
            if r.status_code < 400:
                ai_deliverable = r.json()
        except Exception as e:  # pragma: no cover - defensive
            ai_deliverable = {"error": f"{type(e).__name__}:{e}"}

        if run_ai_trace:
            try:
                t_ai = time.perf_counter()
                r = _post_retry(
                    client,
                    f"{base}/jobs/{job_id}/verify_trace",
                    json_body={"backend": ai_backend},
                    headers={"Content-Type": "application/json"},
                    retries=1,
                )
                ai_trace_s = time.perf_counter() - t_ai
                if r.status_code < 400:
                    ai_trace = r.json()
            except Exception as e:  # pragma: no cover - defensive
                ai_trace = {"error": f"{type(e).__name__}:{e}"}

    return AgentResult(
        instance_label=instance_label,
        agent_id=agent_id,
        job_id=job_id,
        outcome=outcome,
        verify_passed=verify_passed,
        verify_action=verify_action,
        settled=settled,
        refunded=refunded,
        lifecycle_s=round(lifecycle_s, 4),
        ai_deliverable=ai_deliverable,
        ai_deliverable_s=round(ai_deliverable_s, 4) if ai_deliverable_s is not None else None,
        ai_trace=ai_trace,
        ai_trace_s=round(ai_trace_s, 4) if ai_trace_s is not None else None,
        http_status=http_status,
        error=error,
    )


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


def _percentiles(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {"count": 0}
    xs_sorted = sorted(xs)
    return {
        "count": len(xs),
        "mean": round(statistics.mean(xs_sorted), 4),
        "p50": round(statistics.median(xs_sorted), 4),
        "p95": round(xs_sorted[min(len(xs_sorted) - 1, int(0.95 * len(xs_sorted)))], 4),
        "p99": round(xs_sorted[min(len(xs_sorted) - 1, int(0.99 * len(xs_sorted)))], 4),
        "max": round(max(xs_sorted), 4),
    }


def run_scale(
    *,
    base: str,
    total_agents: int,
    instances: int,
    bad_rate: float,
    ai_backend: str,
    ai_sample_rate: float,
    seed: int = 17,
    max_workers_per_instance: int | None = None,
) -> ScaleReport:
    """Run the scale experiment. See module docstring for the design."""
    base = base.rstrip("/")
    total_agents = max(1, total_agents)
    instances = max(1, min(instances, total_agents))
    bad_rate = max(0.0, min(1.0, bad_rate))
    ai_sample_rate = max(0.0, min(1.0, ai_sample_rate))

    rnd = random.Random(seed)

    # Distribute agents round-robin across "instances" so each instance
    # gets roughly equal work, matching a fleet of identical cloud VMs.
    instance_labels = [f"scale-inst-{i + 1}" for i in range(instances)]
    assignments: dict[str, list[str]] = {label: [] for label in instance_labels}
    for i in range(total_agents):
        label = instance_labels[i % instances]
        assignments[label].append(f"doer-{label}-{i + 1:04d}")

    # Pre-assign which agents submit a bad deliverable and which get full
    # AI trace audit (sampling keeps LLM cost predictable).
    bad_set: set[str] = set()
    ai_trace_set: set[str] = set()
    for agents in assignments.values():
        for agent in agents:
            if rnd.random() < bad_rate:
                bad_set.add(agent)
            if rnd.random() < ai_sample_rate:
                ai_trace_set.add(agent)

    # One httpx.Client per "instance" = its own connection pool + its own
    # thread pool, same as running the script on that many VMs.
    workers_per_inst = max_workers_per_instance or max(
        4, (total_agents // max(instances, 1)) + 2
    )

    results: list[AgentResult] = []
    inst_summaries: dict[str, InstanceSummary] = {
        label: InstanceSummary(label=label, agents=len(assignments[label]))
        for label in instance_labels
    }
    inst_start_times: dict[str, float] = {}
    inst_end_times: dict[str, float] = {}

    t_wall_start = time.perf_counter()

    def _run_instance(label: str, agent_ids: list[str]) -> list[AgentResult]:
        inst_start_times[label] = time.perf_counter()
        limits = httpx.Limits(
            max_connections=workers_per_inst * 2,
            max_keepalive_connections=workers_per_inst,
        )
        with httpx.Client(limits=limits, timeout=60.0) as client:
            with ThreadPoolExecutor(max_workers=workers_per_inst) as tp:
                futs = [
                    tp.submit(
                        _run_one_agent,
                        client,
                        base,
                        instance_label=label,
                        agent_id=agent_id,
                        submit_bad=(agent_id in bad_set),
                        ai_backend=ai_backend,
                        run_ai_trace=(agent_id in ai_trace_set),
                    )
                    for agent_id in agent_ids
                ]
                inst_results: list[AgentResult] = []
                for f in as_completed(futs):
                    inst_results.append(f.result())
        inst_end_times[label] = time.perf_counter()
        return inst_results

    # Launch instances themselves in parallel — this is what produces real
    # cross-client contention on the server (multiple connection pools
    # hammering the same FastAPI process).
    with ThreadPoolExecutor(max_workers=instances) as tp:
        futs = {
            tp.submit(_run_instance, label, agents): label
            for label, agents in assignments.items()
        }
        for f in as_completed(futs):
            label = futs[f]
            inst_results = f.result()
            results.extend(inst_results)
            summ = inst_summaries[label]
            for r in inst_results:
                if r.outcome == "settled":
                    summ.settled += 1
                elif r.outcome == "refunded":
                    summ.refunded += 1
                elif r.outcome == "verify_failed":
                    summ.verify_failed += 1
                elif r.outcome == "http_error":
                    summ.http_errors += 1
                else:
                    summ.exceptions += 1
            summ.wall_s = round(
                inst_end_times.get(label, 0) - inst_start_times.get(label, 0), 4
            )

    wall = time.perf_counter() - t_wall_start

    # ---- Aggregate ----------------------------------------------------
    counts = {
        "settled": sum(1 for r in results if r.outcome == "settled"),
        "refunded": sum(1 for r in results if r.outcome == "refunded"),
        "verify_failed": sum(1 for r in results if r.outcome == "verify_failed"),
        "http_error": sum(1 for r in results if r.outcome == "http_error"),
        "exception": sum(1 for r in results if r.outcome == "exception"),
        "total": len(results),
    }
    lifecycle_latencies = [r.lifecycle_s for r in results]
    ai_del_latencies = [
        r.ai_deliverable_s for r in results if r.ai_deliverable_s is not None
    ]
    ai_trace_latencies = [r.ai_trace_s for r in results if r.ai_trace_s is not None]

    http_breakdown: dict[str, int] = {}
    exc_breakdown: dict[str, int] = {}
    for r in results:
        if r.outcome == "http_error":
            key = str(r.http_status) if r.http_status else "request_error"
            http_breakdown[key] = http_breakdown.get(key, 0) + 1
        if r.outcome == "exception" and r.error:
            key = r.error.split(":", 1)[0]
            exc_breakdown[key] = exc_breakdown.get(key, 0) + 1

    per_instance = [
        {**asdict(s), "throughput_jobs_per_s": round(s.agents / s.wall_s, 2) if s.wall_s else 0.0}
        for s in inst_summaries.values()
    ]

    report = ScaleReport(
        started_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - wall)),
        ended_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        base_url=base,
        total_agents=total_agents,
        instances=instances,
        bad_rate=bad_rate,
        ai_backend=ai_backend,
        ai_sample_rate=ai_sample_rate,
        wall_s=round(wall, 3),
        throughput_jobs_per_s=round(len(results) / wall, 2) if wall else 0.0,
        counts=counts,
        lifecycle_latency_s=_percentiles(lifecycle_latencies),
        ai_deliverable_latency_s=_percentiles(ai_del_latencies),
        ai_trace_latency_s=_percentiles(ai_trace_latencies),
        http_error_breakdown=http_breakdown,
        exception_breakdown=exc_breakdown,
        per_instance=per_instance,
        results=[asdict(r) for r in results],
    )
    return report


def _print_summary(rep: ScaleReport) -> None:
    c = rep.counts
    print(f"\n=== HW8 scale report ({rep.total_agents} agents, {rep.instances} instances) ===")
    print(f"base: {rep.base_url}")
    print(f"wall: {rep.wall_s}s  throughput: {rep.throughput_jobs_per_s} jobs/s")
    print(
        "outcomes: "
        f"settled={c['settled']}  refunded={c['refunded']}  "
        f"verify_failed={c['verify_failed']}  http_error={c['http_error']}  "
        f"exception={c['exception']}  (total={c['total']})"
    )
    ll = rep.lifecycle_latency_s
    if ll.get("count"):
        print(
            f"lifecycle latency (s): p50={ll['p50']}  p95={ll['p95']}  p99={ll['p99']}  max={ll['max']}"
        )
    ad = rep.ai_deliverable_latency_s
    if ad.get("count"):
        print(
            f"AI deliverable latency (s) [{rep.ai_backend}]: p50={ad['p50']}  p95={ad['p95']}  p99={ad['p99']}"
        )
    at = rep.ai_trace_latency_s
    if at.get("count"):
        print(
            f"AI trace-audit latency (s): p50={at['p50']}  p95={at['p95']}  p99={at['p99']}"
        )
    if rep.http_error_breakdown:
        print(f"HTTP error breakdown: {rep.http_error_breakdown}")
    if rep.exception_breakdown:
        print(f"Exception breakdown: {rep.exception_breakdown}")
    print("per-instance:")
    for i in rep.per_instance:
        print(
            f"  {i['label']:<20} agents={i['agents']:<4} "
            f"settled={i['settled']:<4} refunded={i['refunded']:<4} "
            f"http_errors={i['http_errors']:<4} "
            f"wall={i['wall_s']}s  throughput={i['throughput_jobs_per_s']} j/s"
        )


def main() -> None:
    p = argparse.ArgumentParser(description="HW8 scale experiment runner")
    p.add_argument("--base", default=DEFAULT_BASE, help="Escrow API base URL")
    p.add_argument("--agents", type=int, default=30, help="Total doer agents (>=30 for HW8)")
    p.add_argument(
        "--instances", type=int, default=3, help="Concurrent cloud-instance simulators"
    )
    p.add_argument(
        "--bad-rate",
        type=float,
        default=0.2,
        help="Fraction of agents that submit a bad (spec-violating) deliverable",
    )
    p.add_argument(
        "--ai-backend",
        choices=("auto", "openai", "heuristic"),
        default="heuristic",
        help="AI verification backend. `heuristic` is offline/free.",
    )
    p.add_argument(
        "--ai-sample",
        type=float,
        default=1.0,
        help="Fraction of agents that additionally get the AI trace audit (0.0-1.0).",
    )
    p.add_argument("--seed", type=int, default=17)
    p.add_argument(
        "--workers-per-instance",
        type=int,
        default=0,
        help="Concurrent agents per instance (0 = auto).",
    )
    p.add_argument(
        "--out",
        default=None,
        help="Write the JSON report to this path (default experiments/results/<date>_scale-<N>.json).",
    )
    args = p.parse_args()

    rep = run_scale(
        base=args.base,
        total_agents=args.agents,
        instances=args.instances,
        bad_rate=args.bad_rate,
        ai_backend=args.ai_backend,
        ai_sample_rate=args.ai_sample,
        seed=args.seed,
        max_workers_per_instance=args.workers_per_instance or None,
    )

    _print_summary(rep)

    out_path: Path
    if args.out:
        out_path = Path(args.out)
    else:
        root = Path(__file__).resolve().parent / "results"
        root.mkdir(parents=True, exist_ok=True)
        out_path = root / f"{date.today().isoformat()}_scale-{args.agents}.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(asdict(rep), indent=2))
    print(f"\nwrote report -> {out_path}")


if __name__ == "__main__":
    main()
