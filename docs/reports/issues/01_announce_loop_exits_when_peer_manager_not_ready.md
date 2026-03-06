# [P0] Announce loop exits permanently when peer manager is not ready

## Summary

When tracker peers arrive before `peer_manager` is ready, `AnnounceLoop.run()` queues peers and executes `return`, which exits the entire announce loop task. After that, no periodic tracker announces run, so peer discovery can stall permanently.

## Impact

- High probability of long-running download stalls after initial peers.
- No fresh tracker peers after first readiness race.
- Particularly damaging for swarms where peers churn quickly.

## Evidence

- Early-exit path in announce loop: `return` after queueing peers.
  - `ccbt/session/announce.py` lines 663-747.
- Announce loop task is created once as a background task.
  - `ccbt/session/session.py` lines 1399-1407.

## Reproduction (conceptual)

1. Start a session where tracker responses can arrive immediately.
2. Delay peer manager readiness slightly (startup contention/race).
3. Trigger tracker peer response while `has_peer_manager` is false.
4. Observe queueing path taken and announce loop task no longer issuing periodic announces.

## Expected behavior

- If peer manager is temporarily unavailable, queue peers and continue loop (`continue`), not terminate loop.

## Actual behavior

- Loop exits permanently via `return`.

## Proposed fix

- Replace queue-path `return` with `continue` so the announce loop remains alive.
- Add guard logging/metrics for loop-lifecycle transitions.
- Add unit/integration test asserting announce loop continues after queue path.

## Acceptance criteria

- Announce loop remains active after peer queue fallback path.
- Subsequent announce intervals continue firing and producing tracker requests.
- Peer discovery resumes when peer manager becomes ready.
