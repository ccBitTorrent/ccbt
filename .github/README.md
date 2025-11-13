# ccBitTorrent - High-Performance BitTorrent Client

[![codecov](https://codecov.io/gh/ccBittorrent/ccbt/branch/main/graph/badge.svg)](https://codecov.io/gh/ccBittorrent/ccbt)
[![🥷 Bandit](https://img.shields.io/badge/🥷-security-yellow.svg)](https://ccbittorrent.readthedocs.io/reports/bandit/)
[![🐍 Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](../pyproject.toml)
[![📜License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](https://ccbittorrent.readthedocs.io/license/)
[![🤝Contributing](https://img.shields.io/badge/🤝-open-brightgreen?logo=pre-commit&logoColor=white)](https://ccbittorrent.readthedocs.io/contributing/)
[![🎁UV](https://img.shields.io/badge/🎁-uv-orange.svg)](https://ccbittorrent.readthedocs.io/getting-started/)
[![🤗 XET](https://img.shields.io/badge/🤗-xet-yellow.svg)](https://ccbittorrent.readthedocs.io/bep_xet/)
[![🌐 IPFS](https://img.shields.io/badge/🌐-IPFS-blue.svg)](https://ccbittorrent.readthedocs.io/API/#ipfsprotocol)
[![🌱 BitTorrent v2](https://img.shields.io/badge/%20BitTorrent🌱-v2-green.svg)](https://ccbittorrent.readthedocs.io/bep52/)
[![🔐SSL](https://img.shields.io/badge/🔐-SSL%2FTLS-blue.svg)](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/ssl_context.py)
[![🔢Encryption](https://img.shields.io/badge/Encryption🔢-enabled-green.svg)](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/encryption.py)

A modern, high-performance BitTorrent client built with Python asyncio, featuring advanced piece selection algorithms, parallel metadata exchange, and optimized disk I/O.

## 📚 Documentation

**👉 [View Full Documentation](https://ccbittorrent.readthedocs.io/)**

The complete documentation is available at [https://ccbittorrent.readthedocs.io/](https://ccbittorrent.readthedocs.io/), including:

- [Getting Started Guide](https://ccbittorrent.readthedocs.io/getting-started/) - Step-by-step tutorial
- [Configuration Guide](https://ccbittorrent.readthedocs.io/configuration/) - Configuration options
- [Performance Tuning](https://ccbittorrent.readthedocs.io/performance/) - Optimization guide
- [API Documentation](https://ccbittorrent.readthedocs.io/API/) - Python API usage
- [Architecture](https://ccbittorrent.readthedocs.io/architecture/) - Technical details
- [Contributing Guide](https://ccbittorrent.readthedocs.io/contributing/) - Development setup
- [BEP XET](https://ccbittorrent.readthedocs.io/bep_xet/) - XET protocol extension
- [BEP 52](https://ccbittorrent.readthedocs.io/bep52/) - BitTorrent v2 support

## Quick Start

### Installation with UV

```bash
# Install UV (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install ccBitTorrent
uv pip install ccbittorrent
```

### Your First Download

```bash
# Download from torrent file
uv run ccbt download movie.torrent

# Download from magnet link
uv run ccbt magnet "magnet:?xt=urn:btih:..."

# Launch Terminal Dashboard (Recommended)
uv run ccbt dashboard
```

For detailed installation instructions, usage examples, configuration, and more, visit the [documentation site](https://ccbittorrent.readthedocs.io/).

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

For detailed development setup and guidelines, see the [Contributing Guide](https://ccbittorrent.readthedocs.io/contributing/).

## License

This project is licensed under the **GNU General Public License v2 (GPL-2.0)** - see the [License Documentation](https://ccbittorrent.readthedocs.io/license/) for the complete license text.

Additionally, this project is subject to additional use restrictions under the **ccBT RAIL-AMS License** - see the [ccBT RAIL Documentation](https://ccbittorrent.readthedocs.io/ccBT-RAIL/) for the complete terms and use restrictions.

**Important**: Both licenses apply to this software. You must comply with all terms and restrictions in both the GPL-2.0 license and the RAIL license.

