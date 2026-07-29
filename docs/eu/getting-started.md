# Hasi

Ongi etorri ccBitTorrent-era! Gida honek BitTorrent bezeroaren abiadura handiarekin azkar hastea eta exekutatzea lagunduko dizu.

!!! tip "Ezaugarri Garrantzitsua: BEP XET Protokolo Hedapena"
    ccBitTorrent-ek **Xet Protokolo Hedapena (BEP XET)** barne hartzen du, edukia definitutako txunkatzea eta torrent arteko deduplikazioa ahalbidetzen dituena. Honek BitTorrent lankidetzarako optimizatutako peer-to-peer fitxategi-sistema super azkar eta eguneragarri bihurtzen du. [Ikasi gehiago BEP XET-i buruz →](bep_xet.md)

## Instalazioa

### Aurrebaldintzak

- Python 3.8 edo handiagoa
- [UV](https://astral.sh/uv) pakete kudeatzailea (gomendatua)

### Instalatu UV

Instalatu UV ofizialeko instalazio script-etik:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### Instalatu ccBitTorrent

Instalatu PyPI-tik:
```bash
uv pip install ccbittorrent
```

Edo instalatu iturburutik:
```bash
git clone https://github.com/ccBittorrent/ccbt.git
cd ccbt
uv pip install -e .
```

Sarrera puntuak [pyproject.toml:79-81](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L79-L81) definituak daude.

## Sarrera Puntu Nagusiak

ccBitTorrent-ek hiru sarrera puntu nagusi eskaintzen ditu:

### 1. Bitonic (Gomendatua)

**Bitonic** terminal panelen interfaze nagusia da. Torrent, peer eta sistema metrika guztien ikuspegi interaktibo eta zuzena eskaintzen du.

- Sarrera puntua: [ccbt/interface/terminal_dashboard.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- Definitua: [pyproject.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L81)
- Abiarazi: `uv run bitonic` edo `uv run ccbt dashboard`

Erabilera xehatuagatik, ikusi [Bitonic Gida](bitonic.md).

### 2. btbt CLI

**btbt** ezaugarri aberatsak dituen komando-lerroko interfaze hobetua da.

- Sarrera puntua: [ccbt/cli/main.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1463)
- Definitua: [pyproject.toml:80](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L80)
- Abiarazi: `uv run btbt`

Komando eskuragarri guztietarako, ikusi [btbt CLI Erreferentzia](btbt-cli.md).

### 3. ccbt (CLI Oinarrizkoa)

**ccbt** komando-lerroko interfaze oinarrizkoa da.

- Sarrera puntua: [ccbt/__main__.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/__main__.py#L18)
- Definitua: [pyproject.toml:79](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L79)
- Abiarazi: `uv run ccbt`

## Abiarazte Azkarra

### Abiarazi Deabrua {#start-daemon}

ccBitTorrent atzeko planoan exekutatu daiteke deabru moduan, edo lokalki saio bakarreko deskargetarako.

**Abiarazi deabrua (gomendatua hainbat torrent-etarako):**
```bash
# Abiarazi deabrua atzeko planoan
uv run btbt daemon start

# Abiarazi deabrua lehen planoan (arazketa egiteko)
uv run btbt daemon start --foreground

# Egiaztatu deabruaren egoera
uv run btbt daemon status
```

Deabrua atzeko planoan exekutatzen da eta torrent saio guztiak kudeatzen ditu. CLI komandoak automatikoki konektatzen dira deabruarekin exekutatzen ari denean.

**Exekutatu lokalki (deabru gabe):**
```bash
# Komandoak modu lokalean exekutatuko dira deabrua ez badago exekutatzen
uv run btbt download movie.torrent
```

### Abiarazi Bitonic (Gomendatua)

Hasi terminal panela:
```bash
uv run bitonic
```

Edo CLI bidez:
```bash
uv run ccbt dashboard
```

Berritze tasa pertsonalizatuarekin:
```bash
uv run ccbt dashboard --refresh 2.0
```

### Deskargatu Torrent bat {#download-torrent}

CLI erabiliz:
```bash
# Deskargatu torrent fitxategitik
uv run btbt download movie.torrent

# Deskargatu magnet estekatik
uv run btbt magnet "magnet:?xt=urn:btih:..."

# Abiadura mugak dituela
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512

# Berrekin kontrol puntutik
uv run btbt download movie.torrent --resume
```

Deskarga aukera guztietarako, ikusi [btbt CLI Erreferentzia](btbt-cli.md).

### Konfiguratu ccBitTorrent {#configure}

Sortu `ccbt.toml` fitxategi bat zure laneko direktorioan. Ikusi adibide konfigurazioa:
- Konfigurazio lehenetsia: [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Ingurune aldagaiak: [env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
- Konfigurazio sistema: [ccbt/config/config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)

!!! warning "Windows Bide Ebazpena"
    Windows-en, deabruarekin lotutako bideak (PID fitxategiak, egoera direktorioak) `ccbt/daemon/daemon_manager.py`-ko `_get_daemon_home_dir()` laguntzailea erabiltzen dute bide ebazpen koherenterako, bereziki erabiltzaile izenetan espazioak daudenean. Xehetasun gehiagorako, ikusi [Konfigurazio Gida - Windows Bide Ebazpena](configuration.md#daemon-home-dir).

Konfigurazio aukera xehatuetarako, ikusi [Konfigurazio Gida](configuration.md).

## Proiektu Txostenak

Ikusi proiektuaren kalitate metrikak eta txostenak:

- **Kode Estaldura**: [reports/coverage.md](reports/coverage.md) - Kode estaldura analisi osatua
- **Segurtasun Txostena**: [reports/bandit/index.md](reports/bandit/index.md) - Bandit-ek egindako segurtasun eskaneatze emaitzak
- **Errendimendu Neurgailuak**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - Errendimendu neurgailu emaitzak

Txosten hauek automatikoki sortzen eta eguneratzen dira gure integrazioa jarraitu prozesuaren zati gisa.

## Hurrengo Urratsak

- [Bitonic](bitonic.md) - Ikasi terminal panel interfazeaz
- [btbt CLI](btbt-cli.md) - Komando-lerroko interfaze erreferentzia osoa
- [Konfigurazioa](configuration.md) - Konfigurazio aukera xehatuak
- [Errendimendu Doikuntza](performance.md) - Optimizazio gida
- [API Erreferentzia](API.md) - Python API dokumentazioa, monitoreatze ezaugarriak barne

## Laguntza Lortu

- Erabili `uv run bitonic --help` edo `uv run btbt --help` komando laguntzarako
- Egiaztatu [btbt CLI Erreferentzia](btbt-cli.md) aukera xehatuetarako
- Bisitatu gure [GitHub biltegia](https://github.com/ccBittorrent/ccbt) arazoetarako eta eztabaidarako
