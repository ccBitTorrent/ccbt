# BEP 52: Protocolo BitTorrent v2

## Resumen

BitTorrent Protocol v2 (BEP 52) es una actualización importante del protocolo BitTorrent que introduce hash SHA-256, estructura de metadatos mejorada y mejor soporte para archivos grandes. ccBitTorrent proporciona soporte completo para torrents solo v2, solo v1 y torrents híbridos que funcionan con ambos protocolos.

### Características Clave

- **Hash SHA-256**: Más seguro que SHA-1 usado en v1
- **Estructura Merkle Tree**: Validación eficiente de piezas y descargas parciales
- **Formato File Tree**: Organización jerárquica de archivos
- **Piece Layers**: Validación de piezas por archivo
- **Torrents Híbridos**: Compatibilidad hacia atrás con clientes v1

## Arquitectura

### Componentes Principales

#### 1. Metadatos del Torrent (`ccbt/core/torrent_v2.py`)

El analizador de torrent v2 maneja todas las operaciones de metadatos:

```python
from ccbt.core.torrent_v2 import TorrentV2Parser, TorrentV2Info

# Analizar torrent v2
parser = TorrentV2Parser()
with open("torrent_file.torrent", "rb") as f:
    torrent_data = decode(f.read())
    
v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

# Acceder a datos específicos de v2
print(f"Info Hash v2: {v2_info.info_hash_v2.hex()}")
print(f"File Tree: {v2_info.file_tree}")
print(f"Piece Layers: {len(v2_info.piece_layers)}")
```

#### 2. Comunicación del Protocolo (`ccbt/protocols/bittorrent_v2.py`)

Maneja handshakes y mensajes v2:

```python
from ccbt.protocols.bittorrent_v2 import (
    create_v2_handshake,
    send_v2_handshake,
    handle_v2_handshake,
    PieceLayerRequest,
    PieceLayerResponse,
)

# Crear handshake v2
info_hash_v2 = v2_info.info_hash_v2
peer_id = b"-CC0101-" + b"x" * 12
handshake = create_v2_handshake(info_hash_v2, peer_id)

# Enviar handshake
await send_v2_handshake(writer, info_hash_v2, peer_id)

# Recibir handshake
version, peer_id, parsed = await handle_v2_handshake(reader, writer)
```

#### 3. Hash SHA-256 (`ccbt/piece/hash_v2.py`)

Implementa funciones de hash v2:

```python
from ccbt.piece.hash_v2 import (
    hash_piece_v2,
    hash_piece_layer,
    hash_file_tree,
    verify_piece_v2,
)

# Hash de una pieza
piece_data = b"..." * 16384
piece_hash = hash_piece_v2(piece_data)

# Verificar pieza
is_valid = verify_piece_v2(piece_data, expected_hash)

# Construir Merkle tree
piece_hashes = [hash_piece_v2(p) for p in pieces]
merkle_root = hash_piece_layer(piece_hashes)
```

## Configuración

### Habilitar Protocolo v2

Configure el soporte del protocolo v2 en `ccbt.toml`:

```toml
[network.protocol_v2]
enable_protocol_v2 = true      # Habilitar soporte v2
prefer_protocol_v2 = false     # Preferir v2 sobre v1 cuando ambos estén disponibles
support_hybrid = true          # Soporte para torrents híbridos
v2_handshake_timeout = 30.0    # Tiempo de espera del handshake en segundos
```

### Variables de Entorno

```bash
export CCBT_PROTOCOL_V2_ENABLE=true
export CCBT_PROTOCOL_V2_PREFER=true
export CCBT_PROTOCOL_V2_SUPPORT_HYBRID=true
export CCBT_PROTOCOL_V2_HANDSHAKE_TIMEOUT=30.0
```

### Banderas CLI

```bash
# Habilitar protocolo v2
ccbt download file.torrent --protocol-v2

# Preferir v2 cuando esté disponible
ccbt download file.torrent --protocol-v2-prefer

# Deshabilitar protocolo v2
ccbt download file.torrent --no-protocol-v2
```

## Crear Torrents

### Torrents Solo V2

Cree torrents que solo funcionen con clientes v2:

```python
from pathlib import Path
from ccbt.core.torrent_v2 import TorrentV2Parser

parser = TorrentV2Parser()

# Crear desde un solo archivo
torrent_bytes = parser.generate_v2_torrent(
    source=Path("video.mp4"),
    output=Path("video.torrent"),
    trackers=["http://tracker.example.com/announce"],
    piece_length=262144,  # 256 KiB
    comment="My video file",
    private=False,
)

# Crear desde directorio
torrent_bytes = parser.generate_v2_torrent(
    source=Path("my_files/"),
    output=Path("my_files.torrent"),
    trackers=[
        "http://tracker1.example.com/announce",
        "http://tracker2.example.com/announce",
    ],
    piece_length=None,  # Auto-calcular
)
```

