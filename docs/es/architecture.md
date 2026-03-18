# Resumen de Arquitectura

Este documento proporciona una descripción técnica de la arquitectura, componentes y flujo de datos de ccBitTorrent.

## Puntos de Entrada

ccBitTorrent proporciona múltiples puntos de entrada para diferentes casos de uso:

1. **CLI Básico (`ccbt`)**: Interfaz de línea de comandos simple para descargas de torrents individuales
   - Punto de entrada: `ccbt/__main__.py:main`
   - Uso: `python -m ccbt torrent.torrent` o `python -m ccbt "magnet:..."`

2. **CLI Async (`ccbt async`)**: Interfaz asíncrona de alto rendimiento con gestión completa de sesiones
   - Punto de entrada: `ccbt/session/async_main.py:main`
   - Soporta modo daemon, múltiples torrents y características avanzadas

3. **CLI Mejorado (`btbt`)**: Interfaz de línea de comandos rica con características completas
   - Punto de entrada: `ccbt/cli/main.py:main`
   - Proporciona comandos interactivos, monitoreo y configuración avanzada

4. **Panel de Terminal (`bitonic`)**: Panel de terminal interactivo en vivo (TUI)
   - Punto de entrada: `ccbt/interface/terminal_dashboard.py:main`
   - Visualización en tiempo real de torrents, pares y métricas del sistema

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    ccBitTorrent Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│  CLI Interface                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │   Basic     │ │ Interactive │ │  Dashboard   │              │
│  │   Commands  │ │     CLI     │ │   (TUI)     │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Session Management                                             │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              AsyncSessionManager                           │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │ │
│  │  │   Config    │ │   Events    │ │  Checkpoint │          │ │
│  │  │  Manager    │ │   System    │ │   Manager   │          │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘          │ │
│  └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  Core Components                                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │    Peer     │ │    Piece    │ │    Disk     │              │
│  │  Connection │ │   Manager   │ │     I/O     │              │
│  │  Manager    │ │             │ │   Manager   │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │   Tracker   │ │     DHT     │ │  Metadata   │              │
│  │   Client    │ │   Manager   │ │  Exchange   │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Network Layer                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │    TCP      │ │     UDP     │ │   WebRTC    │              │
│  │ Connections │ │  Trackers   │ │ (WebTorrent)│              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Monitoring & Observability                                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │   Metrics   │ │   Alerts    │ │   Tracing   │              │
│  │  Collector  │ │   Manager   │ │   Manager   │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## Componentes Principales

### Arquitectura de Servicios

ccBitTorrent utiliza una arquitectura orientada a servicios con varios servicios principales:

- **PeerService**: Gestiona conexiones y comunicación entre pares
  - Implementación: `ccbt/services/peer_service.py`
  - Rastrea conexiones de pares, ancho de banda y estadísticas de piezas
  
- **StorageService**: Gestiona operaciones del sistema de archivos con escrituras fragmentadas de alto rendimiento
  - Implementación: `ccbt/services/storage_service.py`
  - Maneja creación de archivos, operaciones de lectura/escritura de datos
  
- **TrackerService**: Gestiona comunicación con trackers y monitoreo de salud
  - Implementación: `ccbt/services/tracker_service.py`
  - Soporta trackers HTTP y UDP con soporte de scrape (BEP 48)

Todos los servicios heredan de la clase base `Service` que proporciona gestión del ciclo de vida, verificaciones de salud y seguimiento de estado.

::: ccbt.services.base.Service

### AsyncSessionManager

El orquestador central que gestiona toda la sesión BitTorrent. Una sola implementación en `ccbt/session/session.py`; `async_main.py` reexporta.

Componentes principales: `dht_client`, `peer_service`, `queue_manager`, `nat_manager`, `private_torrents` (BEP 27), `scrape_cache` (BEP 48), tareas en segundo plano.

::: ccbt.session.session.AsyncSessionManager

