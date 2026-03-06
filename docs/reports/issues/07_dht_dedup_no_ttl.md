# [P2] DHT dedup cache has no time-based TTL and may suppress useful rediscovery

## Summary

DHT dedup tracks "recently processed peers" in a set without time-based expiry. Cleanup only trims by size (`>1000`). In small/steady swarms, useful peers can remain suppressed for long periods, reducing reconnect opportunities.

## Impact

- Lower chance of reconnecting to intermittently available peers.
- Reduced resilience to churn in small swarms.

## Evidence

- DHT dedup check/mark path:
  - `ccbt/session/dht_setup.py` lines 754-776.
- Session set-based storage and size-only cleanup:
  - `ccbt/session/session.py` lines 3111-3138.

## Reproduction (conceptual)

1. Run in small swarm where same peers are rediscovered often.
2. Disconnect/reconnect churn several times.
3. Observe rediscovered peers skipped as "already processed" despite elapsed time.

## Expected behavior

- Dedup should expire by age (TTL), not only by set size.

## Actual behavior

- Entries can persist until set-size pressure triggers trimming.

## Proposed fix

- Replace plain set with `peer -> last_seen_timestamp` map.
- Apply bounded TTL (e.g., 5-15 minutes, configurable).
- Keep max-size trim as secondary safety.

## Acceptance criteria

- Rediscovered peers become eligible after TTL expiration.
- Dedup still prevents immediate duplicate storms.
- Memory remains bounded.
