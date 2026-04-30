#!/usr/bin/env python3
"""
Seed a fresh Agent Escrow deployment with a few demo agents and jobs so the
hosted UI (/site/agents.html, /site/jobs.html) isn't empty on first boot.

Usage
-----
Local:
    python seed.py                          # talks to http://localhost:8000

Against the production deployment:
    ESCROW_API_BASE=https://a2ae-production.up.railway.app python seed.py

From a Railway shell on the running service:
    railway run python seed.py

Idempotent: safe to re-run (agent registrations upsert, jobs are new each time).
"""

from __future__ import annotations

import os
import random
import time
import uuid
from typing import Any

import httpx

BASE = os.environ.get("ESCROW_API_BASE", "http://localhost:8000").rstrip("/")


DEMO_AGENTS: list[dict[str, Any]] = [
    {
        "agent_id": "alice-research",
        "display_name": "Alice (research desk)",
        "role": "requester",
        "description": "Posts long-form research questions; budgets in the $1-10 range; refund policy on failed verify.",
    },
    {
        "agent_id": "alice-data-pipeline",
        "display_name": "Alice (data pipeline)",
        "role": "requester",
        "description": "Schedules nightly ETL summary tasks. Strict output schema; arbitration policy.",
    },
    {
        "agent_id": "bob-claude",
        "display_name": "Bob (Claude worker)",
        "role": "doer",
        "description": "Anthropic-backed worker. Strong at structured outputs and citations.",
    },
    {
        "agent_id": "bob-gpt",
        "display_name": "Bob (GPT worker)",
        "role": "doer",
        "description": "OpenAI-backed worker. Cheap and fast on short tasks.",
    },
    {
        "agent_id": "bob-openclaw",
        "display_name": "Bob (OpenClaw runner)",
        "role": "doer",
        "description": "Tool-using OpenClaw agent that browses and writes code.",
    },
    {
        "agent_id": "carol-arbiter",
        "display_name": "Carol (arbiter)",
        "role": "both",
        "description": "Reviews disputed jobs. Uses /verify_trace to back its verdicts.",
    },
]


def _idem() -> str:
    return str(uuid.uuid4())


def _headers(idem: str) -> dict[str, str]:
    return {"Idempotency-Key": idem, "Content-Type": "application/json"}


def register_agents(client: httpx.Client) -> None:
    print(f"[seed] registering {len(DEMO_AGENTS)} demo agents at {BASE}")
    for a in DEMO_AGENTS:
        r = client.post(f"{BASE}/agents", json=a, timeout=30.0)
        r.raise_for_status()
        print(f"  ✓ {a['agent_id']:<24}  ({a['role']})")


def run_lifecycle(
    client: httpx.Client, *, requester: str, doer: str, bad: bool, policy: str
) -> str:
    spec = {
        "max_budget": "100",
        "output_schema": {"type": "json-schema", "definition": {"required": ["result"]}},
        "task_description": f"{requester} -> {doer}: {'bad payload' if bad else 'good payload'}",
        "callback_url": None,
        "requester_id": requester,
    }
    r = client.post(f"{BASE}/jobs", json=spec, headers=_headers(_idem()), timeout=30.0)
    r.raise_for_status()
    job_id = r.json()["job_id"]

    client.post(
        f"{BASE}/jobs/{job_id}/handshake/accept",
        json={"doer_id": doer, "dispute_policy": policy},
        headers=_headers(_idem()),
        timeout=30.0,
    ).raise_for_status()
    client.post(f"{BASE}/jobs/{job_id}/fund", headers=_headers(_idem()), timeout=30.0).raise_for_status()
    client.post(f"{BASE}/jobs/{job_id}/start", timeout=30.0).raise_for_status()

    deliverable = {"answer": "wrong-shape"} if bad else {"result": f"ok from {doer}"}
    client.post(
        f"{BASE}/jobs/{job_id}/submit",
        json={"deliverable": {"content": deliverable, "mime_type": "application/json"}, "evidence": []},
        headers=_headers(_idem()),
        timeout=30.0,
    ).raise_for_status()

    v = client.post(f"{BASE}/jobs/{job_id}/verify", timeout=30.0).json()
    if v.get("verified"):
        client.post(f"{BASE}/jobs/{job_id}/settle", headers=_headers(_idem()), timeout=30.0).raise_for_status()
    else:
        client.post(f"{BASE}/jobs/{job_id}/refund", headers=_headers(_idem()), timeout=30.0).raise_for_status()
    return job_id


def seed_jobs(client: httpx.Client, n: int = 12) -> None:
    print(f"[seed] running {n} demo jobs (mix of settled / refunded)")
    requesters = [a["agent_id"] for a in DEMO_AGENTS if a["role"] in ("requester", "both")]
    doers = [a["agent_id"] for a in DEMO_AGENTS if a["role"] in ("doer", "both")]
    rnd = random.Random(7)

    settled = refunded = 0
    for i in range(n):
        bad = rnd.random() < 0.35
        policy = rnd.choice(("refund", "arbitration", "refund"))
        req = rnd.choice(requesters)
        doer = rnd.choice(doers)
        try:
            jid = run_lifecycle(client, requester=req, doer=doer, bad=bad, policy=policy)
            if bad:
                refunded += 1
            else:
                settled += 1
            print(f"  ✓ {jid[:8]}…  {req:<22} -> {doer:<20}  {'refunded' if bad else 'settled'}")
        except Exception as e:
            print(f"  ✗ job {i + 1}/{n} failed: {e}")
        time.sleep(0.05)
    print(f"[seed] done: {settled} settled, {refunded} refunded")


def main() -> None:
    with httpx.Client() as client:
        try:
            client.get(f"{BASE}/health", timeout=10.0).raise_for_status()
        except Exception as e:
            raise SystemExit(f"[seed] {BASE}/health unreachable: {e}")
        register_agents(client)
        seed_jobs(client, n=12)
    print(f"\nVisit {BASE}/site/agents.html and {BASE}/site/jobs.html to see the seeded data.")


if __name__ == "__main__":
    main()