### Torrents Híbridos

Cree torrents compatibles con clientes v1 y v2:

```python
# Crear torrent híbrido
torrent_bytes = parser.generate_hybrid_torrent(
    source=Path("archive.zip"),
    output=Path("archive.torrent"),
    trackers=["http://tracker.example.com/announce"],
    piece_length=1048576,  # 1 MiB
    comment="Backwards compatible torrent",
    private=False,
)
```

### Creación de Torrent CLI

```bash
# Crear torrent v2
ccbt create-torrent file.mp4 --v2 \
    --output file.torrent \
    --tracker http://tracker.example.com/announce \
    --piece-length 262144 \
    --comment "My file"

# Crear torrent híbrido
ccbt create-torrent directory/ --hybrid \
    --output directory.torrent \
    --tracker http://tracker.example.com/announce \
    --private
```

## Detalles del Protocolo

### Formato de Handshake

#### Handshake V2 (80 bytes)
```
- 1 byte:  Longitud de la cadena del protocolo (19)
- 19 bytes: "BitTorrent protocol"
- 8 bytes:  Bytes reservados (bit 0 = 1 para soporte v2)
- 32 bytes: SHA-256 info_hash_v2
- 20 bytes: Peer ID
```

#### Handshake Híbrido (100 bytes)
```
- 1 byte:  Longitud de la cadena del protocolo (19)
- 19 bytes: "BitTorrent protocol"
- 8 bytes:  Bytes reservados (bit 0 = 1)
- 20 bytes: SHA-1 info_hash_v1
- 32 bytes: SHA-256 info_hash_v2
- 20 bytes: Peer ID
```

### Negociación de Versión del Protocolo

ccBitTorrent negocia automáticamente la mejor versión del protocolo:

```python
from ccbt.protocols.bittorrent_v2 import (
    ProtocolVersion,
    negotiate_protocol_version,
)

# Handshake del peer
peer_handshake = b"..."

# Nuestras versiones soportadas (en orden de prioridad)
supported = [
    ProtocolVersion.HYBRID,
    ProtocolVersion.V2,
    ProtocolVersion.V1,
]

# Negociar
negotiated = negotiate_protocol_version(peer_handshake, supported)

if negotiated == ProtocolVersion.V2:
    # Usar protocolo v2
    pass
elif negotiated == ProtocolVersion.HYBRID:
    # Usar modo híbrido
    pass
elif negotiated == ProtocolVersion.V1:
    # Recurrir a v1
    pass
else:
    # Incompatible
    pass
```

### Mensajes Específicos de V2

#### Solicitud de Piece Layer (ID de Mensaje 20)

Solicitar hashes de piezas para un archivo:

```python
from ccbt.protocols.bittorrent_v2 import PieceLayerRequest

pieces_root = b"..." # Hash raíz SHA-256 de 32 bytes
request = PieceLayerRequest(pieces_root)
message_bytes = request.serialize()
```

#### Respuesta de Piece Layer (ID de Mensaje 21)

Enviar hashes de piezas:

```python
from ccbt.protocols.bittorrent_v2 import PieceLayerResponse

piece_hashes = [b"..." * 32 for _ in range(10)]  # Lista de hashes SHA-256
response = PieceLayerResponse(pieces_root, piece_hashes)
message_bytes = response.serialize()
```

#### Solicitud de File Tree (ID de Mensaje 22)

Solicitar árbol de archivos completo:

```python
from ccbt.protocols.bittorrent_v2 import FileTreeRequest

request = FileTreeRequest()
message_bytes = request.serialize()
```

#### Respuesta de File Tree (ID de Mensaje 23)

Enviar estructura del árbol de archivos:

```python
from ccbt.protocols.bittorrent_v2 import FileTreeResponse

file_tree_bencoded = encode(file_tree_dict)
response = FileTreeResponse(file_tree_bencoded)
message_bytes = response.serialize()
```

## Estructura del File Tree

Los torrents v2 usan un árbol de archivos jerárquico:

