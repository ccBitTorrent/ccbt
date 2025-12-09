# Ejemplos

Esta sección proporciona ejemplos prácticos y muestras de código para usar ccBitTorrent.

## Ejemplos de Configuración

### Configuración Básica

Un archivo de configuración mínimo para comenzar:

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

Consulta [example-config-basic.toml](examples/example-config-basic.toml) para una configuración básica completa.

### Configuración Avanzada

Para usuarios avanzados que necesitan control detallado:

Consulta [example-config-advanced.toml](examples/example-config-advanced.toml) para opciones de configuración avanzadas.

### Configuración de Rendimiento

Configuración optimizada para máximo rendimiento:

Consulta [example-config-performance.toml](examples/example-config-performance.toml) para ajuste de rendimiento.

### Configuración de Seguridad

Configuración centrada en seguridad con cifrado y validación:

Consulta [example-config-security.toml](examples/example-config-security.toml) para configuración de seguridad.

## Ejemplos BEP 52

### Crear un Torrent v2

Crear un archivo torrent BitTorrent v2:

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# Crear torrent v2
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # Piezas de 16KB
)
```

Consulta [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) para un ejemplo completo.

### Crear un Torrent Híbrido

Crear un torrent híbrido que funciona con clientes v1 y v2:

Consulta [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) para un ejemplo completo.

### Analizar un Torrent v2

Analizar e inspeccionar un archivo torrent BitTorrent v2:

Consulta [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) para un ejemplo completo.

### Sesión de Protocolo v2

Usar el protocolo BitTorrent v2 en una sesión:

Consulta [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) para un ejemplo completo.

## Comenzar

Para más información sobre cómo comenzar con ccBitTorrent, consulta la [Guía de Inicio](getting-started.md).


