# ܡܬܠܐ

ܗܢܐ ܦܠܓܐ ܡܦܠܚ ܠܡܬܠܐ ܕܡܫܬܡܫܢܐ ܘܢܡܘܢܐ ܕܟܘܕܐ ܠܡܫܬܡܫܢܘܬܐ ܕ ccBitTorrent.

## ܡܬܠܐ ܕܬܟܢܝܬܐ

### ܬܟܢܝܬܐ ܕܒܣܝܣܝܬܐ

ܦܝܠܐ ܕܬܟܢܝܬܐ ܕܙܥܘܪܐ ܠܫܘܪܝܐ:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

ܚܙܝ ܠ [example-config-basic.toml](examples/example-config-basic.toml) ܠܬܟܢܝܬܐ ܕܒܣܝܣܝܬܐ ܡܫܠܡܬܐ.

### ܬܟܢܝܬܐ ܕܪܡܐ

ܠܡܫܬܡܫܢܐ ܕܪܡܐ ܕܡܬܒܥܝܢ ܠܫܘܠܛܢܐ ܕܕܩܝܩ:

ܚܙܝ ܠ [example-config-advanced.toml](examples/example-config-advanced.toml) ܠܓܒܝܬܐ ܕܬܟܢܝܬܐ ܕܪܡܐ.

### ܬܟܢܝܬܐ ܕܬܘܩܦܐ

ܬܟܢܝܬܐ ܕܡܬܬܟܝܢܐ ܠܬܘܩܦܐ ܪܒܐ ܝܬܝܪ:

ܚܙܝ ܠ [example-config-performance.toml](examples/example-config-performance.toml) ܠܬܟܢܝܬܐ ܕܬܘܩܦܐ.

### ܬܟܢܝܬܐ ܕܐܡܢܘܬܐ

ܬܟܢܝܬܐ ܕܡܬܟܝܢܐ ܠܐܡܢܘܬܐ ܥܡ ܐܢܩܪܝܦܬܐ ܘܒܨܘܪܬܐ:

ܚܙܝ ܠ [example-config-security.toml](examples/example-config-security.toml) ܠܬܟܢܝܬܐ ܕܐܡܢܘܬܐ.

## ܡܬܠܐ ܕ BEP 52

### ܒܪܝܬܐ ܕܛܘܪܢܛ v2

