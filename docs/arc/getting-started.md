# ܫܘܪܝܐ

ܒܫܝܢܐ ܠܟܘܢ ܒܟܘܢܝܐ ܕܟܘܢܝܐ ܕܟܘܢܝܐ! ܗܢܐ ܡܕܒܪܢܘܬܐ ܢܥܕܪܟܘܢ ܕܬܫܪܘܢ ܘܬܪܕܘܢ ܒܥܓܠ ܥܡ ܟܠܝܢܛ ܒܝܛܛܘܪܢܛ ܕܬܘܩܦܐ ܪܡܐ ܕܝܠܢ.

!!! tip "ܡܢܝܘܬܐ ܪܫܝܬܐ: ܬܘܣܦܬܐ ܕܦܪܘܛܘܟܘܠ BEP XET"
    ccBitTorrent ܡܫܡܠܐ ܠܬܘܣܦܬܐ ܕܦܪܘܛܘܟܘܠ Xet (BEP XET) ܕܡܦܠܚ ܠܚܘܠܩܐ ܕܡܬܚܪܪ ܡܢ ܡܘܢܝܐ ܘܠܡܦܪܫܘܬܐ ܕܚܘܠܩܐ ܒܝܢ ܛܘܪܢܛܝܢ. ܗܕܐ ܡܗܦܟ ܠܒܝܛܛܘܪܢܛ ܠܡܕܝܢܬ ܦܝܠܝܢ ܕܦܝܪ-ܠ-ܦܝܪ ܕܡܬܚܕܪܐ ܘܡܬܚܕܪ ܕܡܬܬܟܝܢ ܠܫܘܬܦܘܬܐ. [ܝܠܦ ܝܬܝܪ ܥܠ BEP XET →](bep_xet.md)

## ܐܪܡܝܢܘܬܐ

### ܡܘܕܥܢܘܬܐ