```python
from ccbt.core.torrent_v2 import FileTreeNode

# Archivo único
file_node = FileTreeNode(
    name="video.mp4",
    length=1000000,
    pieces_root=b"..." * 32,
    children=None,
)

# Estructura de directorio
dir_node = FileTreeNode(
    name="my_files",
    length=0,
    pieces_root=None,
    children={
        "file1.txt": FileTreeNode(...),
        "file2.txt": FileTreeNode(...),
        "subdir": FileTreeNode(...),
    },
)

# Verificar tipo de nodo
if file_node.is_file():
    print(f"Archivo: {file_node.length} bytes")
if dir_node.is_directory():
    print(f"Directorio con {len(dir_node.children)} elementos")
```

## Piece Layers

Cada archivo tiene su propia capa de piezas con hashes SHA-256:

```python
from ccbt.core.torrent_v2 import PieceLayer

# Crear capa de piezas
layer = PieceLayer(
    piece_length=262144,  # 256 KiB
    pieces=[
        b"..." * 32,  # Hash de pieza 0
        b"..." * 32,  # Hash de pieza 1
        b"..." * 32,  # Hash de pieza 2
    ],
)

# Obtener hash de pieza
piece_0_hash = layer.get_piece_hash(0)

# Número de piezas
num_pieces = layer.num_pieces()
```

## Mejores Prácticas

### Cuándo Usar V2

- **Torrents nuevos**: Siempre preferir v2 para contenido nuevo
- **Archivos grandes**: V2 es más eficiente para archivos > 1 GB
- **Seguridad**: SHA-256 proporciona mejor resistencia a colisiones
- **Preparación para el futuro**: V2 es el futuro de BitTorrent

### Cuándo Usar Híbrido

- **Compatibilidad máxima**: Llegar a clientes v1 y v2
- **Período de transición**: Durante la migración del ecosistema
- **Torrents públicos**: Distribución más amplia

### Cuándo Usar Solo V1

- **Sistemas heredados**: Solo cuando el soporte v2 no esté disponible
- **Archivos pequeños**: La sobrecarga de V1 es aceptable para < 100 MB

### Selección de Longitud de Pieza

Se recomienda el auto-cálculo, pero valores manuales:

- **Archivos pequeños (< 16 MiB)**: 16 KiB
- **Archivos medianos (16 MiB - 512 MiB)**: 256 KiB
- **Archivos grandes (> 512 MiB)**: 1 MiB
- **Archivos muy grandes (> 10 GiB)**: 2-4 MiB

La longitud de pieza debe ser una potencia de 2.

## Referencia de API

### TorrentV2Parser

Clase principal para operaciones de torrent v2:

```python
class TorrentV2Parser:
    def parse_v2(self, info_dict: dict, torrent_data: dict) -> TorrentV2Info:
        """Analizar diccionario de información de torrent v2."""
        
    def parse_hybrid(self, info_dict: dict, torrent_data: dict) -> tuple[TorrentInfo, TorrentV2Info]:
        """Analizar torrent híbrido (devuelve información v1 y v2)."""
        
    def generate_v2_torrent(
        self,
        source: Path,
        output: Path | None = None,
        trackers: list[str] | None = None,
        web_seeds: list[str] | None = None,
        comment: str | None = None,
        created_by: str = "ccBitTorrent",
        piece_length: int | None = None,
        private: bool = False,
    ) -> bytes:
        """Generar archivo torrent solo v2."""
        
    def generate_hybrid_torrent(
        self,
        source: Path,
        output: Path | None = None,
        trackers: list[str] | None = None,
        web_seeds: list[str] | None = None,
        comment: str | None = None,
        created_by: str = "ccBitTorrent",
        piece_length: int | None = None,
        private: bool = False,
    ) -> bytes:
        """Generar archivo torrent híbrido."""
```

### TorrentV2Info

Modelo de datos para información de torrent v2:

```python
@dataclass
class TorrentV2Info:
    name: str
    info_hash_v2: bytes  # SHA-256 de 32 bytes
    info_hash_v1: bytes | None  # SHA-1 de 20 bytes (solo híbrido)
    announce: str
    announce_list: list[list[str]] | None
    comment: str | None
    created_by: str | None
    creation_date: int | None
    encoding: str | None
    is_private: bool
    file_tree: dict[str, FileTreeNode]
    piece_layers: dict[bytes, PieceLayer]
    piece_length: int
    files: list[FileInfo]
    total_length: int
    num_pieces: int
    
    def get_file_paths(self) -> list[str]:
        """Obtener lista de todas las rutas de archivos."""
        
    def get_piece_layer(self, pieces_root: bytes) -> PieceLayer | None:
        """Obtener capa de piezas para un archivo."""
```

### Funciones del Protocolo