ܒܪܝ ܦܝܠܐ ܕܛܘܪܢܛ ܒܝܛܛܘܪܢܛ v2:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# ܒܪܝ ܛܘܪܢܛ v2
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # ܦܝܣܐ ܕ 16KB
)
```

ܚܙܝ ܠ [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) ܠܡܬܠ ܡܫܠܡ.

### ܒܪܝܬܐ ܕܛܘܪܢܛ ܕܚܠܝܛ

ܒܪܝ ܛܘܪܢܛ ܕܚܠܝܛ ܕܦܠܚ ܥܡ ܟܠܝܢܛܣ v1 ܘ v2:

ܚܙܝ ܠ [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) ܠܡܬܠ ܡܫܠܡ.

### ܦܘܪܫܐ ܕܛܘܪܢܛ v2

ܦܘܪܫ ܘܒܨܝ ܠܦܝܠܐ ܕܛܘܪܢܛ ܒܝܛܛܘܪܢܛ v2:

ܚܙܝ ܠ [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) ܠܡܬܠ ܡܫܠܡ.

### ܓܠܣܐ ܕܦܪܘܛܘܟܘܠ v2

ܡܫܬܡܫ ܒܦܪܘܛܘܟܘܠ ܒܝܛܛܘܪܢܛ v2 ܒܓܠܣܐ:

ܚܙܝ ܠ [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) ܠܡܬܠ ܡܫܠܡ.

## ܫܘܪܝܐ

ܠܝܕܥܬܐ ܝܬܝܪܐ ܥܠ ܫܘܪܝܐ ܥܡ ccBitTorrent، ܚܙܝ ܠ [ܡܕܒܪܢܘܬܐ ܕܫܘܪܝܐ](getting-started.md).






ܗܢܐ ܦܠܓܐ ܡܦܠܚ ܠܡܬܠܐ ܕܡܫܬܡܫܢܐ ܘܢܡܘܢܐ ܕܟܘܕܐ ܠܡܫܬܡܫܢܘܬܐ ܕ ccBitTorrent.

## ܡܬܠܐ ܕܬܟܢܝܬܐ

### ܬܟܢܝܬܐ ܕܒܣܝܣܝܬܐ

ܦܝܠܐ ܕܬܟܢܝܬܐ ܕܙܥܘܪܐ ܠܫܘܪܝܐ:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

ܚܙܝ ܠ [example-config-basic.toml](examples/example-config-basic.toml) ܠܬܟܢܝܬܐ ܕܒܣܝܣܝܬܐ ܡܫܠܡܬܐ.

### ܬܟܢܝܬܐ ܕܪܡܐ

ܠܡܫܬܡܫܢܐ ܕܪܡܐ ܕܡܬܒܥܝܢ ܠܫܘܠܛܢܐ ܕܕܩܝܩ:

ܚܙܝ ܠ [example-config-advanced.toml](examples/example-config-advanced.toml) ܠܓܒܝܬܐ ܕܬܟܢܝܬܐ ܕܪܡܐ.

### ܬܟܢܝܬܐ ܕܬܘܩܦܐ

ܬܟܢܝܬܐ ܕܡܬܬܟܝܢܐ ܠܬܘܩܦܐ ܪܒܐ ܝܬܝܪ:

ܚܙܝ ܠ [example-config-performance.toml](examples/example-config-performance.toml) ܠܬܟܢܝܬܐ ܕܬܘܩܦܐ.

### ܬܟܢܝܬܐ ܕܐܡܢܘܬܐ

ܬܟܢܝܬܐ ܕܡܬܟܝܢܐ ܠܐܡܢܘܬܐ ܥܡ ܐܢܩܪܝܦܬܐ ܘܒܨܘܪܬܐ:

ܚܙܝ ܠ [example-config-security.toml](examples/example-config-security.toml) ܠܬܟܢܝܬܐ ܕܐܡܢܘܬܐ.

## ܡܬܠܐ ܕ BEP 52

### ܒܪܝܬܐ ܕܛܘܪܢܛ v2

ܒܪܝ ܦܝܠܐ ܕܛܘܪܢܛ ܒܝܛܛܘܪܢܛ v2:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# ܒܪܝ ܛܘܪܢܛ v2
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # ܦܝܣܐ ܕ 16KB
)
```

ܚܙܝ ܠ [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) ܠܡܬܠ ܡܫܠܡ.

### ܒܪܝܬܐ ܕܛܘܪܢܛ ܕܚܠܝܛ

ܒܪܝ ܛܘܪܢܛ ܕܚܠܝܛ ܕܦܠܚ ܥܡ ܟܠܝܢܛܣ v1 ܘ v2:

ܚܙܝ ܠ [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) ܠܡܬܠ ܡܫܠܡ.

### ܦܘܪܫܐ ܕܛܘܪܢܛ v2

ܦܘܪܫ ܘܒܨܝ ܠܦܝܠܐ ܕܛܘܪܢܛ ܒܝܛܛܘܪܢܛ v2:

ܚܙܝ ܠ [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) ܠܡܬܠ ܡܫܠܡ.

### ܓܠܣܐ ܕܦܪܘܛܘܟܘܠ v2

ܡܫܬܡܫ ܒܦܪܘܛܘܟܘܠ ܒܝܛܛܘܪܢܛ v2 ܒܓܠܣܐ:

ܚܙܝ ܠ [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) ܠܡܬܠ ܡܫܠܡ.

## ܫܘܪܝܐ

ܠܝܕܥܬܐ ܝܬܝܪܐ ܥܠ ܫܘܪܝܐ ܥܡ ccBitTorrent، ܚܙܝ ܠ [ܡܕܒܪܢܘܬܐ ܕܫܘܪܝܐ](getting-started.md).
































































































































































































