# ccBitTorrent Documentation

## Overview

ccBitTorrent is a high-performance, feature-rich BitTorrent client written in Python. It implements modern BitTorrent protocols and provides advanced features for optimal download performance.

## Documentation Index
- Configuration Guide: [configuration.md](configuration.md)
- CLI Reference: [cli-reference.md](cli-reference.md)
- Monitoring & Observability: [monitoring.md](monitoring.md)
- Checkpoints Guide: [checkpoints.md](checkpoints.md)
- Examples: [examples/](examples/)

## Features

### Core BitTorrent Features
- **BitTorrent Protocol**: Full BEP 5 implementation
- **Fast Extension**: BEP 6 support for improved performance
- **Extension Protocol**: BEP 10 for custom extensions
- **WebSeed**: BEP 19 HTTP seeding support
- **Compact Peer Lists**: BEP 23 for efficient peer exchange
- **DHT**: Distributed Hash Table for peer discovery
- **PEX**: Peer Exchange for efficient peer discovery
- **MSE/PE**: Message Stream Encryption and Protocol Encryption

### Modern Protocol Support
- **WebTorrent**: WebRTC-based peer connections
- **IPFS**: InterPlanetary File System integration
- **Protocol Abstraction**: Multi-protocol support

### Performance Optimizations
- **Zero-Copy Operations**: Ring buffers and memory pools
- **Network I/O**: Socket tuning and connection pooling
- **Disk I/O**: io_uring, AIO, and NVMe optimizations
- **Hash Verification**: SIMD-accelerated SHA-1
- **Piece Selection**: Rarest-first and endgame algorithms

### Security Features
- **Peer Validation**: Reputation system and validation
- **Rate Limiting**: Adaptive rate limiting with ML
- **Anomaly Detection**: Statistical and behavioral analysis
- **Encryption**: MSE/PE protocol encryption
- **IP Management**: Blacklist/whitelist management

### Machine Learning Integration
- **Peer Selection**: ML-based peer quality prediction
- **Piece Prediction**: Predictive piece selection
- **Anomaly Detection**: ML-based anomaly detection
- **Adaptive Limiting**: ML-based rate adjustment

### Monitoring & Observability
- **Metrics Collection**: Custom metrics with aggregation
- **Alerting**: Rule-based alert system
- **Tracing**: Distributed tracing with OpenTelemetry
- **Dashboards**: Real-time monitoring dashboards
- **Profiling**: Performance profiling and bottleneck detection

## Installation

### Prerequisites
- Python 3.8+
- pip or conda

### Install from Source
```bash
git clone https://github.com/your-org/ccbt.git
cd ccbt
pip install -e .
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

## Quick Start

### Basic Usage
```bash
# Download a torrent file
python -m ccbt download example.torrent

# Download from magnet link
python -m ccbt magnet "magnet:?xt=urn:btih:..."

# Start interactive mode
python -m ccbt interactive

# Start terminal dashboard
python -m ccbt dashboard
```

### Configuration
```bash
# Show current configuration (JSON)
python -m ccbt config show --format json

# Get a value
python -m ccbt config get network.listen_port

# Set a value (persist locally)
python -m ccbt config set network.listen_port 6881 --local

# Reset a key to defaults
python -m ccbt config reset network.listen_port
```

## Configuration

### Configuration File
The configuration file is located at `~/.ccbt/config.toml` by default.

### Key Settings
```toml
[network]
listen_port = 6881
max_global_peers = 200
max_peers_per_torrent = 50

[disk]
download_path = "~/Downloads"
preallocate = "full"
use_mmap = true

