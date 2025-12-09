# ccBitTorrent - BitTorrent Bezeroaren Errendimendu Handia

Python asyncio-rekin eraikitako BitTorrent bezero moderno eta errendimendu handikoa, pieza hautaketa algoritmo aurreratuak, metadatu trukaketa paraleloa eta disko I/O optimizatua dituena.

## Ezaugarriak

### Errendimendu Optimizazioak
- **Async I/O**: Asyncio inplementazio osoa konkurrentzia handiagorako. Ikusi [ccbt/session/async_main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/async_main.py)
- **Rarest-First Hautaketa**: Pieza hautaketa adimenduna enjambre osasun optimorako. Ikusi [ccbt/piece/async_piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py)
- **Endgame Modua**: Eskaera bikoiztuak osaketa azkarragoagatik
- **Eskaera Pipeline-a**: Eskaera ilara sakonak (16-64 eskaera pendiente peer bakoitzeko). Ikusi [ccbt/peer/async_peer_connection.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/async_peer_connection.py)
- **Tit-for-Tat Choking**: Banda-zabalera banaketa justua optimistic unchoke-arekin
- **Metadatu Paraleloak**: ut_metadata lortze konkurrentea hainbat peer-etatik. Ikusi [ccbt/piece/async_metadata_exchange.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_metadata_exchange.py)
- **Disko I/O Optimizazioa**: Fitxategi aurrez-eskuratzea, idazketa batch-etan, ring-buffer staging, memoria-mapped I/O, io_uring/I/O zuzena (konfiguragarria). Ikusi [ccbt/storage/disk_io.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/disk_io.py)
- **Hash Egiaztapen Pool-a**: SHA-1 egiaztapen paraleloa langile harieetan zehar

### Konfigurazio Aurreratua
- **TOML Konfigurazioa**: Konfigurazio sistema osatu hot-reload-ekin. Ikusi [ccbt/config/config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)
- **Torrent Bakoitzeko Ezarpenak**: Torrent bakoitzeko konfigurazio gainidazketak
- **Abiadura Mugatzea**: Igo/jaitsi muga globalak eta torrent bakoitzeko. Ikusi [ccbt.toml:38-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L38-L42)
- **Estrategia Hautaketa**: Pieza hautaketa round-robin, rarest-first edo sekuentziala. Ikusi [ccbt.toml:100-114](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L100-L114)
- **Streaming Modua**: Lehentasunetan oinarritutako pieza hautaketa multimedia fitxategientzat

### Sare Ezaugarriak
- **UDP Tracker Laguntza**: BEP 15 betetzen duen UDP tracker komunikazioa. Ikusi [ccbt/discovery/tracker_udp_client.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/tracker_udp_client.py)
- **DHT Hobetua**: Kademlia routing taula osoa bilaketa iteratiboekin. Ikusi [ccbt/discovery/dht.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/dht.py)
- **Peer Trukaketa (PEX)**: BEP 11 betetzen duen peer aurkikuntza. Ikusi [ccbt/discovery/pex.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/pex.py)
- **Konexio Kudeaketa**: Peer hautaketa adaptatiboa eta konexio mugak. Ikusi [ccbt/peer/connection_pool.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/connection_pool.py)
- **Protokolo Optimizazioak**: Memoria eraginkorreko mezu kudeaketa zero-kopia bideekin

## Xet Protokolo Hedapena (BEP XET)

Xet Protokolo Hedapena BitTorrent super-azkar eta eguneragarri bihurtzen duen peer-to-peer fitxategi sistema lankidetzarako optimizatua da. BEP XET ahalbidetzen du:

- **Eduki-definitutako Txunking**: Gearhash-etan oinarritutako fitxategi segmentazio adimenduna (8KB-128KB txunkak) eguneratze eraginkorrerako. Ikusi [ccbt/storage/xet_chunking.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py)
- **Torrent Arteko Deduplikazioa**: Txunk mailako deduplikazioa hainbat torrent artean. Ikusi [ccbt/storage/xet_deduplication.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py)
- **Peer-to-Peer CAS**: DHT eta tracker-ak erabiliz Eduki Helbideragarri Biltegi Deszentralizatua. Ikusi [ccbt/discovery/xet_cas.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/xet_cas.py)
- **Eguneratze Super-Azkarrak**: Aldatutako txunkak bakarrik behar dute berriz banatzea, fitxategi lankidetzarako trukaketa azkarra ahalbidetuz
- **P2P Fitxategi Sistema**: BitTorrent lankidetzarako optimizatutako eguneragarri peer-to-peer fitxategi sistema bihurtzen du
- **Merkle Zuhaitz Egiaztapena**: BLAKE3-256 hash-ak SHA-256 fallback-ekin osotasunerako. Ikusi [ccbt/storage/xet_hashing.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py)

