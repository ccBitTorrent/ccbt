# ccBitTorrent Dashboard Roadmap

This roadmap outlines the Textual-based terminal dashboard and future enhancements.

## Phase A: Foundations (Done / In Progress)
- Terminal dashboard app with Textual (Overview + Torrents table)
- 1s refresh loop using set_interval()
- Global stats via `AsyncSessionManager.get_global_stats()`
- Per-torrent status via `AsyncSessionManager.get_status()`
- CLI entry `ccbt dashboard` to launch

References: Textual documentation [Textual docs](https://textual.textualize.io/)

## Phase B: Core UX Enhancements
- Key bindings
  - q: quit
  - p: pause selected torrent
  - r: resume selected torrent
  - del: remove selected torrent (confirm)
- Selection model for torrents table (remember current selection across refresh)
- Command palette (Textual) for common actions and filtering by name / status
- Status bar counters (active / seeding / paused) and network rates

## Phase C: Panels & Widgets
- Peers panel: live list for selected torrent (IP, choked, d/u rates, client)
- Speeds panel: download/upload sparklines (Textual Sparkline/Log)
- Alerts panel: recent alerts with severity colors and ack action
- Logs panel: rolling recent events (RichLog)
- Details panel: torrent metadata (size, created by, comment, trackers)

## Phase D: Actions & Operations
- Per-torrent rate limits (integrate `set_rate_limits`) with live update
- Recheck data / rehash command
- Force announce, scrape, PEX refresh actions
- Checkpoint operations from dashboard: backup/restore/migrate

## Phase E: Observability
- Toggle metrics collection interval; show effective interval
- Export current dashboard snapshot as JSON for diagnostics
- Optional: stream metrics to websocket for external dashboards

## Phase F: Theming & Accessibility
- Light/dark themes; theme toggle via key binding
- Font-size adjustments; colorblind-friendly palette
- Compact mode (more rows per screen)

## Phase G: Testing & Docs
- Dashboard unit tests (widget composition, refresh, key bindings)
- Integration tests (launch app, simulate key actions)
- User guide: dashboard navigation, actions, troubleshooting

## Stretch: Browser UI
- Evaluate Textual’s web mode for remote access
- Security consideration: auth for remote dashboard

## Implementation Notes
- Use Textual’s DataTable for torrents with selection + sorting
- Use reactive() / watch methods for state-driven UI updates
- Avoid long blocking ops in UI; run background tasks with set_interval/workers

## External Inspirations
- Textual reference apps and widgets [Textual docs](https://textual.textualize.io/)
- Consider ideas from tewi’s terminal UIs for layout/interaction patterns https://github.com/anlar/tewi

- [ ] Multi-select actions (pause/resume/remove)
- [ ] Command palette with auto-complete and history
- [ ] Alerts panel: acknowledge, silence rules, jump to source
- [ ] Peers panel: sort by rate, filter by client
- [ ] Speed charts: window selection, export CSV
- [ ] Plugin widgets: register custom panels from plugins
