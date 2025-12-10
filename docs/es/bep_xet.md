# BEP XET: Extensión del Protocolo Xet para Chunking Definido por Contenido y Deduplicación

## Resumen

La Extensión del Protocolo Xet (BEP XET) es una extensión del protocolo BitTorrent que habilita el chunking definido por contenido (CDC) y la deduplicación entre torrents a través de un sistema de almacenamiento direccionable por contenido (CAS) peer-to-peer. Esta extensión transforma BitTorrent en un sistema de archivos peer-to-peer super rápido y actualizable optimizado para colaboración y compartición eficiente de datos.

## Justificación

La extensión del protocolo Xet aborda limitaciones clave de BitTorrent tradicional:

1. **Tamaños de Pieza Fijos**: BitTorrent tradicional usa tamaños de pieza fijos, lo que lleva a redistribución ineficiente cuando se modifican archivos. CDC se adapta a los límites del contenido.

2. **Sin Deduplicación Entre Torrents**: Cada torrent es independiente, incluso si comparte contenido idéntico. Xet habilita deduplicación a nivel de chunk entre torrents.

3. **Almacenamiento Centralizado**: Los sistemas CAS tradicionales requieren servicios externos. Xet construye CAS directamente en la red BitTorrent usando DHT y trackers.

4. **Actualizaciones Ineficientes**: Actualizar un archivo compartido requiere redistribuir todo el archivo. Xet solo redistribuye chunks modificados.

Al combinar CDC, deduplicación y CAS P2P, Xet transforma BitTorrent en un sistema de archivos peer-to-peer super rápido y actualizable optimizado para colaboración.

### Características Clave

- **Chunking Definido por Contenido (CDC)**: Segmentación inteligente de archivos basada en Gearhash (chunks de 8KB-128KB)
- **Deduplicación Entre Torrents**: Deduplicación a nivel de chunk entre múltiples torrents
- **CAS Peer-to-Peer**: Almacenamiento Direccionable por Contenido descentralizado usando DHT y trackers
- **Verificación Merkle Tree**: Hash BLAKE3-256 con fallback SHA-256 para integridad
- **Formato Xorb**: Formato de almacenamiento eficiente para agrupar múltiples chunks
- **Formato Shard**: Almacenamiento de metadatos para información de archivos y datos CAS
- **Compresión LZ4**: Compresión opcional para datos Xorb

## Casos de Uso

### 1. Compartición Colaborativa de Archivos

Xet habilita colaboración eficiente mediante:
- **Deduplicación**: Archivos compartidos entre múltiples torrents comparten los mismos chunks
- **Actualizaciones Rápidas**: Solo los chunks modificados necesitan ser redistribuidos
- **Control de Versiones**: Rastrear versiones de archivos a través de raíces de Merkle tree

### 2. Distribución de Archivos Grandes

Para archivos grandes o conjuntos de datos:
- **Chunking Definido por Contenido**: Límites inteligentes reducen la redistribución de chunks en ediciones
- **Descargas Paralelas**: Descargar chunks de múltiples pares simultáneamente
- **Capacidad de Reanudación**: Rastrear chunks individuales para reanudación confiable

### 3. Sistema de Archivos Peer-to-Peer

Transformar BitTorrent en un sistema de archivos P2P:
- **Integración CAS**: Chunks almacenados en DHT para disponibilidad global
- **Almacenamiento de Metadatos**: Shards proporcionan metadatos del sistema de archivos
- **Búsquedas Rápidas**: Acceso directo a chunks vía hash elimina la necesidad de descargar el torrent completo

## Estado de Implementación

La extensión del protocolo Xet está completamente implementada en ccBitTorrent:

- ✅ Chunking Definido por Contenido (Gearhash CDC)
- ✅ Hash BLAKE3-256 con fallback SHA-256
- ✅ Caché de deduplicación SQLite
- ✅ Integración DHT (BEP 44)
- ✅ Integración de trackers
- ✅ Formatos Xorb y Shard
- ✅ Cálculo de Merkle tree
- ✅ Extensión del protocolo BitTorrent (BEP 10)
- ✅ Integración CLI
- ✅ Gestión de configuración

## Configuración

### Comandos CLI