**Responsabilidades:**
- Gestión del ciclo de vida de torrents
- Coordinación de conexiones de pares a través de `PeerService`
- Gestión de protocolos (`BitTorrentProtocol`, `IPFSProtocol`)
- Asignación y límites de recursos
- Distribución de eventos a través de `EventBus`
- Gestión de checkpoints
- Gestión de cliente DHT
- Gestión de colas para priorización de torrents
- Traversión NAT a través de `NATManager`
- Scraping de trackers (BEP 48)

#### Controladores de Sesión (refactorización)

Para mejorar la mantenibilidad, la lógica de sesión se está extrayendo progresivamente en controladores enfocados bajo `ccbt/session/`:

- `models.py`: Enum `TorrentStatus` y `SessionContext`
- `types.py`: Protocolos (`DHTClientProtocol`, `TrackerClientProtocol`, `PeerManagerProtocol`, `PieceManagerProtocol`)
- `tasks.py`: `TaskSupervisor` para gestión de tareas en segundo plano
- `checkpointing.py`: `CheckpointController` para guardar/cargar y procesamiento por lotes
- `discovery.py`: `DiscoveryController` para descubrimiento DHT/tracker y deduplicación
- `peer_events.py`: `PeerEventsBinder` para conexión de callbacks
- `lifecycle.py`: `LifecycleController` para secuenciación de inicio/pausa/reanudación/detención
- `metrics_status.py`: Ayudantes de agregación de métricas y estado
- `adapters.py`: `DHTAdapter` y `TrackerAdapter` para unificar clientes concretos detrás de protocolos

### Gestor de Conexiones de Pares

Maneja todas las conexiones de pares con pipeline avanzado. El `AsyncPeerConnectionManager` gestiona conexiones de pares individuales para una sesión de torrent.

::: ccbt.peer.async_peer_connection.AsyncPeerConnectionManager

**Características:**
- Conexiones TCP asíncronas
- Pipeline de solicitudes (16-64 solicitudes pendientes)
- Tamaño de bloque adaptativo
- Pool de conexiones
- Algoritmos de choking/unchoking
- Handshake del protocolo BitTorrent
- Soporte de protocolo de extensiones (Fast, PEX, DHT, WebSeed, SSL, XET)

### Gestor de Piezas

Implementa algoritmos avanzados de selección de piezas. El `AsyncPieceManager` coordina la descarga de piezas, verificación y seguimiento de finalización.

::: ccbt.piece.async_piece_manager.AsyncPieceManager

**Algoritmos:**
- **Rarest-First**: Salud óptima del enjambre
- **Secuencial**: Para medios de transmisión
- **Round-Robin**: Fallback simple
- **Modo Endgame**: Solicitudes duplicadas para finalización
- Soporte de selección de archivos para descargas parciales

### Gestor de I/O de Disco

Operaciones de disco optimizadas con múltiples estrategias. El sistema de I/O de disco se inicializa a través de `init_disk_io()` y se gestiona a través del gestor de sesión.

::: ccbt.storage.disk_io.DiskIOManager

**Optimizaciones:**
- Preasignación de archivos (sparse/full)
- Procesamiento por lotes y almacenamiento en búfer de escritura
- I/O mapeado en memoria
- Soporte io_uring (Linux)
- I/O directo para almacenamiento de alto rendimiento
- Verificación de hash paralela
- Gestión de checkpoints para capacidad de reanudación

## Flujo de Datos

### Proceso de Descarga

