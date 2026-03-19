# isProject:false Ownership / Milestone Signoff Checklist

This checklist applies to every milestone in the swarm-stability sequence.

## Standard release ownership block

- **Plan**: `torrent-download-stability-and-swarm-recovery`
- **Requester / owner**: _fill per milestone branch_
- **Implementation branch**: _fill per milestone_
- **Milestone scope**:
  - Phase 0: Evidence + defaults (required before feature edits)
  - Phase 1: Projects 6 + 1
  - Phase 2: Projects 8 + 2
  - Phase 3: Projects 3 + 4
  - Phase 4: Projects 5
  - Phase 5: Project 7
- **isProject flag**: `false` (manual ownership, non-automated flow)

## Pre-merge checklist

Before merging a milestone block, confirm:

1. **Scope alignment**
   - Only changes in the milestone target projects are included.
   - No unrelated behavior changes are merged.
2. **Config/default registration**
   - All newly introduced retry/backoff/selection parameters are present in
     `ccbt/session/swarm_stability_defaults.py`.
   - `DEFAULT_ROLLBACK` entries exist for each new parameter.
3. **Evidence continuity**
   - `docs/en/reports/swarm-stability-evidence-bundle-2026-03-19.md` updated with
     the new extraction window and baseline.
4. **Gate status**
   - Milestone gate section updated in
     `docs/en/reports/swarm-stability-milestone-gates.md`.
5. **Tests and safety**
   - Unit/integration tests relevant to changed behavior are either executed or
     explicitly deferred with justification.
6. **Roll-back readiness**
   - A rollback commit/shadow checkpoint is identified and validated.

## Milestone A signoff

- [ ] Gate A evidence run executed
- [ ] `active_peer_floor_above_2` target met
- [ ] Cleanup churn reduced or flat with no new regression in low-peer windows
- [ ] Plan updates: intent/risk/outcome written

## Milestone B signoff

- [ ] Gate B evidence run executed
- [ ] `No active torrent` drop improved by ≥20%
- [ ] Unchoke-to-request conversion improved by ≥20% on seed-torrent workload
- [ ] No unexpected churn in seed-anchored selection loop

## Milestone C signoff

- [ ] Gate C evidence run executed
- [ ] `Requeued 1 piece(s)` churn under control
- [ ] `No available peers for piece` loop pressure reduced
- [ ] `PIECE_SELECTOR` loop pressure reduced versus baseline

## Milestone D signoff

- [ ] Gate D evidence run executed
- [ ] Required counters present and observed
- [ ] Regression suite passes for newly introduced tests
- [ ] Reconnect-loop delta is not higher than baseline

## Post-merge commitment block

- [ ] `docs/en/reports/swarm-stability-evidence-bundle-2026-03-19.md` contains
  saved before/after metric deltas.
- [ ] `docs/en/reports/swarm-stability-milestone-gates.md` contains:
  - gate input window
  - pass/fail decision
  - rollback or continue action
- [ ] Signoff by owner and reviewer:
  - Owner:
  - Reviewer:
  - Date:

## Attaching checklist to milestone commits

For each milestone merge request/commit message, include:

- `Signoff attached:` link to the applicable section in this file.
- `Evidence run:` attached evidence window/output paths.
- `Gate outcome:` PASS or FAIL and mitigation if any.
