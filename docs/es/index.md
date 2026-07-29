# ccBitTorrent - Cliente BitTorrent de Alto Rendimiento

Un cliente BitTorrent moderno y de alto rendimiento construido con Python asyncio, que incluye algoritmos avanzados de selección de piezas, intercambio paralelo de metadatos y E/O de disco optimizada.

## Características

### Optimizaciones de Rendimiento
- **E/O Asíncrona**: Implementación completa de asyncio para una concurrencia superior. Ver [ccbt/session/async_main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/async_main.py)
- **Selección Rarest-First**: Selección inteligente de piezas para una salud óptima del enjambre. Ver [ccbt/piece/async_piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py)
- **Modo Endgame**: Solicitudes duplicadas para una finalización más rápida
- **Canalización de Solicitudes**: Colas de solicitudes profundas (16-64 solicitudes pendientes por par). Ver [ccbt/peer/async_peer_connection.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/async_peer_connection.py)
- **Choking Tit-for-Tat**: Asignación justa de ancho de banda con optimista unchoke
- **Metadatos Paralelos**: Obtención concurrente de ut_metadata desde múltiples pares. Ver [ccbt/piece/async_metadata_exchange.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_metadata_exchange.py)
- **Optimización de E/O de Disco**: Preasignación de archivos, escritura por lotes, almacenamiento en búfer de anillo, E/O mapeada en memoria, io_uring/E/O directa (configurable). Ver [ccbt/storage/disk_io.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/disk_io.py)
- **Grupo de Verificación de Hash**: Verificación SHA-1 paralela en hilos de trabajo

### Configuración Avanzada
- **Configuración TOML**: Sistema de configuración completo con recarga en caliente. Ver [ccbt/config/config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)
- **Configuración por Torrent**: Anulaciones de configuración individual por torrent
- **Limitación de Velocidad**: Límites globales y por torrent de carga/descarga. Ver [ccbt.toml:38-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L38-L42)
- **Selección de Estrategia**: Selección de piezas round-robin, rarest-first o secuencial. Ver [ccbt.toml:100-114](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L100-L114)
- **Modo Streaming**: Selección de piezas basada en prioridad para archivos multimedia

### Características de Red
- **Soporte de Tracker UDP**: Comunicación de tracker UDP compatible con BEP 15. Ver [ccbt/discovery/tracker_udp_client.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/tracker_udp_client.py)
- **DHT Mejorado**: Tabla de enrutamiento Kademlia completa con búsquedas iterativas. Ver [ccbt/discovery/dht.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/dht.py)
- **Intercambio de Pares (PEX)**: Descubrimiento de pares compatible con BEP 11. Ver [ccbt/discovery/pex.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/pex.py)
- **Gestión de Conexiones**: Selección adaptativa de pares y límites de conexión. Ver [ccbt/peer/connection_pool.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/connection_pool.py)
- **Optimizaciones de Protocolo**: Manejo eficiente de mensajes en memoria con rutas de cero copia

## Extensión de Protocolo Xet (BEP XET)

La Extensión de Protocolo Xet es un diferenciador clave que transforma BitTorrent en un sistema de archivos peer-to-peer actualizable y súper rápido optimizado para colaboración. BEP XET permite:

- **Fragmentación Definida por Contenido**: Segmentación inteligente de archivos basada en Gearhash (fragmentos de 8KB-128KB) para actualizaciones eficientes. Ver [ccbt/storage/xet_chunking.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py)
- **Deduplicación entre Torrents**: Deduplicación a nivel de fragmento entre múltiples torrents. Ver [ccbt/storage/xet_deduplication.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py)
- **CAS Peer-to-Peer**: Almacenamiento de Direcciones de Contenido Descentralizado usando DHT y trackers. Ver [ccbt/discovery/xet_cas.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/xet_cas.py)
- **Actualizaciones Súper Rápidas**: Solo los fragmentos cambiados necesitan redistribución, permitiendo intercambio rápido de archivos colaborativos
- **Sistema de Archivos P2P**: Transforma BitTorrent en un sistema de archivos peer-to-peer actualizable optimizado para colaboración
- **Verificación de Árbol Merkle**: Hashing BLAKE3-256 con respaldo SHA-256 para integridad. Ver [ccbt/storage/xet_hashing.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py)

