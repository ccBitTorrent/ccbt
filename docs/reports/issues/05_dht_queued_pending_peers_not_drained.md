# [P1] DHT queued/pending peer buffers appear undrained

## Summary

On DHT connection readiness/failure paths, peers are stored via `add_queued_dht_peers()` and `add_pending_dht_peer()`. No drain/consumer path is evident for these buffers, so retries may never occur.

## Impact

- Peer candidates are collected but not retried.
- Discovery can appear active in logs while effective connection attempts stall.

## Evidence

- Queue/pending writes in DHT setup:
  - `ccbt/session/dht_setup.py` lines 275-334.
- Data structures and accessors exist in session:
  - `ccbt/session/session.py` lines 3014-3056.
- No additional consumer references found outside these locations.

## Reproduction (conceptual)

1. Trigger DHT callback while session not ready or connection call throws.
2. Observe peers added to queued/pending lists.
3. Observe no later drain/retry from those lists.

## Expected behavior

- Buffered DHT peers should be reattempted when peer manager/session becomes ready.

## Actual behavior

- Buffered peers may remain inert indefinitely.

## Proposed fix

- Add a scheduled drain routine:
  - run on readiness transitions,
  - run periodically with bounded batch size,
  - de-duplicate with expiry.
- Integrate with existing `PeerConnectionHelper`/pending queue machinery.

## Acceptance criteria

- Queued/pending DHT peers are retried automatically.
- Buffers shrink over time under healthy operation.
- Retries stop after policy limits with clear metrics.
