# Swarm Stability Milestone Gates

## Objective

This file operationalizes milestone gates for the 5-phase execution plan.

Each milestone gate must be executed before moving to the next project pair.
If any gate fails, pause progress, preserve current branch state, and apply rollback behavior before continuing.

## Milestone map (plan order)

1. **Milestone A** (after Project 6 + Project 1)
2. **Milestone B** (after Project 8 + Project 2)
3. **Milestone C** (after Project 3 + Project 4)
4. **Milestone D** (after Project 5 + Project 7)

## Gate A definition

Scope: cleanup/recovery stability at low-peer starts.

- Pass criteria:
  - `active_peer_floor_above_2` is at least `90%` across 15-second windows.
  - Cleanup removal bursts (`Removed X unhealthy connections` + `Cleaned up X stale connections`) do not increase versus baseline for the same 15-second window length.
  - `selector_spin_to_progress_ratio` improves compared to baseline by at least `10%` (or remains flat within noise if peer floor target is met).
- Fail criteria:
  - Floor drops below `90%` OR
  - Cleanup churn increases and persists across two consecutive checkpoints, OR
  - Selector spin remains non-improving while active floor is below target.
- Rollback behavior:
  - Stop all additional feature edits.
  - Preserve current commit state as a checkpoint.
  - Revert only the last merged milestone delta if the condition was introduced by a single commit; otherwise isolate by reverting the full milestone branch.
  - Re-run baseline evidence extraction and proceed only after gate pass.

## Gate B definition

Scope: seeder prioritization + choke/handshake productivity.

- Pass criteria:
  - `no_active_torrent_drop_rate` decreases by at least `20%` vs baseline window.
  - `unchoke_to_request_conversion` improves by at least `20%` on the seed-torrent workload.
- Fail criteria:
  - Either metric fails to improve by the required threshold.
  - Any sustained `registration-lag` disconnect burst (`No active torrent`) exceeds baseline by `10%` for three consecutive windows.
- Rollback behavior:
  - Disable the last applied high-risk behavior under the same code path:
    - unchoke-driven request priority for seeders
    - choke-only penalty tuning
  - Restore previous checkpoint and rerun milestone evidence with the same workload.

## Gate C definition

Scope: request productivity and piece reset control under constrained utility.

- Pass criteria:
  - `requeued_piece_loop_count` has no sustained bursts of repeated `Requeued 1 piece(s)` loops (or is reduced by `>30%`).
  - No-progress selector loops (`No available peers for piece` with no piece assignment progression) are reduced by at least `30%`.
- Fail criteria:
  - Both metrics remain flat or worsen after two checkpoints.
- Rollback behavior:
  - Remove temporary bounded pool / retry-deferral code from the last two project branches.
  - Restore checkpoint and keep only baseline behavior (minimal changes) until metric trend is corrected.

## Gate D definition

Scope: observability and regression hardening.

- Pass criteria:
  - New counters are present and sampled in evidence bundle:
    - `peer_choke_state_transitions`
    - `stalled_stale_piece_reset_total`
    - `unchoke_retries`
    - `bootstrap_zero_state_count`
    - `stale_cleanup_removed_total`
    - `registration_lag_handshake_failures`
  - Integration + unit regression sets for this plan pass.
  - Reconnect loop delta is `<=` baseline.
- Fail criteria:
  - Missing any required metric, or regression tests fail, or reconnect loops increase.
- Rollback behavior:
  - Keep the last green checkpoint.
  - Disable new metrics/test additions in the failing area and isolate to a smaller patch for rework.

## Evidence source for gating

- Use `docs/en/reports/swarm-stability-evidence-bundle-2026-03-19.md` as baseline package.
- Regenerate per milestone with the same extraction command and window strategy.
- Append each gate result to the corresponding changelog entry (below).

## Gate result template

```text
Gate: <A|B|C|D>
Timestamp:
Commit range: <prev_commit>..<current_commit>
Inputs: <latest.log, some.log>
Window: <start>-<end>
Pass metrics:
  - metric_1: baseline -> current, delta, pass/fail
  - metric_2: baseline -> current, delta, pass/fail
Fail metrics:
  - reasons
Decision: PASS | FAIL
Rollback status: None | Reverted to checkpoint <sha> | Pending
Next step:
```

## Suggested execution cadence

- Run gating immediately after each two-project merge and before next work starts.
- If `FAIL`, halt and wait for explicit direction before continuing.
