# Kuanza

Karibu ccBitTorrent! Mwongozo huu utakusaidia kuanza haraka na klienti yetu ya BitTorrent yenye utendakazi wa juu.

!!! tip "Kipengele Muhimu: BEP XET Protocol Extension"
    ccBitTorrent inajumuisha **Xet Protocol Extension (BEP XET)**, ambayo inawezesha kugawanya maudhui na kuondoa kurudia kati ya torrents. Hii inabadilisha BitTorrent kuwa mfumo wa faili wa peer-to-peer wa haraka sana na unaoweza kusasishwa ulioongezwa kwa ushirikiano. [Jifunze zaidi kuhusu BEP XET →](bep_xet.md)

## Usanidi

### Mahitaji

- Python 3.8 au zaidi
- [UV](https://astral.sh/uv) msimamizi wa pakiti (inapendekezwa)

### Sanidi UV

Sanidi UV kutoka kwa hati ya usanidi rasmi:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### Sanidi ccBitTorrent

Sanidi kutoka PyPI:
```bash
uv pip install ccbittorrent
```

Au sanidi kutoka chanzo:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

Sehemu za kuingia zimefafanuliwa katika [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81).

## Sehemu za Kuingia Kuu

ccBitTorrent hutoa sehemu tatu za kuingia:

### 1. Bitonic (Inapendekezwa)

**Bitonic** ni kiolesura kuu cha dashboard ya terminal. Hutoa muonekano wa moja kwa moja, unaoendelea wa torrents zote, peers, na vipimo vya mfumo.

- Sehemu ya kuingia: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- Imefafanuliwa katika: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- Anzisha: `uv run bitonic` au `uv run ccbt dashboard`

Angalia [Mwongozo wa Bitonic](bitonic.md) kwa matumizi ya kina.

### 2. btbt CLI

**btbt** ni kiolesura cha mstari wa amri kilichoimarishwa chenye vipengele vingi.

- Sehemu ya kuingia: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- Imefafanuliwa katika: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- Anzisha: `uv run btbt`

Angalia [Marejeo ya btbt CLI](btbt-cli.md) kwa amri zote zinazopatikana.

### 3. ccbt (CLI ya Msingi)

**ccbt** ni kiolesura ya mstari wa amri ya msingi.

- Sehemu ya kuingia: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- Imefafanuliwa katika: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- Anzisha: `uv run ccbt`

## Kuanza Haraka

### Anzisha Bitonic (Inapendekezwa)

Anzisha dashboard ya terminal:
```bash
uv run bitonic
```

Au kupitia CLI:
```bash
uv run ccbt dashboard
```

Kwa kiwango cha kusasisha maalum:
```bash
uv run ccbt dashboard --refresh 2.0
```

### Pakua Torrent

Kutumia CLI:
```bash
# Pakua kutoka faili ya torrent
uv run btbt download movie.torrent

# Pakua kutoka kiungo cha magnet
uv run btbt magnet "magnet:?xt=urn:btih:..."

# Kwa mipaka ya kasi
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

Angalia [Marejeo ya btbt CLI](btbt-cli.md) kwa chaguzi zote za kupakua.

### Sanidi ccBitTorrent

Unda faili `ccbt.toml` katika saraka yako ya kazi. Rejea usanidi wa mfano:
- Usanidi wa kawaida: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- Vigezo vya mazingira: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- Mfumo wa usanidi: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

Angalia [Mwongozo wa Usanidi](configuration.md) kwa chaguzi za kina za usanidi.

## Ripoti za Mradi

Angalia vipimo vya ubora wa mradi na ripoti:

- **Ufunikaji wa Kodi**: [reports/coverage.md](reports/coverage.md) - Uchambuzi kamili wa ufunikaji wa kodi
- **Ripoti ya Usalama**: [reports/bandit/index.md](reports/bandit/index.md) - Matokeo ya uchunguzi wa usalama kutoka Bandit
- **Vipimo**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - Matokeo ya vipimo vya utendakazi

Ripoti hizi zinaundwa na kusasishwa kiotomatiki kama sehemu ya mchakato wetu wa kuunganisha endelevu.

## Hatua Zinazofuata

- [Bitonic](bitonic.md) - Jifunze kuhusu kiolesura cha dashboard ya terminal
- [btbt CLI](btbt-cli.md) - Marejeo kamili ya kiolesura ya mstari wa amri
- [Usanidi](configuration.md) - Chaguzi za kina za usanidi
- [Urekebishaji wa Utendakazi](performance.md) - Mwongozo wa uboreshaji
- [Marejeo ya API](API.md) - Hati za API za Python pamoja na vipengele vya ufuatiliaji

## Kupata Msaada

- Tumia `uv run bitonic --help` au `uv run btbt --help` kwa msaada wa amri
- Angalia [Marejeo ya btbt CLI](btbt-cli.md) kwa chaguzi za kina
- Tembelea [hifadhi yetu ya GitHub](https://github.com/yourusername/ccbittorrent) kwa masuala na mazungumzo






Karibu ccBitTorrent! Mwongozo huu utakusaidia kuanza haraka na klienti yetu ya BitTorrent yenye utendakazi wa juu.

!!! tip "Kipengele Muhimu: BEP XET Protocol Extension"
    ccBitTorrent inajumuisha **Xet Protocol Extension (BEP XET)**, ambayo inawezesha kugawanya maudhui na kuondoa kurudia kati ya torrents. Hii inabadilisha BitTorrent kuwa mfumo wa faili wa peer-to-peer wa haraka sana na unaoweza kusasishwa ulioongezwa kwa ushirikiano. [Jifunze zaidi kuhusu BEP XET →](bep_xet.md)

## Usanidi

### Mahitaji

- Python 3.8 au zaidi
- [UV](https://astral.sh/uv) msimamizi wa pakiti (inapendekezwa)

### Sanidi UV

Sanidi UV kutoka kwa hati ya usanidi rasmi:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### Sanidi ccBitTorrent

Sanidi kutoka PyPI:
```bash
uv pip install ccbittorrent
```

Au sanidi kutoka chanzo:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

Sehemu za kuingia zimefafanuliwa katika [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81).

## Sehemu za Kuingia Kuu

ccBitTorrent hutoa sehemu tatu za kuingia:

### 1. Bitonic (Inapendekezwa)

**Bitonic** ni kiolesura kuu cha dashboard ya terminal. Hutoa muonekano wa moja kwa moja, unaoendelea wa torrents zote, peers, na vipimo vya mfumo.

- Sehemu ya kuingia: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- Imefafanuliwa katika: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- Anzisha: `uv run bitonic` au `uv run ccbt dashboard`

Angalia [Mwongozo wa Bitonic](bitonic.md) kwa matumizi ya kina.

### 2. btbt CLI

**btbt** ni kiolesura cha mstari wa amri kilichoimarishwa chenye vipengele vingi.

- Sehemu ya kuingia: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- Imefafanuliwa katika: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- Anzisha: `uv run btbt`

Angalia [Marejeo ya btbt CLI](btbt-cli.md) kwa amri zote zinazopatikana.

### 3. ccbt (CLI ya Msingi)

**ccbt** ni kiolesura ya mstari wa amri ya msingi.

- Sehemu ya kuingia: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- Imefafanuliwa katika: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- Anzisha: `uv run ccbt`

## Kuanza Haraka

### Anzisha Bitonic (Inapendekezwa)

Anzisha dashboard ya terminal:
```bash
uv run bitonic
```

Au kupitia CLI:
```bash
uv run ccbt dashboard
```

Kwa kiwango cha kusasisha maalum:
```bash
uv run ccbt dashboard --refresh 2.0
```

### Pakua Torrent

Kutumia CLI:
```bash
# Pakua kutoka faili ya torrent
uv run btbt download movie.torrent

# Pakua kutoka kiungo cha magnet
uv run btbt magnet "magnet:?xt=urn:btih:..."

# Kwa mipaka ya kasi
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

Angalia [Marejeo ya btbt CLI](btbt-cli.md) kwa chaguzi zote za kupakua.

### Sanidi ccBitTorrent

Unda faili `ccbt.toml` katika saraka yako ya kazi. Rejea usanidi wa mfano:
- Usanidi wa kawaida: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- Vigezo vya mazingira: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- Mfumo wa usanidi: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

Angalia [Mwongozo wa Usanidi](configuration.md) kwa chaguzi za kina za usanidi.

## Ripoti za Mradi

Angalia vipimo vya ubora wa mradi na ripoti:

- **Ufunikaji wa Kodi**: [reports/coverage.md](reports/coverage.md) - Uchambuzi kamili wa ufunikaji wa kodi
- **Ripoti ya Usalama**: [reports/bandit/index.md](reports/bandit/index.md) - Matokeo ya uchunguzi wa usalama kutoka Bandit
- **Vipimo**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - Matokeo ya vipimo vya utendakazi

Ripoti hizi zinaundwa na kusasishwa kiotomatiki kama sehemu ya mchakato wetu wa kuunganisha endelevu.

## Hatua Zinazofuata

- [Bitonic](bitonic.md) - Jifunze kuhusu kiolesura cha dashboard ya terminal
- [btbt CLI](btbt-cli.md) - Marejeo kamili ya kiolesura ya mstari wa amri
- [Usanidi](configuration.md) - Chaguzi za kina za usanidi
- [Urekebishaji wa Utendakazi](performance.md) - Mwongozo wa uboreshaji
- [Marejeo ya API](API.md) - Hati za API za Python pamoja na vipengele vya ufuatiliaji

## Kupata Msaada

- Tumia `uv run bitonic --help` au `uv run btbt --help` kwa msaada wa amri
- Angalia [Marejeo ya btbt CLI](btbt-cli.md) kwa chaguzi za kina
- Tembelea [hifadhi yetu ya GitHub](https://github.com/yourusername/ccbittorrent) kwa masuala na mazungumzo




























































































































































































