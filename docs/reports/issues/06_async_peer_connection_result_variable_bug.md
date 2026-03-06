# [P1] Connection result processing uses wrong variable (`result` vs `conn_result`)

## Summary

In `AsyncPeerConnectionManager.connect_to_peers()`, per-result processing iterates `conn_result`, but exception handling references `result` from a different scope. This can misclassify outcomes, break failure accounting, and destabilize retry/backoff behavior.

## Impact

- Incorrect failure categorization.
- Corrupted retry/backoff tracking.
- Possible runtime errors in timeout/cancellation-heavy batches.

## Evidence

- Result assignment in completion loop:
  - `ccbt/peer/async_peer_connection.py` lines 3255-3264.
- Later processing branch references `result` while iterating `conn_result`:
  - `ccbt/peer/async_peer_connection.py` lines 3383-3426.

## Reproduction (conceptual)

1. Run high-failure batch (timeouts/cancellations).
2. Inspect logs and failure counters for inconsistencies.
3. Observe mismatched error classification and retry behavior.

## Expected behavior

- Each iteration should classify and track the current `conn_result` only.

## Actual behavior

- Different variable can be consulted, creating incorrect accounting and behavior.

## Proposed fix

- Replace all references to out-of-scope `result` with `conn_result` in post-processing branch.
- Add unit tests for:
  - timeout path,
  - cancelled task path,
  - mixed success/failure batches.

## Acceptance criteria

- Failure stats and backoff reasons reflect actual per-peer outcomes.
- No variable-scope regressions under cancellation/timeout stress tests.
