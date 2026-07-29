# Àwọn Àpẹrẹ

Apá yìí pèsè àwọn àpẹrẹ tí ó ṣe dáadáa àti àwọn àpẹrẹ kódù fún lílo ccBitTorrent.

## Àwọn Àpẹrẹ Ṣètò

### Ṣètò Àkọ́kọ́

Fàìlì ṣètò tí ó kéré jùlọ láti bẹ̀rẹ̀:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

Wo [example-config-basic.toml](examples/example-config-basic.toml) fún ṣètò àkọ́kọ́ tí ó ṣe dáadáa.

### Ṣètò Tó Ga

Fún àwọn onílò tó ga tí wọ́n nilo ìṣàkóso tí ó ṣe dáadáa:

Wo [example-config-advanced.toml](examples/example-config-advanced.toml) fún àwọn àṣàyàn ṣètò tó ga.

### Ṣètò Iṣẹ́

Àwọn ṣètò tí a ṣe ìtúnṣe fún iṣẹ́ tó pọ̀ jùlọ:

Wo [example-config-performance.toml](examples/example-config-performance.toml) fún ìtúnṣe iṣẹ́.

### Ṣètò Ààbò

Ṣètò tí ó ṣe dáadáa fún ààbò pẹ̀lú ìpamọ́ àti ìjẹ́rìí:

Wo [example-config-security.toml](examples/example-config-security.toml) fún àwọn ṣètò ààbò.

## Àwọn Àpẹrẹ BEP 52

### Ṣíṣẹ̀dá Torrent v2

Ṣẹ̀dá fàìlì torrent BitTorrent v2:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# Ṣẹ̀dá torrent v2
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # Àwọn apá 16KB
)
```

Wo [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) fún àpẹrẹ tí ó ṣe dáadáa.

### Ṣíṣẹ̀dá Torrent Àdàpọ̀

Ṣẹ̀dá torrent àdàpọ̀ tí ó ṣiṣẹ́ pẹ̀lú àwọn oníbára v1 àti v2:

Wo [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) fún àpẹrẹ tí ó ṣe dáadáa.

### Ṣàlàyé Torrent v2

Ṣàlàyé àti ṣayẹ̀wò fàìlì torrent BitTorrent v2:

Wo [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) fún àpẹrẹ tí ó ṣe dáadáa.

### Ìgbàkọlé Ìlànà v2

Lo ìlànà BitTorrent v2 ní ìgbàkọlé:

Wo [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) fún àpẹrẹ tí ó ṣe dáadáa.

## Bíbẹ̀rẹ̀

Fún ìmọ̀ sí i nípa bíbẹ̀rẹ̀ pẹ̀lú ccBitTorrent, wo [Ìtọ́sọ́nà Bíbẹ̀rẹ̀](getting-started.md).






Apá yìí pèsè àwọn àpẹrẹ tí ó ṣe dáadáa àti àwọn àpẹrẹ kódù fún lílo ccBitTorrent.

## Àwọn Àpẹrẹ Ṣètò

### Ṣètò Àkọ́kọ́

Fàìlì ṣètò tí ó kéré jùlọ láti bẹ̀rẹ̀:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

Wo [example-config-basic.toml](examples/example-config-basic.toml) fún ṣètò àkọ́kọ́ tí ó ṣe dáadáa.

### Ṣètò Tó Ga

Fún àwọn onílò tó ga tí wọ́n nilo ìṣàkóso tí ó ṣe dáadáa:

Wo [example-config-advanced.toml](examples/example-config-advanced.toml) fún àwọn àṣàyàn ṣètò tó ga.

### Ṣètò Iṣẹ́

Àwọn ṣètò tí a ṣe ìtúnṣe fún iṣẹ́ tó pọ̀ jùlọ:

Wo [example-config-performance.toml](examples/example-config-performance.toml) fún ìtúnṣe iṣẹ́.

### Ṣètò Ààbò

Ṣètò tí ó ṣe dáadáa fún ààbò pẹ̀lú ìpamọ́ àti ìjẹ́rìí:

Wo [example-config-security.toml](examples/example-config-security.toml) fún àwọn ṣètò ààbò.

## Àwọn Àpẹrẹ BEP 52

### Ṣíṣẹ̀dá Torrent v2

Ṣẹ̀dá fàìlì torrent BitTorrent v2:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# Ṣẹ̀dá torrent v2
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # Àwọn apá 16KB
)
```

Wo [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) fún àpẹrẹ tí ó ṣe dáadáa.

### Ṣíṣẹ̀dá Torrent Àdàpọ̀

Ṣẹ̀dá torrent àdàpọ̀ tí ó ṣiṣẹ́ pẹ̀lú àwọn oníbára v1 àti v2:

Wo [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) fún àpẹrẹ tí ó ṣe dáadáa.

### Ṣàlàyé Torrent v2

Ṣàlàyé àti ṣayẹ̀wò fàìlì torrent BitTorrent v2:

Wo [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) fún àpẹrẹ tí ó ṣe dáadáa.

### Ìgbàkọlé Ìlànà v2

Lo ìlànà BitTorrent v2 ní ìgbàkọlé:

Wo [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) fún àpẹrẹ tí ó ṣe dáadáa.

## Bíbẹ̀rẹ̀

Fún ìmọ̀ sí i nípa bíbẹ̀rẹ̀ pẹ̀lú ccBitTorrent, wo [Ìtọ́sọ́nà Bíbẹ̀rẹ̀](getting-started.md).




























































































































































