```bash
# Habilitar protocolo Xet
ccbt xet enable

# Mostrar estado de Xet
ccbt xet status

# Mostrar estadísticas de deduplicación
ccbt xet stats

# Limpiar chunks no utilizados
ccbt xet cleanup --max-age-days 30
```

### Habilitar Protocolo Xet

Configure el soporte Xet en `ccbt.toml`:

```toml
[disk]
# Configuración del Protocolo Xet
xet_enabled = false                        # Habilitar protocolo Xet
xet_chunk_min_size = 8192                  # Tamaño mínimo de chunk (bytes)
xet_chunk_max_size = 131072                # Tamaño máximo de chunk (bytes)
xet_chunk_target_size = 16384              # Tamaño objetivo de chunk (bytes)
xet_deduplication_enabled = true           # Habilitar deduplicación a nivel de chunk
xet_cache_db_path = "data/xet_cache.db"    # Ruta de base de datos de caché SQLite
xet_chunk_store_path = "data/xet_chunks"   # Directorio de almacenamiento de chunks
xet_use_p2p_cas = true                     # Usar Almacenamiento Direccionable por Contenido P2P
xet_compression_enabled = true             # Habilitar compresión LZ4 para datos Xorb
```


## Especificación del Protocolo

### Negociación de Extensión

La extensión XET sigue BEP 10 (Extension Protocol) para la negociación. Durante el handshake extendido, los pares intercambian capacidades de extensión:

- **Nombre de Extensión**: `ut_xet`
- **ID de Extensión**: Asignado dinámicamente durante el handshake (1-255)
- **Capacidades Requeridas**: Ninguna (la extensión es opcional)

Los pares que soportan XET incluyen `ut_xet` en su handshake de extensión. El ID de extensión se almacena por sesión de par para el enrutamiento de mensajes.

### Tipos de Mensaje

La extensión XET define los siguientes tipos de mensaje:

#### Mensajes de Chunk

1. **CHUNK_REQUEST (0x01)**: Solicitar un chunk específico por hash
2. **CHUNK_RESPONSE (0x02)**: Respuesta que contiene datos del chunk
3. **CHUNK_NOT_FOUND (0x03)**: El par no tiene el chunk solicitado
4. **CHUNK_ERROR (0x04)**: Error ocurrido al recuperar el chunk

#### Mensajes de Sincronización de Carpetas

5. **FOLDER_VERSION_REQUEST (0x10)**: Solicitar versión de carpeta (referencia de commit git)
6. **FOLDER_VERSION_RESPONSE (0x11)**: Respuesta con versión de carpeta
7. **FOLDER_UPDATE_NOTIFY (0x12)**: Notificar al par de actualización de carpeta
8. **FOLDER_SYNC_MODE_REQUEST (0x13)**: Solicitar modo de sincronización
9. **FOLDER_SYNC_MODE_RESPONSE (0x14)**: Respuesta con modo de sincronización

#### Mensajes de Intercambio de Metadatos

10. **FOLDER_METADATA_REQUEST (0x20)**: Solicitar metadatos de carpeta (archivo .tonic)
11. **FOLDER_METADATA_RESPONSE (0x21)**: Respuesta con pieza de metadatos de carpeta
12. **FOLDER_METADATA_NOT_FOUND (0x22)**: Metadatos no disponibles

#### Mensajes de Filtro Bloom

13. **BLOOM_FILTER_REQUEST (0x30)**: Solicitar filtro bloom del par para disponibilidad de chunks
14. **BLOOM_FILTER_RESPONSE (0x31)**: Respuesta con datos del filtro bloom

### Formato de Mensaje

#### CHUNK_REQUEST

```
Offset  Tamaño  Descripción
0       32      Hash del chunk (BLAKE3-256 o SHA-256)
```

#### CHUNK_RESPONSE

```
Offset  Tamaño  Descripción
0       32      Hash del chunk
32      4       Longitud de datos del chunk (big-endian)
36      N       Datos del chunk
```

#### CHUNK_NOT_FOUND

```
Offset  Tamaño  Descripción
0       32      Hash del chunk
```

#### CHUNK_ERROR

```
Offset  Tamaño  Descripción
0       32      Hash del chunk
32      4       Código de error (big-endian)
36      N       Mensaje de error (UTF-8)
```

