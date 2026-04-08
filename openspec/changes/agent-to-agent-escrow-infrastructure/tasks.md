# Tasks: Agent-to-Agent Escrow Infrastructure

## 0. Project setup
- [ ] Define Job Spec + Job Contract JSON schemas
- [ ] Implement job_id generation + idempotency keys

## 1. Core job lifecycle
- [ ] Implement job state machine with guarded transitions
- [ ] Persist job state + artifacts (contract, evidence, report)

## 2. Handshake & doer coordination
- [ ] Implement doer acceptance/counteroffer endpoint
- [ ] Support async status updates / progress events

## 3. Payments + ledger
- [ ] Implement payments adapter interface (authorize/hold/release/refund)
- [ ] Implement double-entry ledger and reconciliation checks

## 4. Completion submission
- [ ] Implement completion packet upload + storage
- [ ] Enforce output schema validation on submission

## 5. Verification
- [ ] Add deterministic verification hook (unit tests / validators)
- [ ] Add rubric evaluator hook (configurable)
- [ ] Produce Verification Report artifact

## 6. Settlement + callbacks
- [ ] Implement callback/webhook delivery to requester
- [ ] Implement settlement (release) and refund flows
- [ ] Add retry/backoff for webhook delivery

## 7. Observability & safety
- [ ] Add audit logs for all state transitions
- [ ] Add metrics: completion rate, dispute rate, payout latency
- [ ] Add rate-limiting and abuse controls
