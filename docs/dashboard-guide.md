# Terminal Dashboard Guide

The Terminal Dashboard is ccBitTorrent's live monitoring interface, providing real-time views of torrents, peers, speeds, and system metrics in a beautiful terminal interface.

## Features

- **Real-time Updates**: Live torrent status and progress tracking
- **Peer Monitoring**: View connected peers, their speeds, and client information
- **Speed Visualization**: Download/upload speed graphs with sparklines
- **Alert System**: Real-time notifications for important events
- **Interactive Controls**: Keyboard shortcuts for common operations
- **Multi-torrent Support**: Monitor multiple downloads simultaneously

## Launching the Dashboard

```bash
# Start with default settings
uv run ccbt dashboard

# Custom refresh interval (seconds)
uv run ccbt dashboard --refresh 2.0

# Load alert rules on startup
uv run ccbt dashboard --rules /path/to/alert-rules.json
```

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ ccBitTorrent Dashboard                    [Q] Quit [H] Help     │
├─────────────────────────────────────────────────────────────────┤
│ Overview                                                         │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐    │
│ │ Download Speed  │ │ Upload Speed    │ │ Connected Peers │    │
│ │ 1.2 MB/s        │ │ 256 KB/s        │ │ 12              │    │
│ └─────────────────┘ └─────────────────┘ └─────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│ Torrents                                    [P] Pause [R] Resume │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Name                Progress  Speed    Peers  Status        │ │
│ │ ████████████████░░░ 85.2%     1.2MB/s  12    Downloading   │ │
│ │ ████████████████████ 100%     0KB/s    8     Seeding       │ │
│ └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ Peers (Selected Torrent)                                       │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ IP Address      Client      Speed      Choked  Progress     │ │
│ │ 192.168.1.100   qBittorrent 512KB/s   No     85.2%        │ │
│ │ 10.0.0.5        Transmission 256KB/s Yes    78.1%        │ │
│ └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ Speeds                                                          │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Download: ▁▃▅▇█▇▅▃▁▁▃▅▇█▇▅▃▁▁▃▅▇█▇▅▃▁▁▃▅▇█▇▅▃▁▁▃▅▇█▇▅▃▁ │ │
│ │ Upload:   ▁▁▃▅▇█▇▅▃▁▁▃▅▇█▇▅▃▁▁▃▅▇█▇▅▃▁▁▃▅▇█▇▅▃▁▁▃▅▇█▇▅▃▁ │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Keyboard Shortcuts

### Navigation
- `↑/↓` - Navigate torrent list
- `Enter` - View torrent details
- `Tab` - Switch between panels
- `Esc` - Return to main view

### Torrent Control
- `P` - Pause selected torrent
- `R` - Resume selected torrent
- `D` - Delete selected torrent (with confirmation)
- `Space` - Toggle pause/resume

### Dashboard Control
- `Q` - Quit dashboard
- `H` - Show help
- `C` - Clear completed torrents
- `F` - Filter torrents by name/status
- `S` - Sort torrents by different criteria

### Refresh and Updates
- `U` - Force refresh all data
- `+/-` - Increase/decrease refresh rate
- `R` - Reset refresh rate to default

## Panels Overview

### Overview Panel
Displays global statistics:
- **Download Speed**: Current global download rate
- **Upload Speed**: Current global upload rate
- **Connected Peers**: Total number of connected peers
- **Active Torrents**: Number of downloading/seeding torrents
- **System Resources**: CPU and memory usage (if available)

### Torrents Panel
Shows all active torrents with:
- **Name**: Torrent name (truncated if too long)
- **Progress**: Visual progress bar and percentage
- **Speed**: Current download/upload speed
- **Peers**: Number of connected peers
- **Status**: Downloading, Seeding, Paused, etc.
- **ETA**: Estimated time to completion

### Peers Panel
Displays peers for the selected torrent:
- **IP Address**: Peer's IP address
- **Client**: BitTorrent client name
- **Speed**: Data transfer rate
- **Choked**: Whether peer is choked
- **Progress**: Peer's download progress
- **Connection Time**: How long connected

### Speeds Panel
Real-time speed visualization:
- **Download Graph**: Sparkline showing download speed over time
- **Upload Graph**: Sparkline showing upload speed over time
- **Scale**: Automatic scaling based on current speeds

### Alerts Panel
Shows system alerts and notifications:
- **Severity**: Info, Warning, Error, Critical
- **Message**: Alert description
- **Timestamp**: When the alert occurred
- **Actions**: Acknowledge or dismiss alerts

## Configuration

### Dashboard Settings

You can configure the dashboard behavior in your `ccbt.toml`:

```toml
[dashboard]
refresh_interval = 1.0  # seconds
show_peer_details = true
show_speed_graphs = true
max_torrents_display = 50
auto_refresh = true
```

### Alert Rules

Configure alerts for important events:

```toml
[alerts]
rules = [
    { name = "high_cpu", metric = "cpu_usage", condition = "value > 80", severity = "warning" },
    { name = "low_speed", metric = "download_speed", condition = "value < 100", severity = "info" },
    { name = "no_peers", metric = "connected_peers", condition = "value == 0", severity = "error" }
]
```

## Advanced Usage

### Custom Refresh Rates

```bash
# Very fast updates (0.5 seconds)
uv run ccbt dashboard --refresh 0.5

# Slower updates (5 seconds)
uv run ccbt dashboard --refresh 5.0
```

### Loading Alert Rules

```bash
# Load custom alert rules
uv run ccbt dashboard --rules /path/to/custom-rules.json
```

### Integration with Monitoring

The dashboard integrates with ccBitTorrent's monitoring system:

```bash
# Start dashboard with full monitoring
uv run ccbt dashboard --enable-metrics --enable-alerts
```

## Troubleshooting

### Dashboard Won't Start

1. Check if Textual is installed: `uv pip install textual`
2. Verify terminal supports Unicode and colors
3. Check for conflicting terminal settings

### Performance Issues

1. Increase refresh interval: `--refresh 2.0`
2. Reduce number of displayed torrents
3. Disable speed graphs if not needed

### Missing Data

1. Ensure torrents are actively downloading
2. Check network connectivity
3. Verify peer connections are established

## Tips and Best Practices

1. **Use appropriate refresh rates**: Faster isn't always better
2. **Monitor key metrics**: Focus on speeds and peer counts
3. **Set up alerts**: Configure alerts for important events
4. **Keyboard shortcuts**: Learn the shortcuts for efficiency
5. **Filter torrents**: Use filtering to focus on specific downloads

## Integration with CLI

The dashboard works seamlessly with CLI commands:

```bash
# Start download and immediately open dashboard
uv run ccbt download movie.torrent --interactive

# Monitor specific torrent
uv run ccbt dashboard --torrent <info_hash>
```

For more advanced usage, see the [CLI Reference](cli-reference.md) and [Monitoring](monitoring.md) documentation.