[observability]
log_level = "INFO"
enable_metrics = true
metrics_port = 9090
```

### Environment Variables
```bash
export CCBT_NETWORK_LISTEN_PORT=6881
export CCBT_DISK_DOWNLOAD_PATH=~/Downloads
export CCBT_OBSERVABILITY_LOG_LEVEL=DEBUG
```

## Architecture

### Core Components
- **Session**: Main client session management
- **Torrent**: Torrent file and metadata handling
- **Peer**: Peer connection management
- **Piece Manager**: Piece selection and verification
- **Tracker**: Tracker communication
- **DHT**: Distributed hash table
- **Disk I/O**: File system operations

### Service Architecture
- **Peer Service**: Peer connection management
- **Tracker Service**: Tracker communication
- **Storage Service**: File system operations
- **Security Service**: Security and validation
- **ML Service**: Machine learning features
- **Monitoring Service**: Metrics and observability

### Plugin System
- **Plugin Base**: Core plugin interface
- **Plugin Manager**: Plugin lifecycle management
- **Event Hooks**: Plugin event system
- **Example Plugins**: Logging, metrics, custom extensions

## API Reference

### Core Classes
- `Session`: Main client session
- `Torrent`: Torrent file handling
- `Peer`: Peer connection
- `PieceManager`: Piece management
- `Tracker`: Tracker communication
- `DHT`: Distributed hash table

### Services
- `PeerService`: Peer management
- `TrackerService`: Tracker communication
- `StorageService`: File operations
- `SecurityService`: Security features
- `MLService`: Machine learning
- `MonitoringService`: Metrics and alerts

### Events
- `Event`: Base event class
- `EventBus`: Event system
- `EventType`: Event types
- `EventEmitter`: Event emission

## Performance Tuning

### Network Optimization
- Socket buffer tuning
- Connection pooling
- TCP_NODELAY optimization
- Bandwidth-delay product tuning

### Disk I/O Optimization
- io_uring support (Linux)
- AIO fallback
- NVMe optimizations
- Write-behind caching

### Memory Optimization
- Ring buffers
- Memory pools
- Zero-copy operations
- Garbage collection tuning

## Security

### Peer Validation
- Reputation system
- Behavior analysis
- Protocol compliance
- Connection quality assessment

### Rate Limiting
- Per-peer limiting
- Global limiting
- Adaptive rates
- DDoS protection

### Encryption
- MSE/PE support
- Key exchange
- Session management
- Cipher suites

## Monitoring

### Metrics
- System metrics
- Performance metrics
- Network metrics
- Security metrics

### Alerting
- Rule-based alerts
- Notification channels
- Alert escalation
- Suppression rules

### Dashboards
- Real-time monitoring
- Grafana integration
- Custom dashboards
- Widget system

## Troubleshooting

### Common Issues
1. **Connection Issues**: Check firewall settings
2. **Slow Downloads**: Verify network configuration
3. **Disk Errors**: Check filesystem permissions
4. **Memory Issues**: Adjust buffer sizes

### Debug Mode
```bash
# Enable debug mode
ccbt --debug download example.torrent

# Enable verbose logging
ccbt --verbose download example.torrent

# Start debug shell
ccbt debug
```

### Logs
- Log files: `~/.ccbt/logs/`
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Log rotation: Automatic with size limits

## Development

### Building from Source
```bash
git clone https://github.com/your-org/ccbt.git
cd ccbt
pip install -e .
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/performance/

# Run with coverage
pytest --cov=ccbt
```

### Code Quality
```bash
# Format code
black ccbt/
isort ccbt/

# Type checking
mypy ccbt/

# Linting
ruff ccbt/
```

## Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make changes
4. Add tests
5. Submit pull request

### Code Standards
- Follow PEP 8
- Use type hints
- Write docstrings
- Add tests
- Update documentation

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/your-org/ccbt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/ccbt/discussions)
- **Discord**: [Discord Server](https://discord.gg/ccbt)

## Changelog

### Version 2.0.0
- Complete rewrite with modern architecture
- Added ML-based optimizations
- Enhanced security features
- Improved performance
- Added monitoring and observability

### Version 1.0.0
- Initial release
- Basic BitTorrent functionality
- Core protocol implementation
