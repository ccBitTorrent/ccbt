# TUI Manual QA Walk (big-bang release gate G8)

Run against a local daemon with fixtures: 3 torrents (1 downloading, 1 seeding, 1 paused), 1 shared XET folder, queue entries, one blacklisted IP, one checkpoint.

## Setup
Run from the repo root so `uv run` uses the project venv (textual >= 8.2.8);
running from `~` silently picks up system site-packages.
```powershell
cd <repo root>
uv sync
uv run btbt daemon start
uv run btbt dashboard --no-splash
```

## Crash / graph / diagnostics checks (2026-11-16)
- Preferences tab (step 7) must open without a traceback — regression net:
  `uv run pytest tests/unit/interface/test_compose_coverage.py` composes every
  screen/widget/tab at 80x24 and 120x40, including ConfigScreenWrapper in
  global and torrent modes.
- Network graph: switch to the Performance/Network graph; the upload/download
  strip is at most 9 rows, both sparklines (height 3) and the peak/avg line are
  fully visible with no scrollbar at 80x24 and 120x40.
- Peer diagnostics: run `uv run btbt diagnose` (add `--json` for machine
  output) and compare with the TUI Peer Diagnostics screen (`Ctrl+Shift+D`) —
  connected/active/productive/requestable peers, seeds, trackers, DHT routing
  table size, NAT. Both must agree; neither comes from a local session.
  `btbt status`/`btbt metrics` print an explicit local-session warning when no
  daemon is detected.

## Walk
1. Home: KPI strip shows torrent counts/rates; Torrents table shows correct Seeds (conn) vs Peers (conn), progress bar, ETA, ratio. No "Data provider not available" placeholders.
2. Select torrent with arrow keys: Per-Torrent tabs (Files/Peers/Trackers/Info/Graphs/Media/Config) show *that* torrent's data; switch torrent and confirm no cross-talk.
3. Keys from footer: `p` pause, `r` resume, `Del` remove (cancel), `i` quick-add (cancel), `o` advanced add (cancel), `g` global config, `t` torrent config — each opens/acts, `Esc` returns.
4. `Ctrl+M` menu: open Queue, Security/IP Filter, Checkpoints, Session/Daemon, CAS/Hub, XET Share — each renders a command table, `r` refreshes, `Esc` returns.
5. XET: `Ctrl+X` protocol (enable state, cache stats, cleanup confirms), `Ctrl+F` folders (add/remove/sync), `Ctrl+Shift+S` share screen lists tonic/share/link commands.
6. Graphs: switch all 10 graph tabs; each renders or shows a labelled empty state, never a frozen placeholder.
7. Preferences tab (Insight pane, 4th tab): General/Network/Bandwidth/Storage/Security/Advanced each load a config editor.
8. Resize terminal to 80x24: panes reflow, footer/status still visible, no clipped tables.
9. Theme (`Ctrl+Shift+T`) and Language (`l`): switch and return; table headers remain correct.
10. Quit with `q`; restart dashboard; state rehydrates from daemon snapshot within 2s.

Record: date, commit, textual version, pass/fail per step, screenshots at 120x40 and 80x24.