```python
# Handshake
def create_v2_handshake(info_hash_v2: bytes, peer_id: bytes) -> bytes
def create_hybrid_handshake(info_hash_v1: bytes, info_hash_v2: bytes, peer_id: bytes) -> bytes
def detect_protocol_version(handshake: bytes) -> ProtocolVersion
def parse_v2_handshake(data: bytes) -> dict
def negotiate_protocol_version(handshake: bytes, supported: list[ProtocolVersion]) -> ProtocolVersion | None

# I/O Asíncrono
async def send_v2_handshake(writer: StreamWriter, info_hash_v2: bytes, peer_id: bytes) -> None
async def send_hybrid_handshake(writer: StreamWriter, info_hash_v1: bytes, info_hash_v2: bytes, peer_id: bytes) -> None
async def handle_v2_handshake(reader: StreamReader, writer: StreamWriter, our_info_hash_v2: bytes | None = None, our_info_hash_v1: bytes | None = None, timeout: float = 30.0) -> tuple[ProtocolVersion, bytes, dict]
async def upgrade_to_v2(connection: Any, info_hash_v2: bytes) -> bool
```

### Funciones de Hash

```python
# Hash de piezas
def hash_piece_v2(data: bytes) -> bytes
def hash_piece_v2_streaming(data_source: bytes | IO) -> bytes
def verify_piece_v2(data: bytes, expected_hash: bytes) -> bool

# Merkle trees
def hash_piece_layer(piece_hashes: list[bytes]) -> bytes
def verify_piece_layer(piece_hashes: list[bytes], expected_root: bytes) -> bool

# File trees
def hash_file_tree(file_tree: dict[str, FileTreeNode]) -> bytes
```

## Ejemplos

Consulte [docs/examples/bep52/](examples/bep52/) para ejemplos completos de trabajo:

- `create_v2_torrent.py`: Crear torrent v2 desde archivo
- `create_hybrid_torrent.py`: Crear torrent híbrido
- `parse_v2_torrent.py`: Analizar y mostrar información de torrent v2
- `protocol_v2_session.py`: Iniciar sesión con soporte v2

## Solución de Problemas

### Problemas Comunes

**Problema**: El handshake v2 falla con "Info hash v2 mismatch"
- **Solución**: Verificar que info_hash_v2 se calcule correctamente (SHA-256 del diccionario info bencoded)

**Problema**: La validación de la capa de piezas falla
- **Solución**: Asegurar que piece_length coincida entre torrent y validación

**Problema**: Errores de análisis del árbol de archivos
- **Solución**: Verificar que la estructura del árbol de archivos siga el formato BEP 52 (anidamiento adecuado, longitud de pieces_root)

**Problema**: La negociación de versión del protocolo devuelve None
- **Solución**: El peer puede no soportar v2. Verificar bytes reservados en el handshake.

### Registro de Depuración

Habilitar registro de depuración para el protocolo v2:

```python
import logging
logging.getLogger("ccbt.core.torrent_v2").setLevel(logging.DEBUG)
logging.getLogger("ccbt.protocols.bittorrent_v2").setLevel(logging.DEBUG)
logging.getLogger("ccbt.piece.hash_v2").setLevel(logging.DEBUG)
```

## Consideraciones de Rendimiento

### Uso de Memoria

- Los torrents V2 usan más memoria para las capas de piezas (32 bytes vs 20 bytes por pieza)
- La estructura del árbol de archivos añade sobrecarga para torrents multiarchivo
- Los torrents híbridos almacenan metadatos v1 y v2

### Uso de CPU

- SHA-256 es ~2x más lento que SHA-1 para hash
- La construcción del Merkle tree añade sobrecarga computacional
- Usar longitud de pieza >= 256 KiB para archivos grandes para reducir el uso de CPU

### Red

- Los handshakes V2 son 12 bytes más grandes (80 vs 68 bytes)
- Los handshakes híbridos son 32 bytes más grandes (100 vs 68 bytes)
- El intercambio de capas de piezas añade sobrecarga inicial pero permite reanudación eficiente

## Cumplimiento de Estándares

La implementación de BEP 52 de ccBitTorrent sigue la especificación oficial:

- **BEP 52**: [BitTorrent Protocol v2](https://www.bittorrent.org/beps/bep_0052.html)
- **Suite de Pruebas**: Más de 2500 líneas de pruebas exhaustivas
- **Compatibilidad**: Interoperable con libtorrent, qBittorrent, Transmission

## Ver También

- [Documentación de API](API.md)
- [Guía de Configuración](configuration.md)
- [Resumen de Arquitectura](architecture.md)
- [Índice BEP](https://www.bittorrent.org/beps/bep_0000.html)

