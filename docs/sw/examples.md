# Mifano

Sehemu hii hutoa mifano ya vitendo na sampuli za kodi za kutumia ccBitTorrent.

## Mifano ya Usanidi

### Usanidi wa Msingi

Faili ya usanidi ya chini kabisa ya kuanza:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

Angalia [example-config-basic.toml](examples/example-config-basic.toml) kwa usanidi kamili wa msingi.

### Usanidi wa Hali ya Juu

Kwa watumiaji wa hali ya juu ambao wanahitaji udhibiti wa kina:

Angalia [example-config-advanced.toml](examples/example-config-advanced.toml) kwa chaguzi za usanidi wa hali ya juu.

### Usanidi wa Utendakazi

Mipangilio iliyoongezwa kwa utendakazi wa juu zaidi:

Angalia [example-config-performance.toml](examples/example-config-performance.toml) kwa urekebishaji wa utendakazi.

### Usanidi wa Usalama

Usanidi unaolenga usalama na usimbaji na uthibitishaji:

Angalia [example-config-security.toml](examples/example-config-security.toml) kwa mipangilio ya usalama.

## Mifano ya BEP 52

### Kuunda Torrent v2

Unda faili ya torrent ya BitTorrent v2:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# Unda torrent v2
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # Vipande vya 16KB
)
```

Angalia [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) kwa mfano kamili.

### Kuunda Torrent ya Mseto

Unda torrent ya mseto ambayo inafanya kazi na wateja wa v1 na v2:

Angalia [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) kwa mfano kamili.

### Kuchambua Torrent v2

Chambua na ukagure faili ya torrent ya BitTorrent v2:

Angalia [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) kwa mfano kamili.

### Kikao cha Itifaki v2

Tumia itifaki ya BitTorrent v2 katika kikao:

Angalia [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) kwa mfano kamili.

## Kuanza

Kwa maelezo zaidi juu ya kuanza na ccBitTorrent, angalia [Mwongozo wa Kuanza](getting-started.md).






Sehemu hii hutoa mifano ya vitendo na sampuli za kodi za kutumia ccBitTorrent.

## Mifano ya Usanidi

### Usanidi wa Msingi

Faili ya usanidi ya chini kabisa ya kuanza:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

Angalia [example-config-basic.toml](examples/example-config-basic.toml) kwa usanidi kamili wa msingi.

### Usanidi wa Hali ya Juu

Kwa watumiaji wa hali ya juu ambao wanahitaji udhibiti wa kina:

Angalia [example-config-advanced.toml](examples/example-config-advanced.toml) kwa chaguzi za usanidi wa hali ya juu.

### Usanidi wa Utendakazi

Mipangilio iliyoongezwa kwa utendakazi wa juu zaidi:

Angalia [example-config-performance.toml](examples/example-config-performance.toml) kwa urekebishaji wa utendakazi.

### Usanidi wa Usalama

Usanidi unaolenga usalama na usimbaji na uthibitishaji:

Angalia [example-config-security.toml](examples/example-config-security.toml) kwa mipangilio ya usalama.

## Mifano ya BEP 52

### Kuunda Torrent v2

Unda faili ya torrent ya BitTorrent v2:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# Unda torrent v2
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # Vipande vya 16KB
)
```

Angalia [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) kwa mfano kamili.

### Kuunda Torrent ya Mseto

Unda torrent ya mseto ambayo inafanya kazi na wateja wa v1 na v2:

Angalia [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) kwa mfano kamili.

### Kuchambua Torrent v2

Chambua na ukagure faili ya torrent ya BitTorrent v2:

Angalia [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) kwa mfano kamili.

### Kikao cha Itifaki v2

Tumia itifaki ya BitTorrent v2 katika kikao:

Angalia [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) kwa mfano kamili.

## Kuanza

Kwa maelezo zaidi juu ya kuanza na ccBitTorrent, angalia [Mwongozo wa Kuanza](getting-started.md).




























































































































































































