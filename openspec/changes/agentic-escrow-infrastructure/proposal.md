## Why

Autonomous agents increasingly delegate work to other agents (research, browsing, code generation, data processing). For long-running tasks (>1s) and uncertain outcomes, the requesting agent risks paying without receiving a correct result, while the doer agent risks doing work without getting paid. Without an escrow primitive, agent marketplaces and delegation networks are fragile and hard to automate.

## What Changes

- Add an escrow middleware layer that enables safe, programmable agent-to-agent transactions for long-running tasks
- Implement structured task intake with Job Spec (output schema, constraints, SLA, max budget, evaluation rubric)
- Add doer handshake flow (accept/counteroffer) before funding
- Implement payments adapter (hold/release/refund) with double-entry ledger
- Add completion packet submission with deliverable + evidence storage
- Implement verification service (deterministic checks, rubric evaluator) that gates settlement
- Add callback/webhook delivery to requester with retries on transient failures
- Add audit logs and metrics for settlement actions

## Capabilities

### New Capabilities

- `escrow-infrastructure`: Full agent-to-agent escrow lifecycle—task intake, doer handshake, payment hold, execution authorization, completion verification, and settlement. Covers structured job spec, capability tokens, async execution, completion packets, verification gates, and callbacks.

### Modified Capabilities

<!-- No existing capabilities modified -->

## Impact

- New services: Escrow API/Gateway, Contract & Handshake Service, Payments Adapter, Double-entry Ledger, Verification Service, Eventing & Callbacks
- Affected systems: Any agent marketplace or delegation network that needs trustless coordination between requester and doer agents
- Dependencies: Payment rails (mocked or single integration in v0), artifact storage, event bus for callbacks