#### FOLDER_VERSION_REQUEST

```
Offset  Tamaño  Descripción
0       N       Identificador de carpeta (UTF-8, terminado en null)
```

#### FOLDER_VERSION_RESPONSE

```
Offset  Tamaño  Descripción
0       N       Identificador de carpeta (UTF-8, terminado en null)
N       40      Referencia de commit git (SHA-1, 20 bytes) o (SHA-256, 32 bytes)
```

#### FOLDER_UPDATE_NOTIFY

```
Offset  Tamaño  Descripción
0       N       Identificador de carpeta (UTF-8, terminado en null)
N       40      Nueva referencia de commit git
N+40    8       Timestamp (big-endian, época Unix)
```

#### FOLDER_SYNC_MODE_REQUEST

```
Offset  Tamaño  Descripción
0       N       Identificador de carpeta (UTF-8, terminado en null)
```

#### FOLDER_SYNC_MODE_RESPONSE

```
Offset  Tamaño  Descripción
0       N       Identificador de carpeta (UTF-8, terminado en null)
N       1       Modo de sincronización (0=DESIGNATED, 1=BEST_EFFORT, 2=BROADCAST, 3=CONSENSUS)
```

#### FOLDER_METADATA_REQUEST

```
Offset  Tamaño  Descripción
0       N       Identificador de carpeta (UTF-8, terminado en null)
N       4       Índice de pieza (big-endian, basado en 0)
```

#### FOLDER_METADATA_RESPONSE

```
Offset  Tamaño  Descripción
0       N       Identificador de carpeta (UTF-8, terminado en null)
N       4       Índice de pieza (big-endian)
N+4     4       Total de piezas (big-endian)
N+8     4       Tamaño de pieza (big-endian)
N+12    M       Datos de pieza (fragmento de archivo .tonic bencoded)
```

#### BLOOM_FILTER_REQUEST

```
Offset  Tamaño  Descripción
0       4       Tamaño del filtro en bytes (big-endian)
```

#### BLOOM_FILTER_RESPONSE

```
Offset  Tamaño  Descripción
0       4       Tamaño del filtro en bytes (big-endian)
4       4       Conteo de hash (big-endian)
8       N       Datos del filtro bloom (matriz de bits)
```

### Descubrimiento de Chunks

Los chunks se descubren a través de múltiples mecanismos:

1. **DHT (BEP 44)**: Almacenar y recuperar metadatos de chunks usando DHT. El hash del chunk (32 bytes) se usa como clave DHT. Formato de metadatos: `{"type": "xet_chunk", "available": True, "ed25519_public_key": "...", "ed25519_signature": "..."}`

2. **Trackers**: Anunciar disponibilidad de chunks a trackers. Los primeros 20 bytes del hash del chunk se usan como info_hash para anuncios de tracker.

3. **Peer Exchange (PEX)**: PEX extendido (BEP 11) con mensajes de disponibilidad de chunks. Los tipos de mensaje `CHUNKS_ADDED` y `CHUNKS_DROPPED` intercambian listas de hashes de chunks.

4. **Filtros Bloom**: Pre-filtrar consultas de disponibilidad de chunks. Los pares intercambian filtros bloom que contienen sus chunks disponibles para reducir la sobrecarga de red.

5. **Catálogo de Chunks**: Índice en memoria o persistente que mapea hashes de chunks a información de pares. Permite consultas rápidas en masa para múltiples chunks.

6. **Descubrimiento Local de Pares (BEP 14)**: Multicast UDP para descubrimiento de pares en red local. Dirección y puerto multicast específicos de XET configurables.

7. **Difusión Multicast**: Multicast UDP para anuncios de chunks en red local.

8. **Protocolo Gossip**: Protocolo estilo epidémico para propagación descentralizada de actualizaciones con fanout e intervalo configurables.

9. **Inundación Controlada**: Mecanismo de inundación basado en TTL para actualizaciones urgentes con umbral de prioridad.

10. **Metadatos de Torrent**: Extraer hashes de chunks de metadatos XET del torrent o capas de piezas de BitTorrent v2.

### Sincronización de Carpetas

