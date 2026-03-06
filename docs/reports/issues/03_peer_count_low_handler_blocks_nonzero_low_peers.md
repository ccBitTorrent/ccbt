# [P1] `peer_count_low` handler suppresses DHT when peers are low but non-zero

## Summary

The low-peer event path applies the same 50-peer minimum and only fail-fasts when `active_peer_count == 0`. Sessions stuck at 1-2 non-productive peers can skip DHT repeatedly and remain stalled.

## Impact

- Common "1-2 peers connected but no progress" state is not recovered.
- Fail-fast logic misses non-zero deadlock states.

## Evidence

- Peer-count-low handler gate and fail-fast condition:
  - `ccbt/session/session.py` lines 1153-1208.

## Reproduction (conceptual)

1. Enter state with 1-2 active peers that do not deliver useful pieces.
2. Trigger `peer_count_low` events.
3. Observe DHT skip due to `<50` rule and no fail-fast trigger.

## Expected behavior

- Low-but-nonzero peer states should be treated as degraded and eligible for DHT escalation.

## Actual behavior

- DHT escalation may never occur unless peer count reaches exactly zero for timeout duration.

## Proposed fix

- Extend fail-fast trigger to include low-throughput/low-useful-peer states (not only zero peers).
- Use recent piece completion and request success rates as trigger signals.

## Acceptance criteria

- DHT escalation triggers for low, non-productive peer states.
- Session recovers by discovering additional peers without requiring zero peers.