```
1. Carga de Torrent
   ┌─────────────┐
   │ Torrent File│ ──┐
   │ or Magnet   │   │
   └─────────────┘   │
                     │
2. Anuncio de Tracker│
   ┌─────────────┐   │
   │   Tracker  │ ◄──┘
   │   Client   │
   └─────────────┘
           │
           ▼
3. Descubrimiento de Pares
   ┌─────────────┐
   │    DHT     │
   │   Manager  │
   └─────────────┘
           │
           ▼
4. Conexiones de Pares
   ┌─────────────┐
   │    Peer    │
   │ Connection │
   │   Manager  │
   └─────────────┘
           │
           ▼
5. Selección de Piezas
   ┌─────────────┐
   │    Piece    │
   │   Manager   │
   └─────────────┘
           │
           ▼
6. Transferencia de Datos
   ┌─────────────┐
   │    Disk     │
   │     I/O     │
   │   Manager   │
   └─────────────┘
```

### Sistema de Eventos

El sistema utiliza una arquitectura basada en eventos para acoplamiento flexible. Los eventos se emiten a través del `EventBus` global y pueden ser suscritos por cualquier componente.

**Implementación:** `ccbt/utils/events.py`

El sistema de eventos incluye tipos de eventos completos:

El enum `EventType` define todos los eventos del sistema (pares, piezas, torrents, trackers, DHT, protocolo, extensiones, seguridad) y se emiten con `emit_event()` en el bus global.

::: ccbt.utils.events.EventType
::: ccbt.utils.events.EventBus

## Sistema de Configuración

### Configuración Jerárquica

La configuración es gestionada por `ConfigManager` que carga configuraciones desde múltiples fuentes en orden de prioridad.

**Implementación:** `ccbt/config/config.py`

La clase `ConfigManager` maneja la carga, validación y recarga en caliente.

::: ccbt.config.config.ConfigManager

**Fuentes de Configuración (en orden):**
1. Valores predeterminados (desde modelos Pydantic)
2. Archivo de configuración (`ccbt.toml` en el directorio actual, `~/.config/ccbt/ccbt.toml`, o `~/.ccbt.toml`)
3. Variables de entorno (`CCBT_*`)
4. Argumentos CLI
5. Sobrescrituras por torrent

### Recarga en Caliente

El `ConfigManager` soporta recarga en caliente de archivos de configuración sin reiniciar la aplicación. La recarga en caliente se inicia automáticamente cuando se detecta un archivo de configuración.

## Monitoreo y Observabilidad

### Recopilación de Métricas

La recopilación de métricas se inicializa a través de `init_metrics()` y proporciona métricas compatibles con Prometheus.

**Implementación:** `ccbt/monitoring/metrics_collector.py`

Las métricas se inicializan en el método `start()` del gestor de sesión y se pueden acceder a través de `session.metrics` si está habilitado en la configuración.

### Sistema de Alertas

El sistema de alertas proporciona alertas basadas en reglas para varias condiciones del sistema.

**Implementación:** `ccbt/monitoring/alert_manager.py`

### Trazado

Soporte de trazado distribuido para análisis de rendimiento y depuración.

**Implementación:** `ccbt/monitoring/tracing.py`

## Características de Seguridad

### Gestor de Seguridad

El `SecurityManager` proporciona características de seguridad completas incluyendo filtrado de IP, validación de pares, limitación de velocidad y detección de anomalías.

**Implementación:** `ccbt/security/security_manager.py`

El gestor de seguridad se inicializa en el método `start()` del gestor de sesión y puede cargar filtros de IP desde la configuración.

### Validación de Pares

La validación de pares es manejada por el `PeerValidator` que verifica IPs bloqueadas y patrones de comportamiento sospechosos.

**Implementación:** `ccbt/security/peer_validator.py`

### Limitación de Velocidad

La limitación de velocidad adaptativa para gestión de ancho de banda es proporcionada por el `RateLimiter` y `AdaptiveLimiter` (basado en ML).

**Implementación:** `ccbt/security/rate_limiter.py`, `ccbt/ml/adaptive_limiter.py`

## Extensibilidad

### Sistema de Plugins

El sistema de plugins permite que plugins y extensiones opcionales sean registrados y gestionados.

**Implementación:** `ccbt/plugins/base.py`