[Más información sobre BEP XET →](bep_xet.md)

### Observabilidad
- **Exportación de Métricas**: Métricas compatibles con Prometheus para monitoreo. Ver [ccbt/monitoring/metrics_collector.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/monitoring/metrics_collector.py)
- **Registro Estructurado**: Registro configurable con seguimiento por par. Ver [ccbt/utils/logging_config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/logging_config.py)
- **Estadísticas de Rendimiento**: Seguimiento en tiempo real de rendimiento, latencia y profundidad de cola
- **Monitoreo de Salud**: Calidad de conexión y puntuación de confiabilidad de pares
- **Panel de Terminal**: Panel en vivo basado en Textual (Bitonic). Ver [ccbt/interface/terminal_dashboard.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py)
- **Administrador de Alertas**: Alertas basadas en reglas con persistencia y pruebas mediante CLI. Ver [ccbt/monitoring/alert_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/monitoring/alert_manager.py)

## Inicio Rápido

### Instalación con UV

Instale UV desde [astral.sh/uv](https://astral.sh/uv), luego instale ccBitTorrent.

Referencia: [pyproject.toml:79-81](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L79-L81) para los puntos de entrada

### Puntos de Entrada Principales

**Bitonic** - La interfaz principal del panel de terminal (recomendado):
- Punto de entrada: [ccbt/interface/terminal_dashboard.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- Definido en: [pyproject.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L81)
- Lanzar: `uv run bitonic` o `uv run ccbt dashboard`

**btbt CLI** - Interfaz de línea de comandos mejorada:
- Punto de entrada: [ccbt/cli/main.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1463)
- Definido en: [pyproject.toml:80](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L80)
- Lanzar: `uv run btbt`

**ccbt** - Interfaz CLI básica:
- Punto de entrada: [ccbt/__main__.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/__main__.py#L18)
- Definido en: [pyproject.toml:79](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L79)
- Lanzar: `uv run ccbt`

Para uso detallado, consulte:
- [Guía de Inicio](getting-started.md) - Tutorial paso a paso
- [Bitonic](bitonic.md) - Guía del panel de terminal
- [btbt CLI](btbt-cli.md) - Referencia completa de comandos

## Documentación

- [BEP XET](bep_xet.md) - Extensión de Protocolo Xet para fragmentación definida por contenido y deduplicación
- [Inicio](getting-started.md) - Instalación y primeros pasos
- [Bitonic](bitonic.md) - Panel de terminal (interfaz principal)
- [btbt CLI](btbt-cli.md) - Referencia de interfaz de línea de comandos
- [Configuración](configuration.md) - Opciones de configuración y configuración
- [Ajuste de Rendimiento](performance.md) - Guía de optimización
- [Referencia de API ccBT](API.md) - Documentación de API de Python
- [Contribuir](contributing.md) - Cómo contribuir
- [Financiación](funding.md) - Apoyar el proyecto

## Licencia

Este proyecto está licenciado bajo la **GNU General Public License v2 (GPL-2.0)** - consulte [license.md](license.md) para más detalles.

Además, este proyecto está sujeto a restricciones de uso adicionales bajo la **Licencia ccBT RAIL-AMS** - consulte [ccBT-RAIL.md](ccBT-RAIL.md) para los términos completos y restricciones de uso.

**Importante**: Ambas licencias se aplican a este software. Debe cumplir con todos los términos y restricciones tanto en la licencia GPL-2.0 como en la licencia RAIL.

## Informes

Ver informes del proyecto en la documentación:
- [Informes de Cobertura](reports/coverage.md) - Análisis de cobertura de código
- [Informe de Seguridad Bandit](reports/bandit/index.md) - Resultados de escaneo de seguridad
- [Puntos de Referencia](reports/benchmarks/index.md) - Resultados de puntos de referencia de rendimiento

## Agradecimientos

- Especificación del protocolo BitTorrent (BEP 5, 10, 11, 15, 52)
- Protocolo Xet para inspiración de fragmentación definida por contenido
- Python asyncio para E/O de alto rendimiento
- La comunidad BitTorrent para el desarrollo del protocolo
