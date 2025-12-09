# Fara Aiki

Barka da zuwa ccBitTorrent! Wannan jagorar za ta taimaka maka ka fara aiki da sauri tare da abokin cinikin BitTorrent na mu mai inganci.

!!! tip "Fasali Mai Muhimmanci: BEP XET Protocol Extension"
    ccBitTorrent ya haɗa da **Xet Protocol Extension (BEP XET)**, wanda ke ba da damar rarraba abun ciki da kuma rage kwafi tsakanin torrents. Wannan yana canza BitTorrent zuwa tsarin fayiloli na peer-to-peer mai sauri da za a iya sabuntawa wanda aka inganta don haɗin gwiwa. [Koyi ƙarin game da BEP XET →](bep_xet.md)

## Shigarwa

### Abubuwan da Ake Bukata

- Python 3.8 ko sama da haka
- [UV](https://astral.sh/uv) mai kula da fakiti (ana ba da shawara)

### Shigar da UV

Shigar da UV daga rubutun shigarwa na hukuma:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### Shigar da ccBitTorrent

Shigar daga PyPI:
```bash
uv pip install ccbittorrent
```

Ko kuma shigar daga tushe:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

Matsakaicin shigarwa an bayyana su a [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81).

## Matsakaicin Shigarwa na Farko

ccBitTorrent yana ba da matsakaicin shigarwa guda uku:

### 1. Bitonic (Ana Ba da Shawara)

**Bitonic** shine babban tsarin dashboard na terminal. Yana ba da ra'ayi mai rai, mai hulɗa na duk torrents, peers, da ma'auni na tsarin.

- Matsakaicin shigarwa: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- An bayyana a: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- Kaddamar: `uv run bitonic` ko `uv run ccbt dashboard`

Don amfani mai cikakke, duba [Jagorar Bitonic](bitonic.md).

### 2. btbt CLI

**btbt** shine ingantaccen tsarin layin umarni mai fasali masu yawa.

- Matsakaicin shigarwa: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- An bayyana a: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- Kaddamar: `uv run btbt`

Don duk umarnin da ake samu, duba [Nassoshi na btbt CLI](btbt-cli.md).

### 3. ccbt (CLI na Asali)

**ccbt** shine tsarin layin umarni na asali.

- Matsakaicin shigarwa: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- An bayyana a: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- Kaddamar: `uv run ccbt`

## Fara Aiki da Sauri

### Kaddamar Bitonic (Ana Ba da Shawara)

Fara dashboard na terminal:
```bash
uv run bitonic
```

Ko ta hanyar CLI:
```bash
uv run ccbt dashboard
```

Tare da ƙimar sabuntawa na musamman:
```bash
uv run ccbt dashboard --refresh 2.0
```

### Zazzage Torrent

Ta amfani da CLI:
```bash
# Zazzage daga fayil ɗin torrent
uv run btbt download movie.torrent

# Zazzage daga hanyar haɗin magnet
uv run btbt magnet "magnet:?xt=urn:btih:..."

# Tare da iyakoki na gudun
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

Don duk zaɓuɓɓukan zazzagewa, duba [Nassoshi na btbt CLI](btbt-cli.md).

### Saita ccBitTorrent

Ƙirƙiri fayil ɗin `ccbt.toml` a cikin babban fayil ɗin aikin ku. Duba misalin saitin:
- Saitin tsoho: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- Masu canza yanayi: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- Tsarin saitin: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

Don cikakkun zaɓuɓɓukan saitin, duba [Jagorar Saitin](configuration.md).

## Rahotanni na Ayyuka

Duba ma'auni na ingancin ayyuka da rahotanni:

- **Rufin Kode**: [reports/coverage.md](reports/coverage.md) - Cikakken nazarin rufin kode
- **Rahoton Tsaro**: [reports/bandit/index.md](reports/bandit/index.md) - Sakamakon binciken tsaro daga Bandit
- **Ma'auni**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - Sakamakon ma'auni na aiki

Ana samar da waɗannan rahotanni kuma ana sabunta su ta atomatik a matsayin wani ɓangare na tsarin haɗin gwiwa na ci gaba.

## Matakai na Gaba

- [Bitonic](bitonic.md) - Koyi game da tsarin dashboard na terminal
- [btbt CLI](btbt-cli.md) - Cikakken nassoshi na tsarin layin umarni
- [Saitin](configuration.md) - Cikakkun zaɓuɓɓukan saitin
- [Gyara Aiki](performance.md) - Jagorar ingantawa
- [Nassoshi na API](API.md) - Takardun API na Python gami da fasali na sa ido

## Samun Taimako

- Yi amfani da `uv run bitonic --help` ko `uv run btbt --help` don taimakon umarni
- Bincika [Nassoshi na btbt CLI](btbt-cli.md) don cikakkun zaɓuɓɓuka
- Ziyarci [ma'ajiyar mu ta GitHub](https://github.com/yourusername/ccbittorrent) don batutuwa da tattaunawa






Barka da zuwa ccBitTorrent! Wannan jagorar za ta taimaka maka ka fara aiki da sauri tare da abokin cinikin BitTorrent na mu mai inganci.

!!! tip "Fasali Mai Muhimmanci: BEP XET Protocol Extension"
    ccBitTorrent ya haɗa da **Xet Protocol Extension (BEP XET)**, wanda ke ba da damar rarraba abun ciki da kuma rage kwafi tsakanin torrents. Wannan yana canza BitTorrent zuwa tsarin fayiloli na peer-to-peer mai sauri da za a iya sabuntawa wanda aka inganta don haɗin gwiwa. [Koyi ƙarin game da BEP XET →](bep_xet.md)

## Shigarwa

### Abubuwan da Ake Bukata

- Python 3.8 ko sama da haka
- [UV](https://astral.sh/uv) mai kula da fakiti (ana ba da shawara)

### Shigar da UV

Shigar da UV daga rubutun shigarwa na hukuma:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### Shigar da ccBitTorrent

Shigar daga PyPI:
```bash
uv pip install ccbittorrent
```

Ko kuma shigar daga tushe:
```bash
git clone https://github.com/yourusername/ccbittorrent.git
cd ccbittorrent
uv pip install -e .
```

Matsakaicin shigarwa an bayyana su a [pyproject.toml:79-81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79-L81).

## Matsakaicin Shigarwa na Farko

ccBitTorrent yana ba da matsakaicin shigarwa guda uku:

### 1. Bitonic (Ana Ba da Shawara)

**Bitonic** shine babban tsarin dashboard na terminal. Yana ba da ra'ayi mai rai, mai hulɗa na duk torrents, peers, da ma'auni na tsarin.

- Matsakaicin shigarwa: [ccbt/interface/terminal_dashboard.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- An bayyana a: [pyproject.toml:81](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L81)
- Kaddamar: `uv run bitonic` ko `uv run ccbt dashboard`

Don amfani mai cikakke, duba [Jagorar Bitonic](bitonic.md).

### 2. btbt CLI

**btbt** shine ingantaccen tsarin layin umarni mai fasali masu yawa.

- Matsakaicin shigarwa: [ccbt/cli/main.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/cli/main.py#L1463)
- An bayyana a: [pyproject.toml:80](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L80)
- Kaddamar: `uv run btbt`

Don duk umarnin da ake samu, duba [Nassoshi na btbt CLI](btbt-cli.md).

### 3. ccbt (CLI na Asali)

**ccbt** shine tsarin layin umarni na asali.

- Matsakaicin shigarwa: [ccbt/__main__.py:main](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/__main__.py#L18)
- An bayyana a: [pyproject.toml:79](https://github.com/yourusername/ccbittorrent/blob/main/pyproject.toml#L79)
- Kaddamar: `uv run ccbt`

## Fara Aiki da Sauri

### Kaddamar Bitonic (Ana Ba da Shawara)

Fara dashboard na terminal:
```bash
uv run bitonic
```

Ko ta hanyar CLI:
```bash
uv run ccbt dashboard
```

Tare da ƙimar sabuntawa na musamman:
```bash
uv run ccbt dashboard --refresh 2.0
```

### Zazzage Torrent

Ta amfani da CLI:
```bash
# Zazzage daga fayil ɗin torrent
uv run btbt download movie.torrent

# Zazzage daga hanyar haɗin magnet
uv run btbt magnet "magnet:?xt=urn:btih:..."

# Tare da iyakoki na gudun
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512
```

Don duk zaɓuɓɓukan zazzagewa, duba [Nassoshi na btbt CLI](btbt-cli.md).

### Saita ccBitTorrent

Ƙirƙiri fayil ɗin `ccbt.toml` a cikin babban fayil ɗin aikin ku. Duba misalin saitin:
- Saitin tsoho: [ccbt.toml](https://github.com/yourusername/ccbittorrent/blob/main/ccbt.toml)
- Masu canza yanayi: [env.example](https://github.com/yourusername/ccbittorrent/blob/main/env.example)
- Tsarin saitin: [ccbt/config/config.py](https://github.com/yourusername/ccbittorrent/blob/main/ccbt/config/config.py)

Don cikakkun zaɓuɓɓukan saitin, duba [Jagorar Saitin](configuration.md).

## Rahotanni na Ayyuka

Duba ma'auni na ingancin ayyuka da rahotanni:

- **Rufin Kode**: [reports/coverage.md](reports/coverage.md) - Cikakken nazarin rufin kode
- **Rahoton Tsaro**: [reports/bandit/index.md](reports/bandit/index.md) - Sakamakon binciken tsaro daga Bandit
- **Ma'auni**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - Sakamakon ma'auni na aiki

Ana samar da waɗannan rahotanni kuma ana sabunta su ta atomatik a matsayin wani ɓangare na tsarin haɗin gwiwa na ci gaba.

## Matakai na Gaba

- [Bitonic](bitonic.md) - Koyi game da tsarin dashboard na terminal
- [btbt CLI](btbt-cli.md) - Cikakken nassoshi na tsarin layin umarni
- [Saitin](configuration.md) - Cikakkun zaɓuɓɓukan saitin
- [Gyara Aiki](performance.md) - Jagorar ingantawa
- [Nassoshi na API](API.md) - Takardun API na Python gami da fasali na sa ido

## Samun Taimako

- Yi amfani da `uv run bitonic --help` ko `uv run btbt --help` don taimakon umarni
- Bincika [Nassoshi na btbt CLI](btbt-cli.md) don cikakkun zaɓuɓɓuka
- Ziyarci [ma'ajiyar mu ta GitHub](https://github.com/yourusername/ccbittorrent) don batutuwa da tattaunawa
































































































































































