Los plugins pueden ser registrados con el `PluginManager` y proporcionan hooks para varios eventos del sistema.

### Extensiones de Protocolo

Las extensiones del protocolo BitTorrent son gestionadas por el `ExtensionManager` que maneja las extensiones Fast Extension, PEX, DHT, WebSeed, SSL y XET.

**Implementación:** `ccbt/extensions/manager.py`

El `ExtensionManager` inicializa las extensiones Protocol, SSL, Fast, PEX y DHT.

::: ccbt.extensions.manager.ExtensionManager

### Gestor de Protocolos

El `ProtocolManager` gestiona múltiples protocolos (BitTorrent, IPFS, WebTorrent, XET, Hybrid) con soporte de circuit breaker y seguimiento de rendimiento.

**Implementación:** `ccbt/protocols/base.py`

El `ProtocolManager` gestiona múltiples protocolos con circuit breaker y seguimiento de rendimiento.

::: ccbt.protocols.base.ProtocolManager

## Optimizaciones de Rendimiento

### Async/Await en Todo

Todas las operaciones de I/O son asíncronas:
- Operaciones de red
- I/O de disco
- Verificación de hash
- Carga de configuración

### Gestión de Memoria

- Manejo de mensajes de copia cero donde sea posible
- Búferes de anillo para escenarios de alto rendimiento
- I/O de archivos mapeado en memoria
- Estructuras de datos eficientes

### Pool de Conexiones

El pool de conexiones está implementado en la capa de conexión de pares para reutilizar eficientemente las conexiones TCP y gestionar límites de conexión.

**Implementación:** `ccbt/peer/connection_pool.py`

## Arquitectura de Pruebas

### Categorías de Pruebas

- **Pruebas Unitarias**: Pruebas de componentes individuales
- **Pruebas de Integración**: Pruebas de interacción de componentes
- **Pruebas de Rendimiento**: Benchmarking y perfilado
- **Pruebas de Caos**: Inyección de fallos y pruebas de resiliencia

### Utilidades de Pruebas

Las utilidades de pruebas y mocks están disponibles en el directorio `tests/` para pruebas unitarias, de integración, de propiedades y de rendimiento.

## Consideraciones Futuras de Arquitectura

### Escalabilidad

- Escalado horizontal con múltiples gestores de sesión
- Descubrimiento de pares distribuido
- Balanceo de carga entre instancias

### Integración en la Nube

- Backends de almacenamiento en la nube
- Opciones de despliegue serverless
- Orquestación de contenedores

### Características Avanzadas

- Aprendizaje automático para selección de pares
- Descubrimiento de pares basado en blockchain
- **Integración IPFS** (Implementada)
- Compatibilidad WebTorrent

## Integración del Protocolo IPFS

### Resumen de Arquitectura

La integración del protocolo IPFS proporciona direccionamiento de contenido descentralizado y capacidades de red peer-to-peer a través de un daemon IPFS.

**Implementación:** `ccbt/protocols/ipfs.py`

### Puntos de Integración

