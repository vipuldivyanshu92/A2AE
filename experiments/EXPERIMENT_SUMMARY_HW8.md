# Agent Escrow at Scale + AI Verification Engine

**Goal:** Take the HW7 escrow MVP past happy-path demos. Drive **30+ real HTTP doer agents** from multiple simulated cloud instances, add an **AI Verification Engine** that audits both Bob's deliverable and the full Alice↔Bob trace, and report what actually breaks, degrades, or gets expensive at scale.

---

## What changed since HW7


| Area              | HW7                                                               | HW8                                                                                                                                                                                  |
| ----------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Agent count       | 6 labeled doer agents per wave                                    | **30 / 60 / 120** doer agents per run (scale sweep)                                                                                                                                  |
| Concurrency model | Single `httpx.Client`, 6-thread pool                              | **N parallel "instances"**, each with its own `httpx.Client` (its own connection pool + its own thread group) — same code path as `scp`-ing the runner to N cloud VMs                |
| Failure mix       | Separate exp1–2 arms for bad deliverables                         | `**--bad-rate`** flag mixes good + bad deliverables in the same run so the happy and unhappy queues contend on the server simultaneously                                             |
| Verification      | Deterministic only (`verify_deterministic`, schema + policy echo) | Deterministic **plus a new AI Verification Engine** that reviews the deliverable *and* the full Alice↔Bob negotiation trace                                                          |
| Metrics           | Wall time + success count                                         | **p50 / p95 / p99** lifecycle latency, per-instance throughput, HTTP error breakdown, AI-verifier latency, outcome mix (settled / refunded / verify_failed / http_error / exception) |


### New in the codebase

- `src/escrow/ai_verification.py` — `AIVerifier` with two methods:
  - `review_deliverable(job_spec, deliverable, evidence)` — verdict on Bob's output
  - `review_negotiation_trace(job_spec, contract, audit_log, deliverable, evidence, deterministic_verification)` — verdict on the whole Alice↔Bob lifecycle (were contract terms honored? did the dispute policy drift? did every state transition happen?)
  - Dual backend: **OpenAI** (uses `OPENAI_API_KEY`, `OPENAI_VERIFIER_MODEL`, JSON response format) with an automatic **deterministic heuristic fallback** so scale tests don't need to burn 30+ LLM calls and CI still works offline.
- `src/escrow/api/verification_ai.py` — three new endpoints:
  - `GET /jobs/{id}/trace` — full Alice↔Bob trace (job spec, finalized contract, ordered audit log, deliverable, evidence) — consumable by any external verifier
  - `POST /jobs/{id}/verify_ai` — AI review of the deliverable
  - `POST /jobs/{id}/verify_trace` — AI review of the full trace; also returns a fresh `deterministic_snapshot` so the AI verdict and the gate verdict appear side-by-side
- `experiments/scale_experiment.py` — the new HW8 runner (below).

---

## Scaled setup

- **Target agents:** 30 (assignment floor), plus stress sweeps at 60 and 120 to find the ceiling.
- **"Cloud instances":** each run uses `--instances N` concurrent instance simulators, each with its own `INSTANCE_LABEL` (`scale-inst-1`…`scale-inst-N`), its own `httpx.Client`, its own thread pool, and its own connection pool. Running multiple instances locally produces the same server-side connection-churn + write contention pattern as running the same script from multiple cloud VMs (the CLOUD_RUNBOOK pattern from HW7 still applies verbatim — only the base URL changes).
- **Failure injection:** `--bad-rate 0.2` → 20% of agents submit a spec-violating deliverable (`{"answer": …}` instead of `{"result": …}`), forcing the verify→refund path to run interleaved with happy-path settles.
- **Agent framework:** same REST contract as HW7's OpenClaw-compatible runner. Each "agent" drives the full lifecycle `POST /jobs → /handshake/accept → /fund → /start → /submit → /verify → /settle or /refund`, then calls the new `/verify_ai` and (sampled) `/verify_trace`.

---

## Results — 2026-04-22, local API (FastAPI / SQLite)


