# [P0] DHT discovery hard-gated until 50 active peers

## Summary

DHT discovery loop enforces `min_peers_before_dht = 50`. Sessions with fewer than 50 active peers repeatedly sleep and skip DHT queries, which can block fallback discovery indefinitely.

## Impact

- DHT fallback often never starts in real-world swarms.
- Downloads can stagnate with low-quality initial peers.
- Magnifies stalls when tracker coverage is weak.

## Evidence

- Hard gate and repeated sleep/continue logic:
  - `ccbt/session/dht_setup.py` lines 1273-1379.

## Reproduction (conceptual)

1. Start torrent with DHT enabled and active peers below 50.
2. Let session run with tracker churn and low successful connections.
3. Observe repeated "waiting for minimum peers" behavior and no DHT queries.

## Expected behavior

- DHT should be available as fallback at low peer counts (especially when throughput/active peers are poor).

## Actual behavior

- DHT start is deferred until 50 peers, causing prolonged or permanent non-discovery.

## Proposed fix

- Replace fixed threshold with adaptive policy based on:
  - active peer count,
  - download rate,
  - time since last successful piece,
  - tracker health.
- Provide config defaults that permit DHT at low peer counts with conservative query rate.

## Acceptance criteria

- DHT queries begin in low-peer conditions without requiring 50 active peers.
- Query rate remains conservative enough to avoid blacklisting.
- Stall-recovery tests show additional peers discovered under low-peer scenarios.