XET soporta sincronización de carpetas con múltiples modos de sincronización:

#### Modos de Sincronización

- **DESIGNATED (0)**: Fuente única de verdad. Un par designado como fuente, otros se sincronizan desde él. Elección automática de par fuente basada en tiempo de actividad y disponibilidad de chunks.

- **BEST_EFFORT (1)**: Todos los nodos contribuyen actualizaciones, mejor esfuerzo. Resolución de conflictos vía last-write-wins, version-vector, 3-way-merge o estrategias de timestamp.

- **BROADCAST (2)**: Nodos específicos difunden actualizaciones con cola. Usa protocolo gossip o inundación controlada para propagación.

- **CONSENSUS (3)**: Las actualizaciones requieren acuerdo de la mayoría de nodos. Soporta mayoría simple, consenso Raft o Tolerancia a Fallos Bizantinos (BFT).

#### Resolución de Conflictos

Cuando se detectan conflictos en modo BEST_EFFORT, están disponibles las siguientes estrategias:

- **last-write-wins**: El timestamp de modificación más reciente gana
- **version-vector**: Detección y resolución de conflictos basada en reloj vectorial
- **3-way-merge**: Algoritmo de fusión de tres vías para resolución automática de conflictos
- **timestamp**: Resolución basada en timestamp con ventanas de tiempo configurables

#### Integración Git

Versiones de carpetas rastreadas vía referencias de commit git (SHA-1 o SHA-256). Cambios detectados vía `git diff`. Auto-commit habilitado si `git_auto_commit=True`. El repositorio git debe estar inicializado en la raíz de la carpeta.

#### Lista de Permitidos

Lista de permitidos encriptada usando Ed25519 para firma y AES-256-GCM para almacenamiento. Verificada durante el handshake de pares. Se soportan alias para nombres de pares legibles por humanos. Hash de lista de permitidos intercambiado durante el handshake de extensión.

### Formato de Archivo .tonic

El formato de archivo `.tonic` (similar a `.torrent`) contiene metadatos específicos de XET:

```
dictionary {
    "xet": dictionary {
        "version": integer,           # Versión del formato (1)
        "sync_mode": integer,        # 0=DESIGNATED, 1=BEST_EFFORT, 2=BROADCAST, 3=CONSENSUS
        "git_ref": string,           # Referencia de commit git (SHA-1 o SHA-256)
        "allowlist_hash": string,    # Hash SHA-256 de la lista de permitidos
        "file_tree": dictionary {    # Estructura de directorio anidada
            "path": dictionary {
                "": dictionary {     # Clave vacía = metadatos de archivo
                    "hash": string,   # Hash del archivo
                    "size": integer   # Tamaño del archivo
                }
            }
        },
        "files": list [              # Lista plana de archivos
            dictionary {
                "path": string,
                "hash": string,
                "size": integer
            }
        ],
        "chunk_hashes": list [       # Lista de hashes de chunks (32 bytes cada uno)
            string
        ]
    }
}
```

### Mapeo de Puertos NAT

XET requiere mapeo de puertos UDP para traversión NAT adecuada:

- **Puerto del Protocolo XET**: Configurable vía `xet_port` (por defecto `listen_port_udp`). Mapeado vía UPnP/NAT-PMP si `map_xet_port=True`.

- **Puerto Multicast XET**: Configurable vía `xet_multicast_port`. Mapeado si `map_xet_multicast_port=True` (generalmente no necesario para multicast).

La información del puerto externo se propaga a trackers para descubrimiento adecuado de pares. `NATManager.get_external_port()` soporta protocolo UDP para consultas de puerto XET.


## Arquitectura

### Componentes Principales

#### 1. Extensión de Protocolo (`ccbt/extensions/xet.py`)

La extensión Xet implementa mensajes de BEP 10 (Extension Protocol) para solicitudes y respuestas de chunks.

::: ccbt.extensions.xet.XetExtension
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Tipos de Mensaje:**

```23:29:ccbt/extensions/xet.py
class XetMessageType(IntEnum):
    """Xet Extension message types."""

    CHUNK_REQUEST = 0x01  # Request chunk by hash
    CHUNK_RESPONSE = 0x02  # Response with chunk data
    CHUNK_NOT_FOUND = 0x03  # Chunk not available
    CHUNK_ERROR = 0x04  # Error retrieving chunk
```