- Python 3.8 ܐܘ ܝܬܝܪ
- ܡܕܒܪ ܦܩܥܬܐ [UV](https://astral.sh/uv) (ܡܘܨܦ)

### ܐܪܡܝ ܠܐܘܝܘܝ

ܐܪܡܝ ܠܐܘܝܘܝ ܡܢ ܣܟܪܝܦܬܐ ܕܐܪܡܝܢܘܬܐ ܪܫܡܝܬܐ:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### ܐܪܡܝ ܠܟܘܢܝܐ ܕܟܘܢܝܐ

ܐܪܡܝ ܡܢ PyPI:
```bash
uv pip install ccbittorrent
```

ܐܘ ܐܪܡܝ ܡܢ ܡܒܘܥܐ:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

ܢܩܒܬܐ ܕܥܠܝܬܐ ܡܬܚܪܪܐ ܒ [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81).

## ܢܩܒܬܐ ܕܥܠܝܬܐ ܪܫܝܬܐ

ccBitTorrent ܡܦܠܚ ܠܬܠܬ ܢܩܒܬܐ ܕܥܠܝܬܐ ܪܫܝܬܐ:

### 1. Bitonic (ܡܘܨܦ)

**Bitonic** ܗܘ ܦܐܬܐ ܕܕܐܫܒܘܪܕ ܕܛܪܡܝܢܠ ܪܫܝܬܐ. ܡܦܠܚ ܠܚܙܝܐ ܚܝܐ ܘܡܫܬܘܬܦܢܐ ܕܟܠ ܛܘܪܢܛܝܢ، ܦܝܪܝܢ، ܘܡܝܬܪܝܟܣ ܕܡܕܝܢܬܐ.

- ܢܩܒܬܐ ܕܥܠܝܬܐ: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- ܡܬܚܪܪܐ ܒ: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- ܫܪܝ: `uv run bitonic` ܐܘ `uv run ccbt dashboard`

ܚܙܝ ܠ [ܡܕܒܪܢܘܬܐ ܕܒܝܛܘܢܝܩ](bitonic.md) ܠܡܫܬܡܫܢܘܬܐ ܡܦܪܫܬܐ.

### 2. btbt CLI

**btbt** ܗܘ ܦܐܬܐ ܕܦܘܩܕܢܐ-ܫܪܝܬܐ ܕܡܬܬܟܝܢ ܥܡ ܡܢܝܘܬܐ ܪܒܬܐ.

- ܢܩܒܬܐ ܕܥܠܝܬܐ: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- ܡܬܚܪܪܐ ܒ: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- ܫܪܝ: `uv run btbt`

ܚܙܝ ܠ [ܡܥܠܝܬܐ ܕܒܝܛܒܝܛ CLI](btbt-cli.md) ܠܟܠ ܦܘܩܕܢܐ ܕܐܝܬܝܗܘܢ.

### 3. ccbt (CLI ܒܣܝܣܝܐ)

**ccbt** ܗܘ ܦܐܬܐ ܕܦܘܩܕܢܐ-ܫܪܝܬܐ ܒܣܝܣܝܬܐ.

- ܢܩܒܬܐ ܕܥܠܝܬܐ: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- ܡܬܚܪܪܐ ܒ: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- ܫܪܝ: `uv run ccbt`

## ܫܘܪܝܐ ܥܓܠ

### ܫܪܝ ܠܒܝܛܘܢܝܩ (ܡܘܨܦ)

ܫܪܝ ܠܕܐܫܒܘܪܕ ܕܛܪܡܝܢܠ:
```bash
uv run bitonic
```

ܐܘ ܡܢ ܦܐܬܐ ܕܟܠܝܐܝ:
```bash
uv run ccbt dashboard
```

ܥܡ ܪܝܬܐ ܕܚܕܬܐ ܕܡܬܬܟܝܢܐ:
```bash
uv run ccbt dashboard --refresh 2.0
```

### ܐܚܬ ܛܘܪܢܛ

ܡܫܬܡܫ ܒܟܠܝܐܝ:
```bash
# ܐܚܬ ܡܢ ܦܝܠܐ ܕܛܘܪܢܛ
uv run btbt download movie.torrent

# ܐܚܬ ܡܢ ܐܣܘܪܐ ܕܡܓܢܛ
uv run btbt magnet "magnet:?xt=urn:btih:..."

# ܥܡ ܚܕܝܢܐ ܕܪܝܬܐ
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

ܚܙܝ ܠ [ܡܥܠܝܬܐ ܕܒܝܛܒܝܛ CLI](btbt-cli.md) ܠܟܠ ܓܒܝܬܐ ܕܐܚܬܐ.

### ܬܟܢܝ ܠܟܘܢܝܐ ܕܟܘܢܝܐ

ܒܪܝ ܦܝܠܐ ܕ `ccbt.toml` ܒܕܝܪܟܬܘܪܝ ܕܥܒܕܟ. ܚܙܝ ܠܬܟܢܝܬܐ ܕܡܬܠܐ:
- ܬܟܢܝܬܐ ܕܒܣܝܣܝܬܐ: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- ܡܫܚܠܦܢܐ ܕܐܬܪܐ: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- ܡܕܝܢܬܐ ܕܬܟܢܝܬܐ: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

ܚܙܝ ܠ [ܡܕܒܪܢܘܬܐ ܕܬܟܢܝܬܐ](configuration.md) ܠܓܒܝܬܐ ܕܬܟܢܝܬܐ ܡܦܪܫܬܐ.

## ܬܘܒܝܢܐ ܕܦܪܘܝܟܬܐ

ܚܙܝ ܠܡܝܬܪܝܟܣ ܕܐܝܩܪܐ ܕܦܪܘܝܟܬܐ ܘܬܘܒܝܢܐ:

- **ܟܘܦܪܝܓ ܕܟܘܕܐ**: [reports/coverage.md](reports/coverage.md) - ܦܘܪܫܐ ܡܫܡܠܝܐ ܕܟܘܦܪܝܓ ܕܟܘܕܐ
- **ܬܘܒܝܢܐ ܕܐܡܢܘܬܐ**: [reports/bandit/index.md](reports/bandit/index.md) - ܦܠܓܐ ܕܦܘܪܫܐ ܕܐܡܢܘܬܐ ܡܢ Bandit
- **ܒܢܟܡܐܪܟܣ**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - ܦܠܓܐ ܕܒܢܟܡܐܪܟ ܕܬܘܩܦܐ

ܗܠܝܢ ܬܘܒܝܢܐ ܡܬܒܢܝܢ ܘܡܬܚܕܬܢ ܒܝܕ ܐܘܛܘܡܛܝܩ ܐܝܟ ܦܠܓܐ ܡܢ ܦܪܘܣܣ ܕܐܚܝܕܘܬܐ ܕܡܫܘܚܚܢܝܬܐ ܕܝܠܢ.

## ܨܠܘܒܐ ܕܒܬܪ

- [Bitonic](bitonic.md) - ܝܠܦ ܥܠ ܦܐܬܐ ܕܕܐܫܒܘܪܕ ܕܛܪܡܝܢܠ
- [btbt CLI](btbt-cli.md) - ܡܥܠܝܬܐ ܡܫܠܡܬܐ ܕܦܐܬܐ ܕܦܘܩܕܢܐ-ܫܪܝܬܐ
- [ܬܟܢܝܬܐ](configuration.md) - ܓܒܝܬܐ ܕܬܟܢܝܬܐ ܡܦܪܫܬܐ
- [ܬܟܢܝܬܐ ܕܬܘܩܦܐ](performance.md) - ܡܕܒܪܢܘܬܐ ܕܬܟܢܝܬܐ
- [ܡܥܠܝܬܐ ܕܐܦܝ ܐܝ](API.md) - ܟܬܒܐ ܕܐܦܝ ܐܝ ܕܦܝܬܘܢ ܕܡܫܡܠܐ ܠܡܢܝܘܬܐ ܕܢܛܪܘܬܐ

## ܩܒܠ ܥܕܪܐ

- ܡܫܬܡܫ ܒ `uv run bitonic --help` ܐܘ `uv run btbt --help` ܠܥܕܪܐ ܕܦܘܩܕܢܐ
- ܒܨܝ ܠ [ܡܥܠܝܬܐ ܕܒܝܛܒܝܛ CLI](btbt-cli.md) ܠܓܒܝܬܐ ܡܦܪܫܬܐ
- ܙܘܪ ܠ [ܡܐܟܙܢܐ ܕܓܝܛܗܘܒ](https://github.com/yourusername/ccbittorrent) ܕܝܠܢ ܠܡܫܐܠܐ ܘܡܠܟܫܐ






ܒܫܝܢܐ ܠܟܘܢ ܒܟܘܢܝܐ ܕܟܘܢܝܐ ܕܟܘܢܝܐ! ܗܢܐ ܡܕܒܪܢܘܬܐ ܢܥܕܪܟܘܢ ܕܬܫܪܘܢ ܘܬܪܕܘܢ ܒܥܓܠ ܥܡ ܟܠܝܢܛ ܒܝܛܛܘܪܢܛ ܕܬܘܩܦܐ ܪܡܐ ܕܝܠܢ.

!!! tip "ܡܢܝܘܬܐ ܪܫܝܬܐ: ܬܘܣܦܬܐ ܕܦܪܘܛܘܟܘܠ BEP XET"
    ccBitTorrent ܡܫܡܠܐ ܠܬܘܣܦܬܐ ܕܦܪܘܛܘܟܘܠ Xet (BEP XET) ܕܡܦܠܚ ܠܚܘܠܩܐ ܕܡܬܚܪܪ ܡܢ ܡܘܢܝܐ ܘܠܡܦܪܫܘܬܐ ܕܚܘܠܩܐ ܒܝܢ ܛܘܪܢܛܝܢ. ܗܕܐ ܡܗܦܟ ܠܒܝܛܛܘܪܢܛ ܠܡܕܝܢܬ ܦܝܠܝܢ ܕܦܝܪ-ܠ-ܦܝܪ ܕܡܬܚܕܪܐ ܘܡܬܚܕܪ ܕܡܬܬܟܝܢ ܠܫܘܬܦܘܬܐ. [ܝܠܦ ܝܬܝܪ ܥܠ BEP XET →](bep_xet.md)

## ܐܪܡܝܢܘܬܐ

### ܡܘܕܥܢܘܬܐ

- Python 3.8 ܐܘ ܝܬܝܪ
- ܡܕܒܪ ܦܩܥܬܐ [UV](https://astral.sh/uv) (ܡܘܨܦ)

### ܐܪܡܝ ܠܐܘܝܘܝ

ܐܪܡܝ ܠܐܘܝܘܝ ܡܢ ܣܟܪܝܦܬܐ ܕܐܪܡܝܢܘܬܐ ܪܫܡܝܬܐ:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### ܐܪܡܝ ܠܟܘܢܝܐ ܕܟܘܢܝܐ

ܐܪܡܝ ܡܢ PyPI:
```bash
uv pip install ccbittorrent
```

ܐܘ ܐܪܡܝ ܡܢ ܡܒܘܥܐ:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

ܢܩܒܬܐ ܕܥܠܝܬܐ ܡܬܚܪܪܐ ܒ [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81).

## ܢܩܒܬܐ ܕܥܠܝܬܐ ܪܫܝܬܐ

ccBitTorrent ܡܦܠܚ ܠܬܠܬ ܢܩܒܬܐ ܕܥܠܝܬܐ ܪܫܝܬܐ:

### 1. Bitonic (ܡܘܨܦ)

**Bitonic** ܗܘ ܦܐܬܐ ܕܕܐܫܒܘܪܕ ܕܛܪܡܝܢܠ ܪܫܝܬܐ. ܡܦܠܚ ܠܚܙܝܐ ܚܝܐ ܘܡܫܬܘܬܦܢܐ ܕܟܠ ܛܘܪܢܛܝܢ، ܦܝܪܝܢ، ܘܡܝܬܪܝܟܣ ܕܡܕܝܢܬܐ.

- ܢܩܒܬܐ ܕܥܠܝܬܐ: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- ܡܬܚܪܪܐ ܒ: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- ܫܪܝ: `uv run bitonic` ܐܘ `uv run ccbt dashboard`

ܚܙܝ ܠ [ܡܕܒܪܢܘܬܐ ܕܒܝܛܘܢܝܩ](bitonic.md) ܠܡܫܬܡܫܢܘܬܐ ܡܦܪܫܬܐ.

### 2. btbt CLI

**btbt** ܗܘ ܦܐܬܐ ܕܦܘܩܕܢܐ-ܫܪܝܬܐ ܕܡܬܬܟܝܢ ܥܡ ܡܢܝܘܬܐ ܪܒܬܐ.

- ܢܩܒܬܐ ܕܥܠܝܬܐ: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- ܡܬܚܪܪܐ ܒ: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- ܫܪܝ: `uv run btbt`

ܚܙܝ ܠ [ܡܥܠܝܬܐ ܕܒܝܛܒܝܛ CLI](btbt-cli.md) ܠܟܠ ܦܘܩܕܢܐ ܕܐܝܬܝܗܘܢ.

### 3. ccbt (CLI ܒܣܝܣܝܐ)

**ccbt** ܗܘ ܦܐܬܐ ܕܦܘܩܕܢܐ-ܫܪܝܬܐ ܒܣܝܣܝܬܐ.

- ܢܩܒܬܐ ܕܥܠܝܬܐ: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- ܡܬܚܪܪܐ ܒ: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- ܫܪܝ: `uv run ccbt`

## ܫܘܪܝܐ ܥܓܠ

### ܫܪܝ ܠܒܝܛܘܢܝܩ (ܡܘܨܦ)

ܫܪܝ ܠܕܐܫܒܘܪܕ ܕܛܪܡܝܢܠ:
```bash
uv run bitonic
```

ܐܘ ܡܢ ܦܐܬܐ ܕܟܠܝܐܝ:
```bash
uv run ccbt dashboard
```

ܥܡ ܪܝܬܐ ܕܚܕܬܐ ܕܡܬܬܟܝܢܐ:
```bash
uv run ccbt dashboard --refresh 2.0
```

### ܐܚܬ ܛܘܪܢܛ

ܡܫܬܡܫ ܒܟܠܝܐܝ:
```bash
# ܐܚܬ ܡܢ ܦܝܠܐ ܕܛܘܪܢܛ
uv run btbt download movie.torrent

# ܐܚܬ ܡܢ ܐܣܘܪܐ ܕܡܓܢܛ
uv run btbt magnet "magnet:?xt=urn:btih:..."

# ܥܡ ܚܕܝܢܐ ܕܪܝܬܐ
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

ܚܙܝ ܠ [ܡܥܠܝܬܐ ܕܒܝܛܒܝܛ CLI](btbt-cli.md) ܠܟܠ ܓܒܝܬܐ ܕܐܚܬܐ.

### ܬܟܢܝ ܠܟܘܢܝܐ ܕܟܘܢܝܐ

ܒܪܝ ܦܝܠܐ ܕ `ccbt.toml` ܒܕܝܪܟܬܘܪܝ ܕܥܒܕܟ. ܚܙܝ ܠܬܟܢܝܬܐ ܕܡܬܠܐ:
- ܬܟܢܝܬܐ ܕܒܣܝܣܝܬܐ: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- ܡܫܚܠܦܢܐ ܕܐܬܪܐ: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- ܡܕܝܢܬܐ ܕܬܟܢܝܬܐ: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

ܚܙܝ ܠ [ܡܕܒܪܢܘܬܐ ܕܬܟܢܝܬܐ](configuration.md) ܠܓܒܝܬܐ ܕܬܟܢܝܬܐ ܡܦܪܫܬܐ.

## ܬܘܒܝܢܐ ܕܦܪܘܝܟܬܐ

ܚܙܝ ܠܡܝܬܪܝܟܣ ܕܐܝܩܪܐ ܕܦܪܘܝܟܬܐ ܘܬܘܒܝܢܐ:

- **ܟܘܦܪܝܓ ܕܟܘܕܐ**: [reports/coverage.md](reports/coverage.md) - ܦܘܪܫܐ ܡܫܡܠܝܐ ܕܟܘܦܪܝܓ ܕܟܘܕܐ
- **ܬܘܒܝܢܐ ܕܐܡܢܘܬܐ**: [reports/bandit/index.md](reports/bandit/index.md) - ܦܠܓܐ ܕܦܘܪܫܐ ܕܐܡܢܘܬܐ ܡܢ Bandit
- **ܒܢܟܡܐܪܟܣ**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - ܦܠܓܐ ܕܒܢܟܡܐܪܟ ܕܬܘܩܦܐ

ܗܠܝܢ ܬܘܒܝܢܐ ܡܬܒܢܝܢ ܘܡܬܚܕܬܢ ܒܝܕ ܐܘܛܘܡܛܝܩ ܐܝܟ ܦܠܓܐ ܡܢ ܦܪܘܣܣ ܕܐܚܝܕܘܬܐ ܕܡܫܘܚܚܢܝܬܐ ܕܝܠܢ.

## ܨܠܘܒܐ ܕܒܬܪ

- [Bitonic](bitonic.md) - ܝܠܦ ܥܠ ܦܐܬܐ ܕܕܐܫܒܘܪܕ ܕܛܪܡܝܢܠ
- [btbt CLI](btbt-cli.md) - ܡܥܠܝܬܐ ܡܫܠܡܬܐ ܕܦܐܬܐ ܕܦܘܩܕܢܐ-ܫܪܝܬܐ
- [ܬܟܢܝܬܐ](configuration.md) - ܓܒܝܬܐ ܕܬܟܢܝܬܐ ܡܦܪܫܬܐ
- [ܬܟܢܝܬܐ ܕܬܘܩܦܐ](performance.md) - ܡܕܒܪܢܘܬܐ ܕܬܟܢܝܬܐ
- [ܡܥܠܝܬܐ ܕܐܦܝ ܐܝ](API.md) - ܟܬܒܐ ܕܐܦܝ ܐܝ ܕܦܝܬܘܢ ܕܡܫܡܠܐ ܠܡܢܝܘܬܐ ܕܢܛܪܘܬܐ

## ܩܒܠ ܥܕܪܐ

- ܡܫܬܡܫ ܒ `uv run bitonic --help` ܐܘ `uv run btbt --help` ܠܥܕܪܐ ܕܦܘܩܕܢܐ
- ܒܨܝ ܠ [ܡܥܠܝܬܐ ܕܒܝܛܒܝܛ CLI](btbt-cli.md) ܠܓܒܝܬܐ ܡܦܪܫܬܐ
- ܙܘܪ ܠ [ܡܐܟܙܢܐ ܕܓܝܛܗܘܒ](https://github.com/yourusername/ccbittorrent) ܕܝܠܢ ܠܡܫܐܠܐ ܘܡܠܟܫܐ
































































































































































































