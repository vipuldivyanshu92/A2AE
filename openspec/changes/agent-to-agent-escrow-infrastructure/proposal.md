# Proposal: Agent-to-Agent Escrow Infrastructure

## Summary
Build an escrow middleware layer that enables **safe, programmable, agent-to-agent transactions** for long-running tasks. The escrow service coordinates task intake, doer handshake, payment hold, execution authorization, completion verification, and settlement.

## Problem
Autonomous agents increasingly **delegate work to other agents** (research, browsing, code generation, data processing). For long-running tasks (>1s) and outcome uncertainty, there is a classic trust gap:

- The **requesting agent** risks paying without receiving a correct result.
- The **doer agent** risks doing work without getting paid.

Without an escrow primitive, agent marketplaces and delegation networks are fragile, hard to automate, and prone to fraud/disputes.

## Goals
- **Make agent work safe to buy and safe to sell** using funded escrow + verifiable completion.
- Support **async/long-running tasks** with progress events, timeouts, and retries.
- Provide a **clear contract + audit trail** for every job (terms, ledger, evidence, verification report).
- Offer **callback-first integration** so agents can operate without human intervention.

## Non-goals (for v0)
- Not building a full money-transmission platform or global rail coverage.
- Not solving generalized “truth” for all open-ended tasks; v0 focuses on definable rubrics and evidence.
- Not implementing credit underwriting or dynamic pricing marketplaces.

## Key artifacts
- **Job Spec**: structured task request (schema, constraints, SLA, evaluation rubric).
- **Job Contract**: accepted terms (price, refund/partial payout, evidence, verification procedure).
- **Escrow Hold**: locked funds for the job.
- **Start Token**: capability that authorizes doer execution only after funding.
- **Completion Packet**: deliverable + evidence bundle.
- **Verification Report**: pass/fail + scores/traces.

## Why now
- Agents are getting more autonomous and multi-agent coordination is mainstream.
- Agent “economies” require an economic layer: **payments, metering, escrow, billing**.
- Escrow is a minimal, composable primitive that unlocks higher-level coordination and marketplaces.

## Success metrics
- ≥99% correctness of state transitions (no double-pay / missed refunds).
- Measurable improvement in transaction completion rate vs direct peer-to-peer.
- Low dispute rate per 1,000 jobs (or quick resolution time).
- High developer satisfaction: “easy to plug into my agent framework.”

## Risks
- Verification ambiguity for open-ended tasks; evaluators can be noisy or gameable.
- Fraud attempts (doer submits low-effort outputs; requester disputes in bad faith).
- Rail constraints (chargebacks, reversals) depending on payment method.

## MVP scope
- 1–2 payment methods (mock or testnet) + ledger holds/releases
- Job contract schema + state machine
- Callback/webhook delivery to requesting agent
- Deterministic verification hooks + rubric-based evaluator option