**Métodos Clave:**
- `encode_chunk_request()`: [ccbt/extensions/xet.py:89](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/extensions/xet.py#L89) - Codificar mensaje de solicitud de chunk con ID de solicitud
- `decode_chunk_request()`: [ccbt/extensions/xet.py:108](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/extensions/xet.py#L108) - Decodificar mensaje de solicitud de chunk
- `encode_chunk_response()`: [ccbt/extensions/xet.py:136](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/extensions/xet.py#L136) - Codificar respuesta de chunk con datos
- `handle_chunk_request()`: [ccbt/extensions/xet.py:210](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/extensions/xet.py#L210) - Manejar solicitud de chunk entrante del par
- `handle_chunk_response()`: [ccbt/extensions/xet.py:284](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/extensions/xet.py#L284) - Manejar respuesta de chunk del par

**Handshake de Extensión:**
- `encode_handshake()`: [ccbt/extensions/xet.py:61](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/extensions/xet.py#L61) - Codificar capacidades de extensión Xet
- `decode_handshake()`: [ccbt/extensions/xet.py:75](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/extensions/xet.py#L75) - Decodificar capacidades de extensión Xet del par

#### 2. Chunking Definido por Contenido (`ccbt/storage/xet_chunking.py`)

Algoritmo Gearhash CDC para segmentación inteligente de archivos con chunks de tamaño variable basados en patrones de contenido.

::: ccbt.storage.xet_chunking.GearhashChunker
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Constantes:**
- `MIN_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:21](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py#L21) - Tamaño mínimo de chunk de 8 KB
- `MAX_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:22](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py#L22) - Tamaño máximo de chunk de 128 KB
- `TARGET_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:23](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py#L23) - Tamaño objetivo de chunk por defecto de 16 KB
- `WINDOW_SIZE`: [ccbt/storage/xet_chunking.py:24](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py#L24) - Ventana de hash rodante de 48 bytes

**Métodos Clave:**
- `chunk_buffer()`: [ccbt/storage/xet_chunking.py:210](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py#L210) - Fragmentar datos usando algoritmo Gearhash CDC
- `_find_chunk_boundary()`: [ccbt/storage/xet_chunking.py:242](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py#L242) - Encontrar límite de chunk definido por contenido usando hash rodante
- `_init_gear_table()`: [ccbt/storage/xet_chunking.py:54](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py#L54) - Inicializar tabla de gear precalculada para hash rodante

**Algoritmo:**
El algoritmo Gearhash usa un hash rodante con una tabla de gear precalculada de 256 elementos para encontrar límites definidos por contenido. Esto asegura que contenido similar en diferentes archivos produzca los mismos límites de chunk, habilitando deduplicación entre archivos.

#### 3. Caché de Deduplicación (`ccbt/storage/xet_deduplication.py`)

Caché de deduplicación local basado en SQLite con integración DHT para deduplicación a nivel de chunk.

::: ccbt.storage.xet_deduplication.XetDeduplication
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Esquema de Base de Datos:**
- Tabla `chunks`: [ccbt/storage/xet_deduplication.py:65](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py#L65) - Almacena hash de chunk, tamaño, ruta de almacenamiento, conteo de referencias, timestamps
- Índices: [ccbt/storage/xet_deduplication.py:75](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py#L75) - En tamaño y last_accessed para consultas eficientes

**Métodos Clave:**
- `check_chunk_exists()`: [ccbt/storage/xet_deduplication.py:85](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py#L85) - Verificar si el chunk existe localmente y actualizar tiempo de acceso
- `store_chunk()`: [ccbt/storage/xet_deduplication.py:112](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py#L112) - Almacenar chunk con deduplicación (incrementa ref_count si existe)
- `get_chunk_path()`: [ccbt/storage/xet_deduplication.py:165](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py#L165) - Obtener ruta de almacenamiento local para chunk
- `cleanup_unused_chunks()`: [ccbt/storage/xet_deduplication.py:201](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py#L201) - Eliminar chunks no accedidos dentro de max_age_days

**Características:**
- Conteo de referencias: Rastrea cuántos torrents/archivos referencian cada chunk
- Limpieza automática: Elimina chunks no utilizados basados en tiempo de acceso
- Almacenamiento físico: Chunks almacenados en directorio `xet_chunks/` con hash como nombre de archivo

#### 4. CAS Peer-to-Peer (`ccbt/discovery/xet_cas.py`)

Descubrimiento e intercambio de chunks basado en DHT y trackers para Almacenamiento Direccionable por Contenido descentralizado.

::: ccbt.discovery.xet_cas.P2PCASClient
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Métodos Clave:**
- `announce_chunk()`: [ccbt/discovery/xet_cas.py:50](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/xet_cas.py#L50) - Anunciar disponibilidad de chunk a DHT (BEP 44) y trackers
- `find_chunk_peers()`: [ccbt/discovery/xet_cas.py:112](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/xet_cas.py#L112) - Encontrar pares que tienen un chunk específico vía consultas DHT y tracker
- `request_chunk_from_peer()`: [ccbt/discovery/xet_cas.py:200](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/xet_cas.py#L200) - Solicitar chunk de un par específico usando protocolo de extensión Xet

**Integración DHT:**
- Usa BEP 44 (Distributed Hash Table for Mutable Items) para almacenar metadatos de chunks
- Formato de metadatos de chunk: [ccbt/discovery/xet_cas.py:68](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/xet_cas.py#L68) - `{"type": "xet_chunk", "available": True}`
- Soporta múltiples métodos DHT: `store()`, `store_chunk_hash()`, `get_chunk_peers()`, `get_peers()`, `find_value()`

**Integración de Trackers:**
- Anuncia chunks a trackers usando los primeros 20 bytes del hash del chunk como info_hash
- Habilita descubrimiento de pares basado en trackers para chunks

## Formatos de Almacenamiento

### Formato Xorb

Los Xorbs agrupan múltiples chunks para almacenamiento y recuperación eficientes.

::: ccbt.storage.xet_xorb.Xorb
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Especificación de Formato:**
- Encabezado: [ccbt/storage/xet_xorb.py:123](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L123) - 16 bytes (magic `0x24687531`, versión, flags, reservado)
- Conteo de chunks: [ccbt/storage/xet_xorb.py:149](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L149) - 4 bytes (uint32, little-endian)
- Entradas de chunk: [ccbt/storage/xet_xorb.py:140](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L140) - Variable (hash, tamaños, datos para cada chunk)
- Metadatos: [ccbt/storage/xet_xorb.py:119](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L119) - 8 bytes (tamaño total sin comprimir como uint64)

**Constantes:**
- `MAX_XORB_SIZE`: [ccbt/storage/xet_xorb.py:35](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L35) - Tamaño máximo de xorb de 64 MiB
- `XORB_MAGIC_INT`: [ccbt/storage/xet_xorb.py:36](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L36) - Número mágico `0x24687531`
- `FLAG_COMPRESSED`: [ccbt/storage/xet_xorb.py:42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L42) - Flag de compresión LZ4

**Métodos Clave:**
- `add_chunk()`: [ccbt/storage/xet_xorb.py:62](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L62) - Añadir chunk a xorb (falla si excede MAX_XORB_SIZE)
- `serialize()`: [ccbt/storage/xet_xorb.py:84](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L84) - Serializar xorb a formato binario con compresión LZ4 opcional
- `deserialize()`: [ccbt/storage/xet_xorb.py:200](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L200) - Deserializar xorb desde formato binario con descompresión automática

**Compresión:**
- Compresión LZ4 opcional: [ccbt/storage/xet_xorb.py:132](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L132) - Comprime datos de chunk si `compress=True` y LZ4 disponible
- Detección automática: [ccbt/storage/xet_xorb.py:22](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L22) - Recurre elegantemente si LZ4 no está instalado

### Formato Shard

Los Shards almacenan metadatos de archivos e información CAS para operaciones eficientes del sistema de archivos.

::: ccbt.storage.xet_shard.XetShard
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Especificación de Formato:**
- Encabezado: [ccbt/storage/xet_shard.py:142](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L142) - 24 bytes (magic `"SHAR"`, versión, flags, conteos de archivo/xorb/chunk)
- Sección de Información de Archivo: [ccbt/storage/xet_shard.py:145](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L145) - Variable (ruta, hash, tamaño, referencias xorb para cada archivo)
- Sección de Información CAS: [ccbt/storage/xet_shard.py:148](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L148) - Variable (hashes xorb, hashes de chunks)
- Pie de página HMAC: [ccbt/storage/xet_shard.py:150](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L150) - 32 bytes (HMAC-SHA256 si se proporciona clave)

**Constantes:**
- `SHARD_MAGIC`: [ccbt/storage/xet_shard.py:19](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L19) - Bytes mágicos `b"SHAR"`
- `SHARD_VERSION`: [ccbt/storage/xet_shard.py:20](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L20) - Versión de formato 1
- `HMAC_SIZE`: [ccbt/storage/xet_shard.py:22](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L22) - 32 bytes para HMAC-SHA256

**Métodos Clave:**
- `add_file_info()`: [ccbt/storage/xet_shard.py:47](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L47) - Añadir metadatos de archivo con referencias xorb
- `add_chunk_hash()`: [ccbt/storage/xet_shard.py:80](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L80) - Añadir hash de chunk a shard
- `add_xorb_hash()`: [ccbt/storage/xet_shard.py:93](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L93) - Añadir hash xorb a shard
- `serialize()`: [ccbt/storage/xet_shard.py:106](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L106) - Serializar shard a formato binario con HMAC opcional
- `deserialize()`: [ccbt/storage/xet_shard.py:201](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L201) - Deserializar shard desde formato binario con verificación HMAC

**Integridad:**
- Verificación HMAC: [ccbt/storage/xet_shard.py:170](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L170) - HMAC-SHA256 opcional para integridad de shard

## Cálculo de Merkle Tree

Los archivos se verifican usando Merkle trees construidos desde hashes de chunks para verificación eficiente de integridad.

::: ccbt.storage.xet_hashing.XetHasher
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Funciones de Hash:**
- `compute_chunk_hash()`: [ccbt/storage/xet_hashing.py:43](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L43) - Calcular hash BLAKE3-256 para chunk (recurre a SHA-256)
- `compute_xorb_hash()`: [ccbt/storage/xet_hashing.py:63](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L63) - Calcular hash para datos xorb
- `verify_chunk_hash()`: [ccbt/storage/xet_hashing.py:158](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L158) - Verificar datos de chunk contra hash esperado

**Construcción de Merkle Tree:**
- `build_merkle_tree()`: [ccbt/storage/xet_hashing.py:78](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L78) - Construir Merkle tree desde datos de chunk (hashea chunks primero)
- `build_merkle_tree_from_hashes()`: [ccbt/storage/xet_hashing.py:115](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L115) - Construir Merkle tree desde hashes de chunk pre-calculados

**Algoritmo:**
El Merkle tree se construye de abajo hacia arriba emparejando hashes en cada nivel:
1. Comenzar con hashes de chunk (nodos hoja)
2. Emparejar hashes adyacentes y hashear la combinación
3. Repetir hasta que quede un solo hash raíz
4. Números impares: duplicar el último hash para emparejamiento

**Hash Incremental:**
- `hash_file_incremental()`: [ccbt/storage/xet_hashing.py:175](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L175) - Calcular hash de archivo incrementalmente para eficiencia de memoria

**Tamaño de Hash:**
- `HASH_SIZE`: [ccbt/storage/xet_hashing.py:40](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L40) - 32 bytes para BLAKE3-256 o SHA-256

**Soporte BLAKE3:**
- Detección automática: [ccbt/storage/xet_hashing.py:21](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L21) - Usa BLAKE3 si está disponible, recurre a SHA-256
- Rendimiento: BLAKE3 proporciona mejor rendimiento para archivos grandes

## Referencias

- [BEP 10: Extension Protocol](https://www.bittorrent.org/beps/bep_0010.html)
- [BEP 44: Distributed Hash Table for Mutable Items](https://www.bittorrent.org/beps/bep_0044.html)
- [BEP 52: BitTorrent Protocol v2](https://www.bittorrent.org/beps/bep_0052.html)
- [Gearhash Algorithm](https://github.com/xetdata/xet-core)

