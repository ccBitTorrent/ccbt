# [P1] DHT fallback is disabled for non-magnet torrents unless explicitly requested

## Summary

Session startup enables DHT only for magnets or when `options.enable_dht` is explicitly set. Standard `.torrent` sessions can run without DHT fallback even when tracker peer quality is poor.

## Impact

- Reduced resilience in tracker-limited environments.
- Greater chance of "initial peers only" behavior on non-magnet torrents.

## Evidence

- Conditional DHT initialization logic:
  - `ccbt/session/session.py` lines 973-1022.

## Reproduction (conceptual)

1. Start non-magnet torrent with `config.discovery.enable_dht=true` but no explicit `--enable-dht`.
2. Observe DHT not initialized.
3. If tracker peers churn/fail, no DHT fallback path is available.

## Expected behavior

- DHT fallback should be available by default (or at least adaptive) for non-private torrents.

## Actual behavior

- DHT can be skipped entirely for non-magnet sessions unless explicitly requested.

## Proposed fix

- For non-private torrents, initialize DHT by default with conservative settings.
- Keep explicit disable option for operators that need strict tracker-only mode.

## Acceptance criteria

- Non-private `.torrent` sessions initialize DHT fallback by default.
- Private torrent behavior remains BEP 27-compliant (no DHT/PEX).