```
┌─────────────────────────────────────────────────────────────┐
│                    IPFS Protocol Integration                  │
├─────────────────────────────────────────────────────────────┤
│  Session Manager                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         AsyncSessionManager                           │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │         ProtocolManager                         │ │  │
│  │  │  ┌──────────────┐  ┌──────────────┐           │ │  │
│  │  │  │ BitTorrent   │  │    IPFS      │           │ │  │
│  │  │  │  Protocol    │  │  Protocol    │           │ │  │
│  │  │  └──────────────┘  └──────────────┘           │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  IPFS Protocol                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   HTTP API   │  │   Pubsub     │  │     DHT      │     │
│  │  Client      │  │  Messaging   │  │  Discovery   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Content    │  │   Gateway    │  │   Pinning    │     │
│  │  Operations  │  │   Fallback   │  │   Manager    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
├─────────────────────────────────────────────────────────────┤
│  IPFS Daemon (External)                                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  IPFS Node (libp2p, Bitswap, DHT, Gateway)          │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Ciclo de Vida del Protocolo

1. **Inicialización**: Protocolo creado y registrado en `ProtocolManager`
2. **Conexión**: `start()` se conecta al daemon IPFS a través de HTTP API
3. **Verificación**: ID de nodo consultado para verificar conexión
4. **Operación**: Operaciones de contenido, conexiones de pares, mensajería
5. **Limpieza**: `stop()` desconecta y limpia recursos

### Integración del Gestor de Sesión

El protocolo IPFS se registra automáticamente al iniciar el gestor de sesión si está habilitado.

::: ccbt.protocols.ipfs.IPFSProtocol

### Direccionamiento de Contenido

IPFS utiliza Identificadores de Contenido (CIDs) para direccionamiento de contenido inmutable:

- **CIDv0**: Codificado en Base58, formato legacy (ej., `Qm...`)
- **CIDv1**: Codificado en Multibase, formato moderno (ej., `bafybei...`)
- El contenido se direcciona por su hash criptográfico
- El mismo contenido siempre produce el mismo CID

### Conversión de Torrent a IPFS

Los torrents pueden convertirse a contenido IPFS:

1. Metadatos del torrent serializados a JSON
2. Metadatos añadidos a IPFS, generando CID
3. Hashes de piezas referenciados como bloques
4. Contenido automáticamente fijado si está configurado

### Comunicación entre Pares

- **Pubsub**: Mensajería basada en temas (`/ccbt/peer/{peer_id}`)
- **Multiaddr**: Formato estándar para direcciones de pares
- **DHT**: Tabla hash distribuida para descubrimiento de pares
- **Colas de Mensajes**: Colas por par para entrega confiable

### Operaciones de Contenido

- **Add**: Contenido añadido a IPFS, devuelve CID
- **Get**: Contenido recuperado por CID
- **Pin**: Contenido fijado para prevenir recolección de basura
- **Unpin**: Contenido desfijado, puede ser recolectado como basura
- **Stats**: Estadísticas de contenido (tamaño, bloques, enlaces)

### Configuración

La configuración IPFS es parte del modelo `Config` principal. Vea la documentación de configuración para detalles sobre configuraciones IPFS.

### Manejo de Errores

- Fallos de conexión: Reintento automático con backoff exponencial
- Timeouts: Timeouts configurables por operación
- Daemon no disponible: Degradación elegante, protocolo permanece registrado
- Contenido no encontrado: Devuelve `None`, registra advertencia

### Consideraciones de Rendimiento

- **Operaciones Asíncronas**: Todas las llamadas API de IPFS usan `asyncio.to_thread` para evitar bloqueo
- **Caché**: Resultados de descubrimiento y estadísticas de contenido en caché con TTL
- **Fallback de Gateway**: Gateways públicos usados si el daemon no está disponible
- **Pool de Conexiones**: Reutiliza conexiones HTTP al daemon IPFS

### Diagrama de Secuencia

```
Session Manager          IPFS Protocol          IPFS Daemon
     │                         │                      │
     │  start()                │                      │
     ├────────────────────────>│                      │
     │                         │  connect()           │
     │                         ├─────────────────────>│
     │                         │  id()                │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │                         │                      │
     │  add_content()           │                      │
     ├────────────────────────>│  add_bytes()         │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │  <CID>                  │                      │
     │<────────────────────────┤                      │
     │                         │                      │
     │  get_content(CID)       │                      │
     ├────────────────────────>│  cat(CID)            │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │  <content>               │                      │
     │<────────────────────────┤                      │
     │                         │                      │
     │  stop()                  │                      │
     ├────────────────────────>│  close()             │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │                         │                      │
```

Para información más detallada sobre componentes específicos, vea los archivos de documentación individuales y el código fuente.

