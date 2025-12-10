# Misalai

Wannan sashe yana ba da misalai masu amfani da samfuran kode don amfani da ccBitTorrent.

## Misalan Saitin

### Saitin Asali

Fayil ɗin saitin mafi ƙanƙanta don farawa:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

Duba [example-config-basic.toml](examples/example-config-basic.toml) don cikakken saitin asali.

### Saitin Ci Gaba

Ga masu amfani masu ci gaba waɗanda ke buƙatar sarrafawa mai zurfi:

Duba [example-config-advanced.toml](examples/example-config-advanced.toml) don zaɓuɓɓukan saitin ci gaba.

### Saitin Aiki

Saitunan da aka inganta don aiki mafi girma:

Duba [example-config-performance.toml](examples/example-config-performance.toml) don gyara aiki.

### Saitin Tsaro

Saitin mai da hankali kan tsaro tare da rufe sirri da tabbatarwa:

Duba [example-config-security.toml](examples/example-config-security.toml) don saitunan tsaro.

## Misalan BEP 52

### Ƙirƙiri Torrent v2

Ƙirƙiri fayil ɗin torrent BitTorrent v2:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# Ƙirƙiri torrent v2
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # Guntu 16KB
)
```

Duba [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) don misali mai cikakke.

### Ƙirƙiri Torrent Hybrid

Ƙirƙiri torrent hybrid wanda ke aiki tare da abokan ciniki na v1 da v2:

Duba [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) don misali mai cikakke.

### Fassara Torrent v2

Fassara da bincika fayil ɗin torrent BitTorrent v2:

Duba [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) don misali mai cikakke.

### Taron Ka'idar v2

Yi amfani da ka'idar BitTorrent v2 a cikin taron:

Duba [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) don misali mai cikakke.

## Fara Aiki

Don ƙarin bayani game da fara aiki tare da ccBitTorrent, duba [Jagorar Fara Aiki](getting-started.md).






Wannan sashe yana ba da misalai masu amfani da samfuran kode don amfani da ccBitTorrent.

## Misalan Saitin

### Saitin Asali

Fayil ɗin saitin mafi ƙanƙanta don farawa:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

Duba [example-config-basic.toml](examples/example-config-basic.toml) don cikakken saitin asali.

### Saitin Ci Gaba

Ga masu amfani masu ci gaba waɗanda ke buƙatar sarrafawa mai zurfi:

Duba [example-config-advanced.toml](examples/example-config-advanced.toml) don zaɓuɓɓukan saitin ci gaba.

### Saitin Aiki

Saitunan da aka inganta don aiki mafi girma:

Duba [example-config-performance.toml](examples/example-config-performance.toml) don gyara aiki.

### Saitin Tsaro

Saitin mai da hankali kan tsaro tare da rufe sirri da tabbatarwa:

Duba [example-config-security.toml](examples/example-config-security.toml) don saitunan tsaro.

## Misalan BEP 52

### Ƙirƙiri Torrent v2

Ƙirƙiri fayil ɗin torrent BitTorrent v2:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# Ƙirƙiri torrent v2
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # Guntu 16KB
)
```

Duba [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) don misali mai cikakke.

### Ƙirƙiri Torrent Hybrid

Ƙirƙiri torrent hybrid wanda ke aiki tare da abokan ciniki na v1 da v2:

Duba [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) don misali mai cikakke.

### Fassara Torrent v2

Fassara da bincika fayil ɗin torrent BitTorrent v2:

Duba [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) don misali mai cikakke.

### Taron Ka'idar v2

Yi amfani da ka'idar BitTorrent v2 a cikin taron:

Duba [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) don misali mai cikakke.

## Fara Aiki

Don ƙarin bayani game da fara aiki tare da ccBitTorrent, duba [Jagorar Fara Aiki](getting-started.md).




























































































































































