[Gehiago ikasi BEP XET-i buruz →](bep_xet.md)

### Behatzea
- **Metrika Esportazioa**: Prometheus bateragarri metrikak monitorizaziorako. Ikusi [ccbt/monitoring/metrics_collector.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/monitoring/metrics_collector.py)
- **Egiturazko Erregistroa**: Konfiguragarri erregistroa peer bakoitzeko jarraipenarekin. Ikusi [ccbt/utils/logging_config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/logging_config.py)
- **Errendimendu Estatistikak**: Denbora errealean errendimendu, atzerapena eta ilara sakonera jarraipena
- **Osasun Monitorizazioa**: Konexio kalitatea eta peer fidagarritasun puntuazioa
- **Terminal Dashboard**: Textual-n oinarritutako dashboard bizia (Bitonic). Ikusi [ccbt/interface/terminal_dashboard.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py)
- **Alerta Kudeatzailea**: Arauetan oinarritutako alertak iraunkortasuna eta CLI bidezko probekin. Ikusi [ccbt/monitoring/alert_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/monitoring/alert_manager.py)

## Abiarazte Azkarra

### UV-rekin Instalazioa

Instalatu UV [astral.sh/uv](https://astral.sh/uv)-tik, gero instalatu ccBitTorrent.

Erreferentziak: [pyproject.toml:79-81](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L79-L81) sarrera puntuetarako

### Sarrera Puntu Nagusiak

**Bitonic** - Terminal dashboard interfaze nagusia (gomendatua):
- Sarrera puntua: [ccbt/interface/terminal_dashboard.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- Definitua: [pyproject.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L81)
- Abiarazi: `uv run bitonic` edo `uv run ccbt dashboard`

**btbt CLI** - Hobetutako komando-lerro interfazea:
- Sarrera puntua: [ccbt/cli/main.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1463)
- Definitua: [pyproject.toml:80](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L80)
- Abiarazi: `uv run btbt`

**ccbt** - Oinarrizko CLI interfazea:
- Sarrera puntua: [ccbt/__main__.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/__main__.py#L18)
- Definitua: [pyproject.toml:79](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L79)
- Abiarazi: `uv run ccbt`

Erabilera xehatuagorako, ikusi:
- [Abiarazte Gida](getting-started.md) - Urratsez urrats tutoriala
- [Bitonic](bitonic.md) - Terminal dashboard gida
- [btbt CLI](btbt-cli.md) - Komando erreferentziak osoa

## Dokumentazioa

- [BEP XET](bep_xet.md) - Xet Protokolo Hedapena eduki-definitutako txunking eta deduplikaziorako
- [Abiaraztea](getting-started.md) - Instalazioa eta lehen urratsak
- [Bitonic](bitonic.md) - Terminal dashboard (interfaze nagusia)
- [btbt CLI](btbt-cli.md) - Komando-lerro interfaze erreferentziak
- [Konfigurazioa](configuration.md) - Konfigurazio aukerak eta ezarpena
- [Errendimendu Doikuntza](performance.md) - Optimizazio gida
- [ccBT API kontsultatua](API.md) - Python API dokumentazioa
- [Ekarpena](contributing.md) - Nola ekarri
- [Finantzaketa](funding.md) - Proiektua lagundu

## Lizentzia

Proiektu hau **GNU General Public License v2 (GPL-2.0)** lizentziapean dago - ikusi [license.md](license.md) xehetasunetarako.

Gainera, proiektu hau **ccBT RAIL-AMS Lizentzia**-ren erabilera murrizketen mende dago - ikusi [ccBT-RAIL.md](ccBT-RAIL.md) termino eta murrizketa osoetarako.

**Garrantzitsua**: Bi lizentziak aplikatzen dira software honi. GPL-2.0 lizentzia eta RAIL lizentziako termino eta murrizketa guztiak bete behar dituzu.

## Txostenak

Ikusi proiektu txostenak dokumentazioan:
- [Estaldura Txostenak](reports/coverage.md) - Kode estaldura analisia
- [Bandit Segurtasun Txostena](reports/bandit/index.md) - Segurtasun eskaneatze emaitzak
- [Benchmark-ak](reports/benchmarks/index.md) - Errendimendu benchmark emaitzak

## Eskerrak

- BitTorrent protokolo espezifikazioa (BEP 5, 10, 11, 15, 52)
- Xet protokoloa eduki-definitutako txunking inspiraziorako
- Python asyncio errendimendu handiko I/O-rako
- BitTorrent komunitatea protokolo garapenerako
