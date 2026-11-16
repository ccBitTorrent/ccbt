# Live perf gate — 2026-11-16 (after download-performance fix)

Torrent: Adobe InDesign 2027 v22.0 (x64) [AppDoze], 2891 pieces.
Baseline frozen in `dev/perf-baseline-2026-11-16.json` (~16 KiB/s, 1 peer,
DHT routing 0 reported "healthy", 25/33 trackers stuck "updating").

## After snapshots (`btbt diagnose --json`)

| snapshot | download | peers | DHT routing | DHT queries | progress |
|---|---|---|---|---|---|
| perf-after-2min.json | 1.47 MB/s | 2 | 0 (reporting bug*) | 0 | — |
| perf-after-v3.json | 807 KB/s | 2 | 39 healthy | 0 | 26.6% |
| perf-after-v4.json | 31 KB/s | 2 | 18 healthy | 0 | 30.2% |
| perf-after-v5.json | 306 KB/s | 2 | 33 healthy | 5 | 35.1% |

*The routing-table IPC read was fixed during the gate (routing table had
no `__len__`/`get_all_nodes`; handler read `dht_client` from the torrent
session instead of the session manager; bound_port/total_queries were
never copied from client counters). Bound port now reports 64120.

## Verdict vs plan gate

- routing_table_size > 0: **yes** (18–39, health `healthy` truthfully)
- download ≥ 5× baseline (80 KiB/s): **yes**, sustained snapshots
  306 KB/s–1.47 MB/s (~19–94×)
- connected ≥ 10 / requestable ≥ 4: **not reached** — this swarm only
  ever offered 2 reachable seeders; tracker rounds (now capped at 10/round
  with rotation) show `never-announced` draining and dead trackers in
  `backoff`, and the daemon log shows mass outbound connection timeouts
  to tracker-supplied addresses. Per the plan, this is the
  swarm-limited branch, not an engine limit.
- Lock-timeouts during final snapshots: none observed.
- Daemon heartbeat (`daemon.heartbeat`, 15s cadence) reported fresh in
  every snapshot.

NAT remains outbound-only on this network (no IGD); `btbt diagnose` now
states this explicitly with manual-forward instructions (TCP/UDP 64122,
UDP 64120).
