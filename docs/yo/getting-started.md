# Bíbẹ̀rẹ̀

Kaabọ si ccBitTorrent! Ìtọ́sọ́nà yìí yóò ràn ọ́ lọ́wọ́ láti bẹ̀rẹ̀ ní kíákíá pẹ̀lú ẹ̀rọ BitTorrent tí ó ṣe dáadáa.

!!! tip "Ẹ̀yà Pàtàkì: BEP XET Protocol Extension"
    ccBitTorrent ní **Xet Protocol Extension (BEP XET)** tí ó mú kí a lè ṣe ìpíndá àkóónú àti ìyọkúrò ìdàpọ̀ láàárín torrents. Èyí yípadà BitTorrent sí àwọn ìfáìlì peer-to-peer tí ó yára púpọ̀ tí a lè ṣe àtúnṣe tí ó ṣe dáadáa fún ìṣọ̀kan. [Kọ́ nípa BEP XET sí i →](bep_xet.md)

## Ìfisílẹ̀

### Àwọn Ohun tí a Nílò

- Python 3.8 tàbí tó ga ju bẹ́ẹ̀
- [UV](https://astral.sh/uv) olùṣàkóso àwọn pákéètì (a dábàá)

### Fi UV sílẹ̀

Fi UV sílẹ̀ láti ìgbàtẹ́ ìfisílẹ̀ ìjọba:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### Fi ccBitTorrent sílẹ̀

Fi sílẹ̀ láti PyPI:
```bash
uv pip install ccbittorrent
```

Tàbí fi sílẹ̀ láti orísun:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

Àwọn ibẹ̀rẹ̀ ìwọlé wà ní [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81).

## Àwọn Ibẹ̀rẹ̀ Ìwọlé Pàtàkì

ccBitTorrent pèsè àwọn ibẹ̀rẹ̀ ìwọlé mẹ́ta:

### 1. Bitonic (A Dábàá)

**Bitonic** jẹ́ àwọn ìfọ̀rọ̀wérẹ́ dashboard tẹ́ẹ̀mínà àkọ́kọ́. Ó pèsè ìwòye tí ó ṣe dáadáa, tí ó ṣe ìbáṣepọ̀ fún gbogbo torrents, peers, àti àwọn ìwọ̀n ìgbàkọlé.

- Ibẹ̀rẹ̀ ìwọlé: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- A ṣàlàyé ní: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- Bẹ̀rẹ̀: `uv run bitonic` tàbí `uv run ccbt dashboard`

Wo [Ìtọ́sọ́nà Bitonic](bitonic.md) fún lilo tí ó ṣe dáadáa.

### 2. btbt CLI

**btbt** jẹ́ àwọn ìfọ̀rọ̀wérẹ́ ìlànà àṣẹ tí ó ṣe dáadáa tí ó ní ọ̀pọ̀lọpọ̀ àwọn ẹ̀yà.

- Ibẹ̀rẹ̀ ìwọlé: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- A ṣàlàyé ní: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- Bẹ̀rẹ̀: `uv run btbt`

Wo [Àtẹ̀jáde btbt CLI](btbt-cli.md) fún gbogbo àwọn àṣẹ tí ó wà.

### 3. ccbt (CLI Àkọ́kọ́)

**ccbt** jẹ́ àwọn ìfọ̀rọ̀wérẹ́ ìlànà àṣẹ àkọ́kọ́.

- Ibẹ̀rẹ̀ ìwọlé: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- A ṣàlàyé ní: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- Bẹ̀rẹ̀: `uv run ccbt`

## Bíbẹ̀rẹ̀ Kíákíá

### Bẹ̀rẹ̀ Bitonic (A Dábàá)

Bẹ̀rẹ̀ dashboard tẹ́ẹ̀mínà:
```bash
uv run bitonic
```

Tàbí nípa CLI:
```bash
uv run ccbt dashboard
```

Pẹ̀lú ìwọ̀n ìtúnṣe tí ó ṣe dáadáa:
```bash
uv run ccbt dashboard --refresh 2.0
```

### Gba Torrent

Lílo CLI:
```bash
# Gba láti fàìlì torrent
uv run btbt download movie.torrent

# Gba láti ìkàn torrent
uv run btbt magnet "magnet:?xt=urn:btih:..."

# Pẹ̀lú àwọn ìdíwọ̀n ìyára
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

Wo [Àtẹ̀jáde btbt CLI](btbt-cli.md) fún gbogbo àwọn àṣàyàn ìgbàsílẹ̀.

### Ṣètò ccBitTorrent

Ṣẹ̀dá fàìlì `ccbt.toml` ní àwọn fóldà iṣẹ́ rẹ. Wo àpẹrẹ ṣètò:
- Ṣètò àkọ́kọ́: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- Àwọn onírúurú ayé: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- Ìgbàkọlé ṣètò: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

Wo [Ìtọ́sọ́nà Ṣètò](configuration.md) fún àwọn àṣàyàn ṣètò tí ó ṣe dáadáa.

## Àwọn Ìròyìn Ìṣẹ́

Wo àwọn ìwọ̀n ìdárayá ìṣẹ́ àti àwọn ìròyìn:

- **Ìpamọ́ Kódù**: [reports/coverage.md](reports/coverage.md) - Ìtúpalẹ̀ ìpamọ́ kódù tí ó ṣe dáadáa
- **Ìròyìn Ààbò**: [reports/bandit/index.md](reports/bandit/index.md) - Àwọn èsì ìwádìí ààbò láti Bandit
- **Àwọn Ìwọ̀n**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - Àwọn èsì ìwọ̀n iṣẹ́

A ṣẹ̀dá àwọn ìròyìn yìí àti a túnṣe wọn ní àìdánilójú gẹ́gẹ́ bí apá ìgbàkọlé ìgbàkọlé wa.

## Àwọn Ìgbésẹ̀ Tókàn

- [Bitonic](bitonic.md) - Kọ́ nípa àwọn ìfọ̀rọ̀wérẹ́ dashboard tẹ́ẹ̀mínà
- [btbt CLI](btbt-cli.md) - Àtẹ̀jáde ìfọ̀rọ̀wérẹ́ ìlànà àṣẹ tí ó ṣe dáadáa
- [Ṣètò](configuration.md) - Àwọn àṣàyàn ṣètò tí ó ṣe dáadáa
- [Ìtúnṣe Iṣẹ́](performance.md) - Ìtọ́sọ́nà ìtúnṣe
- [Àtẹ̀jáde API](API.md) - Ìwé ìtúpalẹ̀ API Python pẹ̀lú àwọn ẹ̀yà ìtọ́kàsọ̀

## Gba Ìrànlọ́wọ́

- Lo `uv run bitonic --help` tàbí `uv run btbt --help` fún ìrànlọ́wọ́ àṣẹ
- Ṣayẹ̀wò [Àtẹ̀jáde btbt CLI](btbt-cli.md) fún àwọn àṣàyàn tí ó ṣe dáadáa
- Wọ àwọn àpótí wa GitHub](https://github.com/yourusername/ccbittorrent) fún àwọn ìṣòro àti àwọn ìjíròrò






Kaabọ si ccBitTorrent! Ìtọ́sọ́nà yìí yóò ràn ọ́ lọ́wọ́ láti bẹ̀rẹ̀ ní kíákíá pẹ̀lú ẹ̀rọ BitTorrent tí ó ṣe dáadáa.

!!! tip "Ẹ̀yà Pàtàkì: BEP XET Protocol Extension"
    ccBitTorrent ní **Xet Protocol Extension (BEP XET)** tí ó mú kí a lè ṣe ìpíndá àkóónú àti ìyọkúrò ìdàpọ̀ láàárín torrents. Èyí yípadà BitTorrent sí àwọn ìfáìlì peer-to-peer tí ó yára púpọ̀ tí a lè ṣe àtúnṣe tí ó ṣe dáadáa fún ìṣọ̀kan. [Kọ́ nípa BEP XET sí i →](bep_xet.md)

## Ìfisílẹ̀

### Àwọn Ohun tí a Nílò

- Python 3.8 tàbí tó ga ju bẹ́ẹ̀
- [UV](https://astral.sh/uv) olùṣàkóso àwọn pákéètì (a dábàá)

### Fi UV sílẹ̀

Fi UV sílẹ̀ láti ìgbàtẹ́ ìfisílẹ̀ ìjọba:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### Fi ccBitTorrent sílẹ̀

Fi sílẹ̀ láti PyPI:
```bash
uv pip install ccbittorrent
```

Tàbí fi sílẹ̀ láti orísun:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

Àwọn ibẹ̀rẹ̀ ìwọlé wà ní [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81).

## Àwọn Ibẹ̀rẹ̀ Ìwọlé Pàtàkì

ccBitTorrent pèsè àwọn ibẹ̀rẹ̀ ìwọlé mẹ́ta:

### 1. Bitonic (A Dábàá)

**Bitonic** jẹ́ àwọn ìfọ̀rọ̀wérẹ́ dashboard tẹ́ẹ̀mínà àkọ́kọ́. Ó pèsè ìwòye tí ó ṣe dáadáa, tí ó ṣe ìbáṣepọ̀ fún gbogbo torrents, peers, àti àwọn ìwọ̀n ìgbàkọlé.

- Ibẹ̀rẹ̀ ìwọlé: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- A ṣàlàyé ní: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- Bẹ̀rẹ̀: `uv run bitonic` tàbí `uv run ccbt dashboard`

Wo [Ìtọ́sọ́nà Bitonic](bitonic.md) fún lilo tí ó ṣe dáadáa.

### 2. btbt CLI

**btbt** jẹ́ àwọn ìfọ̀rọ̀wérẹ́ ìlànà àṣẹ tí ó ṣe dáadáa tí ó ní ọ̀pọ̀lọpọ̀ àwọn ẹ̀yà.

- Ibẹ̀rẹ̀ ìwọlé: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- A ṣàlàyé ní: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- Bẹ̀rẹ̀: `uv run btbt`

Wo [Àtẹ̀jáde btbt CLI](btbt-cli.md) fún gbogbo àwọn àṣẹ tí ó wà.

### 3. ccbt (CLI Àkọ́kọ́)

**ccbt** jẹ́ àwọn ìfọ̀rọ̀wérẹ́ ìlànà àṣẹ àkọ́kọ́.

- Ibẹ̀rẹ̀ ìwọlé: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- A ṣàlàyé ní: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- Bẹ̀rẹ̀: `uv run ccbt`

## Bíbẹ̀rẹ̀ Kíákíá

### Bẹ̀rẹ̀ Bitonic (A Dábàá)

Bẹ̀rẹ̀ dashboard tẹ́ẹ̀mínà:
```bash
uv run bitonic
```

Tàbí nípa CLI:
```bash
uv run ccbt dashboard
```

Pẹ̀lú ìwọ̀n ìtúnṣe tí ó ṣe dáadáa:
```bash
uv run ccbt dashboard --refresh 2.0
```

### Gba Torrent

Lílo CLI:
```bash
# Gba láti fàìlì torrent
uv run btbt download movie.torrent

# Gba láti ìkàn torrent
uv run btbt magnet "magnet:?xt=urn:btih:..."

# Pẹ̀lú àwọn ìdíwọ̀n ìyára
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

Wo [Àtẹ̀jáde btbt CLI](btbt-cli.md) fún gbogbo àwọn àṣàyàn ìgbàsílẹ̀.

### Ṣètò ccBitTorrent

Ṣẹ̀dá fàìlì `ccbt.toml` ní àwọn fóldà iṣẹ́ rẹ. Wo àpẹrẹ ṣètò:
- Ṣètò àkọ́kọ́: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- Àwọn onírúurú ayé: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- Ìgbàkọlé ṣètò: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

Wo [Ìtọ́sọ́nà Ṣètò](configuration.md) fún àwọn àṣàyàn ṣètò tí ó ṣe dáadáa.

## Àwọn Ìròyìn Ìṣẹ́

Wo àwọn ìwọ̀n ìdárayá ìṣẹ́ àti àwọn ìròyìn:

- **Ìpamọ́ Kódù**: [reports/coverage.md](reports/coverage.md) - Ìtúpalẹ̀ ìpamọ́ kódù tí ó ṣe dáadáa
- **Ìròyìn Ààbò**: [reports/bandit/index.md](reports/bandit/index.md) - Àwọn èsì ìwádìí ààbò láti Bandit
- **Àwọn Ìwọ̀n**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - Àwọn èsì ìwọ̀n iṣẹ́

A ṣẹ̀dá àwọn ìròyìn yìí àti a túnṣe wọn ní àìdánilójú gẹ́gẹ́ bí apá ìgbàkọlé ìgbàkọlé wa.

## Àwọn Ìgbésẹ̀ Tókàn

- [Bitonic](bitonic.md) - Kọ́ nípa àwọn ìfọ̀rọ̀wérẹ́ dashboard tẹ́ẹ̀mínà
- [btbt CLI](btbt-cli.md) - Àtẹ̀jáde ìfọ̀rọ̀wérẹ́ ìlànà àṣẹ tí ó ṣe dáadáa
- [Ṣètò](configuration.md) - Àwọn àṣàyàn ṣètò tí ó ṣe dáadáa
- [Ìtúnṣe Iṣẹ́](performance.md) - Ìtọ́sọ́nà ìtúnṣe
- [Àtẹ̀jáde API](API.md) - Ìwé ìtúpalẹ̀ API Python pẹ̀lú àwọn ẹ̀yà ìtọ́kàsọ̀

## Gba Ìrànlọ́wọ́

- Lo `uv run bitonic --help` tàbí `uv run btbt --help` fún ìrànlọ́wọ́ àṣẹ
- Ṣayẹ̀wò [Àtẹ̀jáde btbt CLI](btbt-cli.md) fún àwọn àṣàyàn tí ó ṣe dáadáa
- Wọ àwọn àpótí wa GitHub](https://github.com/yourusername/ccbittorrent) fún àwọn ìṣòro àti àwọn ìjíròrò




























































































































































































