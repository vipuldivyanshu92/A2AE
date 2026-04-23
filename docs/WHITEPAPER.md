# Agent Escrow — an escrow primitive for agent-to-agent work

**Status:** v0.2 (open source, MIT) — 2026-04-22
**Scope:** protocol, implementation, and measurements for a minimal escrow service between autonomous agents.

---

## 1. Problem

Autonomous agents are beginning to delegate real work to other autonomous agents — research, code generation, data processing, browsing, fulfillment. Two asymmetric risks make this fragile today:

1. The **requesting agent** pays and receives nothing verifiable.
2. The **doing agent** works and never gets paid.

Classical solutions (human arbitration, reputational systems, prepaid marketplaces) don't compose with long-running, uncertain, machine-to-machine tasks. What's missing is a small, shared primitive agents can *call* the way humans call a credit-card network: a service that holds funds, verifies completion against an explicit contract, and settles atomically with a full audit trail.

## 2. Goals and non-goals

**Goals.** Make agent work safe to buy and sell using a **funded escrow + verifiable completion** loop. Support async/long-running tasks with explicit timeouts and dispute policies. Produce a machine-readable **audit trail** (contract, ledger, evidence, verification report) so downstream systems — whether humans, arbitrators, or AI auditors — can reason about what happened.

**Non-goals (v0).** Not a global payments stack; the payments adapter is mockable. Not a solver for generalized truth on open-ended tasks; verification is contract-scoped. No underwriting or credit.

## 3. Protocol

The escrow service exposes a state machine that both parties drive via REST:

```
CREATED → NEGOTIATED → FUNDED → IN_PROGRESS → SUBMITTED → VERIFIED → SETTLED
                                                               └────→ REFUNDED
```

Every transition is audited; every mutating endpoint takes an idempotency key.

**Contract-first.** At handshake, requester and doer lock in a **Job Contract** that captures: the finalized `JobSpec` (output schema, constraints, SLA, budget, optional rubric), the agreed amount and deadline, callback URL, and the **dispute policy** (`retry | arbitration | refund`). The contract is the single source of truth the rest of the system is judged against.

**Deterministic gate.** `POST /jobs/{id}/verify` runs schema checks against the submitted deliverable. On failure it returns `{verified: false, action: <dispute_policy>}` — the action field is the contract's policy echoed back, so downstream automations can branch deterministically without re-reading the contract.

**Scoped execution.** The `/start` endpoint issues a capability token tied to the job id. Funds are held before execution begins; they cannot be released without a passed deterministic check.

**Atomic settlement.** `/settle` is idempotent and double-entry-ledgered. Repeated calls do not double-pay; refunds follow the same rule.

## 4. The AI Verification Engine

The deterministic gate is small and strict. But agents want richer checks — "did Bob actually honor the contract?" is a different question than "does the JSON have the required keys?". v0.2 adds a second verifier:

**`AIVerifier.review_deliverable`** reviews Bob's output against the `JobSpec`. Returns `{verdict, score, reasoning, issues}`.

**`AIVerifier.review_negotiation_trace`** takes the *full* trace — `JobSpec`, finalized contract, ordered audit log, deliverable, evidence, and the deterministic verdict — and audits the whole Alice↔Bob lifecycle:

- did every expected state transition happen?
- does the verify response's `action` match the contract's `dispute_policy` (no policy drift)?
- does the deliverable honor the agreed output schema?
- are there structural inconsistencies?

**Design principles:**

1. **The AI verifier is a pure auditor.** It never mutates job state. The deterministic `/verify` remains the only thing that can gate settlement. The AI verdict is audit evidence, which arbitrators or callers can act on.
2. **Two backends, one interface.** `openai` (with JSON response format + `temperature=0`) when `OPENAI_API_KEY` is set; a deterministic **heuristic** fallback otherwise. Same return shape. Same endpoints. This is what makes 30+ agent scale tests affordable, and it makes the engine usable offline / in CI.
3. **External auditability.** `GET /jobs/{id}/trace` returns the full Alice↔Bob trace in one JSON blob so *any* external agent (peer auditor, bounty runner, arbitrator) can reason about it without scraping the API.

## 5. Measurements

A single FastAPI + SQLite node, 3–8 concurrent "cloud instance" simulators (each with its own `httpx` connection pool), 20% bad-deliverable rate:

| Agents | Instances | Throughput | p50 lifecycle | p95 | Errors |
|---:|---:|---:|---:|---:|---:|
| 30  | 3 | 38 jobs/s | 0.48 s | 0.72 s | 0 |
| 60  | 6 | 39 jobs/s | 1.01 s | 1.42 s | 0 |
| 120 | 8 | 39 jobs/s | 2.39 s | 2.89 s | 0 |

Throughput plateaus at ~39 jobs/s independent of agent count — the single-writer SQLite lock is the ceiling. p50 latency grows linearly with concurrency. No HTTP errors up to 120 agents. The HW8 scale sweep also surfaced a real bug in the heuristic's state-transition accounting (the initial `CREATED` state only appears as a `from_status` on the first transition, not as a `to_status`) that a one-off demo would have missed. Moving to Postgres with a connection pool is the next production step.

## 6. What this enables

Once agents can *commit* to each other's work, a number of follow-on systems become tractable:

- **Peer-to-peer agent marketplaces** where listings are `JobSpec`s and reputations are signed trace bundles.
- **Arbitration agents** that consume `GET /trace` and produce signed verdicts under a known policy.
- **Bounty markets** on top of the dispute policy — if verification fails, an arbitrator agent can claim part of the held funds by producing a better-reasoned AI trace review.
- **Multi-step workflows** where the output of one escrow job is the input to another, with the audit chain preserved across jobs.

## 7. Limitations

- **SQLite ceiling** (~40 jobs/s on one node). Postgres is the first production move.
- **Mocked payments adapter** — real PSP integration is the adapter's job.
- **Trusted caller identity** in v0. Mutating endpoints require `Idempotency-Key`, but no signature. Production deployments should sit behind mTLS / OAuth.
- **No retrying webhook worker** in v0 — the field is in the contract, but there's no background delivery loop.
- **AI verifier is advisory only** — by design. Moving funds based on an LLM verdict belongs in a separate system with its own policy.

## 8. Open source

Apache-style pragmatism, MIT license. The repo is a single Python package plus one optional React UI; the Railway deployment is a single service. Contributions and framework integrations (OpenClaw, LangGraph, Temporal, custom runners) are welcome — any agent framework that can do REST with idempotency keys is compatible.

See `README.md` for setup and `experiments/EXPERIMENT_SUMMARY_HW8.md` for the full scale numbers.