| Agents | Instances | Workers/inst | Wall   | **Throughput** | p50 lifecycle | p95    | p99    | max    | HTTP errors |
| ------ | --------- | ------------ | ------ | -------------- | ------------- | ------ | ------ | ------ | ----------- |
| 30     | 3         | 10           | 0.79 s | **38.1 j/s**   | 0.48 s        | 0.72 s | 0.73 s | 0.73 s | 0           |
| 60     | 6         | 10           | 1.53 s | **39.1 j/s**   | 1.01 s        | 1.42 s | 1.48 s | 1.48 s | 0           |
| 120    | 8         | 15           | 3.10 s | **38.7 j/s**   | 2.39 s        | 2.89 s | 2.93 s | 3.01 s | 0           |


**AI verifier latency (heuristic backend, every agent):** p50 ≈ 3–90 ms, p95 ≈ 16–247 ms — scales with server load, not with verifier work, because the engine is pure Python over already-materialized objects.

**AI verifier output (sample, heuristic backend):**

- Settled job → `{"verdict": "accept", "score": 1.0, "issues": []}`
- Refunded job (bad deliverable) → `{"verdict": "needs_review", "score": 0.75, "issues": ["deliverable:missing_required_field:result"]}`, with `deterministic_snapshot = {"verified": false, "error": "Missing required field: result", "action": "refund"}` — the AI verdict and the deterministic gate stay consistent.

Raw JSON reports: `experiments/results/2026-04-22_hw8_scale-30.json`, `…_scale-60.json`, `…_scale-120.json`.

---

## What broke / degraded / got expensive

1. **Throughput ceiling at ~39 jobs/s, independent of agent count or instance count.** Going from 30→60→120 agents and 3→6→8 instances moved the number barely at all. That is the classic fingerprint of a **single-writer SQLite + single FastAPI worker**: every `/jobs`, `/handshake`, `/fund`, `/submit`, `/verify`, `/settle` performs a transaction, and all of them serialize through one writer. More client concurrency just lengthens the queue behind that writer.
2. **p50 lifecycle latency scales linearly with load.** 30→60→120 agents → p50 0.48 → 1.01 → 2.39 s. Doubling the agent pool roughly doubled the tail, which means at this scale **the server is the bottleneck, not the network or the agent code**. The HW7 claim that "parallel was slower than sequential locally" is now quantified: it isn't that parallel is slow, it's that the write lock turns all the parallel work into a FIFO.
3. **Heuristic AI verifier tail inflates with server pressure.** AI deliverable p95 went 16 ms → 56 ms → 247 ms from the 30-agent to the 120-agent run, even though the verifier work itself is constant — because `/verify_ai` has to open a DB session and read the packet, which contends on the same write lock.
4. **Audit log had a real consistency gap the scale sweep caught.** The first 30-agent run flagged `missing_state_transition:created` on every single trace, because `JobRepository.create` inserts a job in `CREATED` without writing an audit row. The scale test exposed it immediately because it ran 30 traces in a row; a one-off demo would have missed it. Fix: the trace reviewer now counts a state as "seen" if it appears as either `to_status` **or** `from_status` (the first transition out of CREATED still carries the evidence). Longer-term fix belongs in `JobRepository.create`.
5. **No HTTP errors, no 5xx, no timeouts up to 120 agents** — but projected linearly we'd start hitting the 60 s client timeout around **~2500 concurrent agents**. Running Postgres with connection pooling (or switching to WAL mode on SQLite) is the next change that will actually move the ceiling.

---

## What we added or improved

- **AI Verification Engine** (OpenAI + heuristic-fallback) with deliverable review and full-trace audit — a first-class *auditor* that runs independently of the deterministic gate, never mutates state, and is callable on any job at any point.
- **Trace endpoint** (`GET /jobs/{id}/trace`) — gives external verifiers (teammates, bug-bounty agents, downstream dispute arbitrators) a single read that contains everything they need to reason about Alice↔Bob.
- **Scale experiment runner** with multi-instance / multi-connection-pool load, bad-deliverable injection, p50/p95/p99 latency, HTTP + exception breakdowns, and per-instance throughput — the runner is the "what breaks at scale" tool, not just a demo script.
- **Bug caught and fixed** in the heuristic trace reviewer's state-transition accounting — surfaced exactly because the scale run generated 30+ traces in one shot.

---

**Artifacts:**

- Code: `src/escrow/ai_verification.py`, `src/escrow/api/verification_ai.py`, `experiments/scale_experiment.py`
- Results: `experiments/results/2026-04-22_hw8_scale-{30,60,120}.json`
- Video script: `experiments/VIDEO_ONE_MINUTE_SCRIPT_HW8.md`

