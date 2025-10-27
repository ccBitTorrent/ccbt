# Monitoring and Dashboard

This document explains the terminal dashboard and monitoring features in ccBitTorrent.

## Terminal Dashboard (Textual)

- Launch: `ccbt dashboard`
- Live refresh: every 0.5–2.0s (toggle with R)
- Panels:
  - Overview: counts (torrents/active/paused/seeding), global rates
  - Speeds: download/upload sparklines (rolling history)
  - Torrents: selectable list with progress and rates
  - Peers: live peers for selected torrent (when available)
  - Details: metadata and rates for selected torrent
  - Alerts: active alerts
  - Logs: recent actions

### Key bindings
- q: Quit
- p/r: Pause/Resume selected torrent
- delete: Remove selected (y/n confirm)
- a/s/e/h: Announce/Scrape/PEX/Rehash
- 1/2: Rate limits (0/0, 1024/1024 KiB/s)
- /: Filter by name/status; Enter to apply
- :: Command palette (pause/resume/remove/announce/scrape/pex/rehash/limit/backup/restore)
- x: Export snapshot JSON
- R: Cycle UI refresh interval (0.5, 1.0, 2.0s)
- M: Cycle metrics interval (1, 5, 10s)
- t: Toggle theme (light/dark)
- c: Compact mode

### Requirements
- Textual TUI framework. See Textual documentation for usage and widgets.

Reference: [Textual docs](https://textual.textualize.io/)

## Metrics

- MetricsCollector collects system/performance metrics at a configurable interval (M toggles 1/5/10s).
- Future: export metrics to external sinks and integrate alert rules.

## Alerts

- Alerts panel displays active alerts. Acknowledge all with key K.
- Future: configure alert rules and notification channels.

## Tracing and Profiling

- Tracing and profiling stubs exist in monitoring/observability modules for future integration.
