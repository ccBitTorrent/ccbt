# Adibideak

Atal honek ccBitTorrent erabiltzeko adibide praktikoak eta kode laginak eskaintzen ditu.

## Konfigurazio Adibideak

### Konfigurazio Oinarrizkoa

Hasteko konfigurazio fitxategi minimoa:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

Konfigurazio oinarrizko osorako, ikusi [example-config-basic.toml](examples/example-config-basic.toml).

### Konfigurazio Aurreratua

Kontrol fina behar duten erabiltzaile aurreratuentzat:

Konfigurazio aukera aurreratuetarako, ikusi [example-config-advanced.toml](examples/example-config-advanced.toml).

### Errendimendu Konfigurazioa

Errendimendu maximorako optimizatutako ezarpenak:

Errendimendu doikuntzarako, ikusi [example-config-performance.toml](examples/example-config-performance.toml).

### Segurtasun Konfigurazioa

Enkriptazio eta baliozkotzearekin segurtasun zentratutako konfigurazioa:

Segurtasun ezarpenetarako, ikusi [example-config-security.toml](examples/example-config-security.toml).

## BEP 52 Adibideak

### v2 Torrent Sortu

Sortu BitTorrent v2 torrent fitxategia:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# Sortu v2 torrent
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # 16KB piezak
)
```

Adibide osorako, ikusi [create_v2_torrent.py](examples/bep52/create_v2_torrent.py).

### Hibrido Torrent Sortu

Sortu v1 eta v2 bezeroekin funtzionatzen duen hibrido torrent:

Adibide osorako, ikusi [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py).

### v2 Torrent Parseatu

Parseatu eta aztertu BitTorrent v2 torrent fitxategia:

Adibide osorako, ikusi [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py).

### Protokolo v2 Saioa

Erabili BitTorrent v2 protokoloa saio batean:

Adibide osorako, ikusi [protocol_v2_session.py](examples/bep52/protocol_v2_session.py).

## Hasi

ccBitTorrent-ekin hasteko informazio gehiagorako, ikusi [Hasi Gida](getting-started.md).


