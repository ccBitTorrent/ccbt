# ccBitTorrent - High-Performance BitTorrent Client

[![codecov](https://codecov.io/gh/ccBittorrent/ccbt/branch/main/graph/badge.svg)](https://codecov.io/gh/ccBittorrent/ccbt)
[![🥷 Bandit](https://img.shields.io/badge/🥷-security-yellow.svg)](https://ccbittorrent.readthedocs.io/en/reports/bandit/)
[![🐍 Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](../pyproject.toml)
[![📜License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](https://ccbittorrent.readthedocs.io/en/license/)
[![🤝Contributing](https://img.shields.io/badge/🤝-open-brightgreen?logo=pre-commit&logoColor=white)](https://ccbittorrent.readthedocs.io/en/contributing/)
[![🎁UV](https://img.shields.io/badge/🎁-uv-orange.svg)](https://ccbittorrent.readthedocs.io/en/getting-started/)
[![🤗 XET](https://img.shields.io/badge/🤗-xet-yellow.svg)](https://ccbittorrent.readthedocs.io/en/bep_xet/)
[![🌐 IPFS](https://img.shields.io/badge/🌐-IPFS-blue.svg)](https://ccbittorrent.readthedocs.io/en/API/#ipfsprotocol)
[![🌱 BitTorrent v2](https://img.shields.io/badge/🌱-BitTorrent-green.svg)](https://ccbittorrent.readthedocs.io/en/bep52/)
[![🔐SSL](https://img.shields.io/badge/🔐-SSL%2FTLS-blue.svg)](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/ssl_context.py)
[![🔢Encryption](https://img.shields.io/badge/🔢-Encryption-green.svg)](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/encryption.py)

**🌍 Documentation Languages:**
[![🇬🇧 English](https://img.shields.io/badge/🇬🇧-English-blue.svg)](https://ccbittorrent.readthedocs.io/en/)
[![🇪🇸 Español](https://img.shields.io/badge/🇪🇸-Español-red.svg)](https://ccbittorrent.readthedocs.io/es/)
[![🇫🇷 Français](https://img.shields.io/badge/🇫🇷-Français-blue.svg)](https://ccbittorrent.readthedocs.io/fr/)
[![🇯🇵 日本語](https://img.shields.io/badge/🇯🇵-日本語-red.svg)](https://ccbittorrent.readthedocs.io/ja/)
[![🇰🇷 한국어](https://img.shields.io/badge/🇰🇷-한국어-blue.svg)](https://ccbittorrent.readthedocs.io/ko/)
[![🇮🇳 हिन्दी](https://img.shields.io/badge/🇮🇳-हिन्दी-orange.svg)](https://ccbittorrent.readthedocs.io/hi/)
[![🇵🇰 اردو](https://img.shields.io/badge/🇵🇰-اردو-green.svg)](https://ccbittorrent.readthedocs.io/ur/)
[![🇮🇷 فارسی](https://img.shields.io/badge/🇮🇷-فارسی-green.svg)](https://ccbittorrent.readthedocs.io/fa/)
[![🇹🇭 ไทย](https://img.shields.io/badge/🇹🇭-ไทย-red.svg)](https://ccbittorrent.readthedocs.io/th/)
[![🇨🇳 中文](https://img.shields.io/badge/🇨🇳-中文-red.svg)](https://ccbittorrent.readthedocs.io/zh/)
[![🇸🇾 ܐܪܡܝܐ](https://img.shields.io/badge/🇸🇾-ܐܪܡܝܐ-red.svg)](https://ccbittorrent.readthedocs.io/arc/)
[![🇪🇸 Euskara](https://img.shields.io/badge/🇪🇸-Euskara-red.svg)](https://ccbittorrent.readthedocs.io/eu/)
[![🇳🇬 Hausa](https://img.shields.io/badge/🇳🇬-Hausa-green.svg)](https://ccbittorrent.readthedocs.io/ha/)
[![🇹🇿 Kiswahili](https://img.shields.io/badge/🇹🇿-Kiswahili-blue.svg)](https://ccbittorrent.readthedocs.io/sw/)
[![🇳🇬 Yorùbá](https://img.shields.io/badge/🇳🇬-Yorùbá-green.svg)](https://ccbittorrent.readthedocs.io/yo/)

A modern, high-performance BitTorrent client built with Python asyncio, featuring advanced piece selection algorithms, parallel metadata exchange, and optimized disk I/O.

## 📚 Documentation

**👉 [View Full Documentation](https://ccbittorrent.readthedocs.io/en/)**

The complete documentation is available at [https://ccbittorrent.readthedocs.io/en/](https://ccbittorrent.readthedocs.io/en/), including:

- [Getting Started Guide](https://ccbittorrent.readthedocs.io/en/getting-started/) - Step-by-step tutorial
- [Configuration Guide](https://ccbittorrent.readthedocs.io/en/configuration/) - Configuration options
- [Performance Tuning](https://ccbittorrent.readthedocs.io/en/performance/) - Optimization guide
- [API Documentation](https://ccbittorrent.readthedocs.io/en/API/) - Python API usage
- [Architecture](https://ccbittorrent.readthedocs.io/en/architecture/) - Technical details
- [Contributing Guide](https://ccbittorrent.readthedocs.io/en/contributing/) - Development setup
- [BEP XET](https://ccbittorrent.readthedocs.io/en/bep_xet/) - XET protocol extension
- [BEP 52](https://ccbittorrent.readthedocs.io/en/bep52/) - BitTorrent v2 support

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

For detailed installation instructions, usage examples, configuration, and more, visit the [documentation site](https://ccbittorrent.readthedocs.io/en/).

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

For detailed development setup and guidelines, see the [Contributing Guide](https://ccbittorrent.readthedocs.io/en/contributing/).

## License

This project is licensed under the **GNU General Public License v2 (GPL-2.0)** - see the [License Documentation](https://ccbittorrent.readthedocs.io/en/license/) for the complete license text.

Additionally, this project is subject to additional use restrictions under the **ccBT RAIL-AMS License** - see the [ccBT RAIL Documentation](https://ccbittorrent.readthedocs.io/en/ccBT-RAIL/) for the complete terms and use restrictions.

**Important**: Both licenses apply to this software. You must comply with all terms and restrictions in both the GPL-2.0 license and the RAIL license.
