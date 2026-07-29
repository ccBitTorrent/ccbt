# Guía de Ajuste de Rendimiento

Esta guía cubre técnicas de optimización de rendimiento para ccBitTorrent para lograr velocidades de descarga máximas y uso eficiente de recursos.

## Optimización de Red

### Configuración de Conexión

#### Profundidad del Pipeline

Controla el número de solicitudes pendientes por par.

Configuración: [ccbt.toml:12](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L12)

**Recomendaciones:**
- **Conexiones de alta latencia**: 32-64 (satélite, móvil)
- **Conexiones de baja latencia**: 16-32 (fibra, cable)
- **Redes locales**: 8-16 (transferencias LAN)

Implementación: [ccbt/peer/async_peer_connection.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/async_peer_connection.py) - Canalización de solicitudes

#### Tamaño de Bloque

Tamaño de los bloques de datos solicitados a los pares.

Configuración: [ccbt.toml:13](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L13)

**Recomendaciones:**
- **Alto ancho de banda**: 32-64 KiB (fibra, cable)
- **Ancho de banda medio**: 16-32 KiB (DSL, móvil)
- **Bajo ancho de banda**: 4-16 KiB (marcado, móvil lento)

Tamaños mín/máx de bloque: [ccbt.toml:14-15](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L14-L15)

#### Búferes de Socket

Aumentar para escenarios de alto rendimiento.

Configuración: [ccbt.toml:17-18](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L17-L18)

Valores predeterminados: [ccbt.toml:17-18](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L17-L18) (256 KiB cada uno)

Configuración TCP_NODELAY: [ccbt.toml:19](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L19)

### Límites de Conexión

#### Límites Globales de Pares

Configuración: [ccbt.toml:6-7](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L6-L7)

**Pautas de Ajuste:**
- **Alto ancho de banda**: Aumentar pares globales (200-500)
- **Bajo ancho de banda**: Reducir pares globales (50-100)
- **Muchos torrents**: Reducir límite por torrent (10-25)
- **Pocos torrents**: Aumentar límite por torrent (50-100)

Implementación: [ccbt/peer/connection_pool.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/connection_pool.py) - Gestión de grupo de conexiones

Conexiones máximas por par: [ccbt.toml:8](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L8)

#### Tiempos de Espera de Conexión

Configuración: [ccbt.toml:22-25](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L22-L25)

- Tiempo de espera de conexión: [ccbt.toml:22](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L22)
- Tiempo de espera de handshake: [ccbt.toml:23](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L23)
- Intervalo de keep alive: [ccbt.toml:24](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L24)
- Tiempo de espera de par: [ccbt.toml:25](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L25)

## Optimización de E/S de Disco

### Estrategia de Preasignación

Configuración: [ccbt.toml:59](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L59)

**Recomendaciones:**
- **SSD**: Usar "full" para mejor rendimiento
- **HDD**: Usar "sparse" para ahorrar espacio
- **Almacenamiento de red**: Usar "none" para evitar retrasos

Opción de archivos dispersos: [ccbt.toml:60](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L60)

Implementación: [ccbt/storage/disk_io.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Operaciones de E/S de disco

### Optimización de Escritura

Configuración: [ccbt.toml:63-64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L63-L64)

**Pautas de Ajuste:**
- **Almacenamiento rápido**: Aumentar tamaño de lote (128-256 KiB)
- **Almacenamiento lento**: Disminuir tamaño de lote (32-64 KiB)
- **Datos críticos**: Habilitar sync_writes
- **Rendimiento**: Deshabilitar sync_writes

Tamaño de lote de escritura: [ccbt.toml:63](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L63)

Tamaño de búfer de escritura: [ccbt.toml:64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L64)

Configuración de escrituras sincronizadas: [ccbt.toml:82](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L82)

Ensamblador de archivos: [ccbt/storage/file_assembler.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/file_assembler.py)

### Mapeo de Memoria

Configuración: [ccbt.toml:65-66](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L65-L66)

**Beneficios:**
- Lecturas más rápidas para piezas completadas
- Uso reducido de memoria
- Mejor caché del sistema operativo

**Consideraciones:**
- Requiere RAM suficiente
- Puede causar presión de memoria
- Mejor para cargas de trabajo intensivas en lectura

Usar MMAP: [ccbt.toml:65](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L65)

Tamaño de caché MMAP: [ccbt.toml:66](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L66)

Intervalo de limpieza de caché MMAP: [ccbt.toml:67](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L67)

### Características Avanzadas de E/S

#### io_uring (Linux)

Configuración: [ccbt.toml:84](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L84)

**Requisitos:**
- Kernel de Linux 5.1+
- Dispositivos de almacenamiento modernos
- Recursos del sistema suficientes

#### E/S Directa

Configuración: [ccbt.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L81)

**Casos de Uso:**
- Almacenamiento de alto rendimiento
- Omitir caché de páginas del sistema operativo
- Rendimiento consistente

Tamaño de lectura anticipada: [ccbt.toml:83](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L83)

## Selección de Estrategia

### Algoritmos de Selección de Piezas

Configuración: [ccbt.toml:101](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L101)

#### Rarest-First (Recomendado)

**Beneficios:**
- Salud óptima del enjambre
- Tiempos de finalización más rápidos
- Mejor cooperación entre pares

Implementación: [ccbt/piece/async_piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py) - Lógica de selección de piezas

Umbral rarest first: [ccbt.toml:107](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L107)

#### Secuencial

**Casos de Uso:**
- Archivos multimedia de transmisión
- Patrones de acceso secuencial
- Descargas basadas en prioridad

Ventana secuencial: [ccbt.toml:108](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L108)

Modo de transmisión: [ccbt.toml:104](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L104)

#### Round-Robin

**Casos de Uso:**
- Escenarios simples
- Depuración
- Compatibilidad heredada

Implementación: [ccbt/piece/piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/piece_manager.py)

### Optimización de Endgame

Configuración: [ccbt.toml:102-103](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L102-L103)

**Ajuste:**
- **Conexiones rápidas**: Umbral más bajo (0.85-0.9)
- **Conexiones lentas**: Umbral más alto (0.95-0.98)
- **Muchos pares**: Aumentar duplicados (3-5)
- **Pocos pares**: Disminuir duplicados (1-2)

Umbral de endgame: [ccbt.toml:103](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L103)

Duplicados de endgame: [ccbt.toml:102](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L102)

Capacidad del pipeline: [ccbt.toml:109](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L109)

### Prioridades de Piezas

Configuración: [ccbt.toml:112-113](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L112-L113)

Prioridad de primera pieza: [ccbt.toml:112](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L112)

Prioridad de última pieza: [ccbt.toml:113](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L113)

## Limitación de Velocidad

### Límites Globales

Configuración: [ccbt.toml:140-141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L140-L141)

Límite global de descarga: [ccbt.toml:140](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L140) (0 = ilimitado)

Límite global de carga: [ccbt.toml:141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L141) (0 = ilimitado)

Límites a nivel de red: [ccbt.toml:39-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L39-L42)

Implementación: [ccbt/security/rate_limiter.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/rate_limiter.py) - Lógica de limitación de velocidad

### Límites por Torrent

Establecer límites vía CLI usando [ccbt/cli/main.py:download](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L369) con las opciones `--download-limit` y `--upload-limit`.

Configuración por torrent: [ccbt.toml:144-145](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L144-L145)

Límites por par: [ccbt.toml:148](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L148)

### Configuración del Programador

Segmento de tiempo del programador: [ccbt.toml:151](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L151)

## Verificación de Hash

### Hilos de Trabajo

Configuración: [ccbt.toml:70](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L70)

**Pautas de Ajuste:**
- **Núcleos de CPU**: Coincidir o exceder el número de núcleos
- **Almacenamiento SSD**: Puede manejar más trabajadores
- **Almacenamiento HDD**: Limitar trabajadores (2-4)

Tamaño de fragmento de hash: [ccbt.toml:71](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L71)

Tamaño de lote de hash: [ccbt.toml:72](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L72)

Tamaño de cola de hash: [ccbt.toml:73](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L73)

Implementación: [ccbt/storage/disk_io.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Trabajadores de verificación de hash

## Gestión de Memoria

### Tamaños de Búfer

Búfer de escritura: [ccbt.toml:64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L64)

Lectura anticipada: [ccbt.toml:83](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L83)

### Configuración de Caché

Tamaño de caché: [ccbt.toml:78](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L78)

Caché MMAP: [ccbt.toml:66](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L66)

Tamaño de cola de disco: [ccbt.toml:77](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L77)

Trabajadores de disco: [ccbt.toml:76](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L76)

## Optimización a Nivel de Sistema

### Ajuste del Sistema de Archivos

Para optimizaciones a nivel de sistema, consulta la documentación de tu sistema operativo. Estas son recomendaciones generales que se aplican fuera de la configuración de ccBitTorrent.

### Ajuste de la Pila de Red

Para optimizaciones de la pila de red, consulta la documentación de tu sistema operativo. Estas son configuraciones a nivel de sistema que afectan el rendimiento general de la red.

## Monitoreo del Rendimiento

### Métricas Clave

Monitorea estas métricas clave vía Prometheus:

- **Velocidad de Descarga**: `ccbt_download_rate_bytes_per_second` - Ver [ccbt/utils/metrics.py:142](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/metrics.py#L142)
- **Velocidad de Carga**: `ccbt_upload_rate_bytes_per_second` - Ver [ccbt/utils/metrics.py:148](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/metrics.py#L148)
- **Pares Conectados**: Disponible vía MetricsCollector
- **Profundidad de Cola de Disco**: Disponible vía MetricsCollector - Ver [ccbt/monitoring/metrics_collector.py]
- **Profundidad de Cola de Hash**: Disponible vía MetricsCollector

Endpoint de métricas Prometheus: [ccbt/utils/metrics.py:179](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/metrics.py#L179)

### Perfilado de Rendimiento

Habilitar métricas: [ccbt.toml:164](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L164)

Puerto de métricas: [ccbt.toml:165](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L165)

Acceder a métricas en `http://localhost:9090/metrics` cuando esté habilitado.

Ver métricas vía CLI: [ccbt/cli/monitoring_commands.py:metrics](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L229)

## Solución de Problemas de Rendimiento

### Velocidades de Descarga Bajas

1. **Verificar conexiones de pares**:
   Lanzar panel Bitonic: [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L20)

2. **Verificar selección de piezas**:
   Configurar en [ccbt.toml:101](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L101)
   
   Implementación: [ccbt/piece/async_piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py)

3. **Aumentar profundidad del pipeline**:
   Configurar en [ccbt.toml:12](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L12)
   
   Implementación: [ccbt/peer/async_peer_connection.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/async_peer_connection.py)

4. **Verificar límites de velocidad**:
   Configuración: [ccbt.toml:140-141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L140-L141)
   
   Comando de estado CLI: [ccbt/cli/main.py:status](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L789)

### Alto Uso de CPU

1. **Reducir trabajadores de hash**:
   Configurar en [ccbt.toml:70](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L70)

2. **Deshabilitar mapeo de memoria**:
   Configurar en [ccbt.toml:65](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L65)

3. **Aumentar intervalos de actualización**:
   Intervalo de actualización de Bitonic: [ccbt/interface/terminal_dashboard.py:303](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L303)
   
   Configuración del panel: [ccbt.toml:189](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L189)

### Cuellos de Botella de E/S de Disco

1. **Habilitar escritura por lotes**:
   Configurar tamaño de lote de escritura: [ccbt.toml:63](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L63)
   
   Implementación: [ccbt/storage/disk_io.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/disk_io.py)

2. **Usar almacenamiento más rápido**:
   - Mover descargas a SSD
   - Usar RAID 0 para rendimiento

3. **Optimizar sistema de archivos**:
   - Usar sistema de archivos apropiado
   - Ajustar opciones de montaje

## Benchmarking

### Scripts de Benchmark

Los scripts de benchmark de rendimiento se encuentran en `tests/performance/`:

- Verificación de hash: `tests/performance/bench_hash_verify.py`
- E/S de disco: `tests/performance/bench_disk_io.py`
- Ensamblaje de piezas: `tests/performance/bench_piece_assembly.py`
- Rendimiento de loopback: `tests/performance/bench_loopback_throughput.py`
- Cifrado: `tests/performance/bench_encryption.py`

Ejecutar todos los benchmarks: [tests/scripts/bench_all.py](https://github.com/ccBittorrent/ccbt/blob/main/tests/scripts/bench_all.py)

Ejemplo de configuración de benchmark: [example-config-performance.toml](examples/example-config-performance.toml)

### Grabación de Benchmark

Los benchmarks se pueden grabar con diferentes modos para rastrear el rendimiento a lo largo del tiempo:

#### Modos de Grabación

- **`pre-commit`**: Graba durante ejecuciones de hook pre-commit (pruebas rápidas de humo)
- **`commit`**: Graba durante commits reales (benchmarks completos, grabados tanto en por-ejecución como en series temporales)
- **`both`**: Graba en contextos de pre-commit y commit
- **`auto`**: Detecta automáticamente el contexto (usa la variable de entorno `PRE_COMMIT`)
- **`none`**: Sin grabación (el benchmark se ejecuta pero no guarda resultados)

#### Ejecutar Benchmarks con Grabación

```bash
# Modo pre-commit (prueba rápida de humo)
uv run python tests/performance/bench_hash_verify.py --quick --record-mode=pre-commit

# Modo commit (benchmark completo)
uv run python tests/performance/bench_hash_verify.py --record-mode=commit

# Ambos modos
uv run python tests/performance/bench_hash_verify.py --record-mode=both

# Modo de auto-detección (predeterminado)
uv run python tests/performance/bench_hash_verify.py --record-mode=auto
```

#### Almacenamiento de Datos de Benchmark

Los resultados de benchmark se almacenan en dos formatos:

1. **Archivos por ejecución** (`docs/reports/benchmarks/runs/`):
   - Archivos JSON individuales para cada ejecución de benchmark
   - Formato de nombre de archivo: `{benchmark_name}-{timestamp}-{commit_hash_short}.json`
   - Contiene metadatos completos: hash de commit de git, rama, autor, información de plataforma, resultados

2. **Archivos de series temporales** (`docs/reports/benchmarks/timeseries/`):
   - Datos históricos agregados en formato JSON
   - Formato de nombre de archivo: `{benchmark_name}_timeseries.json`
   - Permite consultar fácilmente las tendencias de rendimiento a lo largo del tiempo

Para información detallada sobre consultar datos históricos e informes de benchmark, ver [Informes de Benchmark](reports/benchmarks/index.md).

### Artefactos de Prueba y Cobertura

Al ejecutar la suite completa de pruebas (pre-push/CI), los artefactos se emiten a:

- `tests/.reports/junit.xml` (informe JUnit)
- `tests/.reports/pytest.log` (registros de prueba)
- `coverage.xml` y `htmlcov/` (informes de cobertura)

Estos se integran con Codecov; las banderas en `dev/.codecov.yml` están alineadas con los subpaquetes `ccbt/` para atribuir la cobertura con precisión (ej., `peer`, `piece`, `protocols`, `extensions`). El informe HTML de cobertura se integra automáticamente en la documentación a través del plugin `mkdocs-coverage`, que lee desde `site/reports/htmlcov/` y lo renderiza en [reports/coverage.md](reports/coverage.md).

#### Artefactos de Benchmark Heredados

Los artefactos de benchmark heredados todavía se escriben en `site/reports/benchmarks/artifacts/` para compatibilidad hacia atrás cuando se usa el argumento `--output-dir`. Sin embargo, se recomienda el nuevo sistema de grabación para rastrear el rendimiento a lo largo del tiempo.

## Mejores Prácticas

1. **Comenzar con valores predeterminados**: Comenzar con configuraciones predeterminadas de [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
2. **Medir línea base**: Establecer línea base de rendimiento usando [ccbt/cli/monitoring_commands.py:metrics](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L229)
3. **Cambiar una configuración**: Modificar una configuración a la vez en [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
4. **Probar a fondo**: Verificar mejoras
5. **Monitorear recursos**: Observar uso de CPU, memoria, disco vía [Bitonic](bitonic.md)
6. **Documentar cambios**: Mantener registro de configuraciones efectivas

## Plantillas de Configuración

### Configuración de Alto Rendimiento

Referencia de plantilla de configuración de alto rendimiento: [ccbt/config/config_templates.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_templates.py)

Configuraciones clave:
- Red: [ccbt.toml:11-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L11-L42)
- Disco: [ccbt.toml:57-85](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L57-L85)
- Estrategia: [ccbt.toml:99-114](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L99-L114)

Ejemplo: [example-config-performance.toml](examples/example-config-performance.toml)

### Configuración de Recursos Bajos

Referencia de plantilla de configuración de recursos bajos: [ccbt/config/config_templates.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_templates.py)

Configuraciones clave:
- Red: [ccbt.toml:6-7](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L6-L7) - Reducir límites de pares
- Disco: [ccbt.toml:59-65](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L59-L65) - Usar preasignación dispersa, deshabilitar MMAP
- Estrategia: [ccbt.toml:101](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L101) - Rarest-first sigue siendo óptimo

Para opciones de configuración más detalladas, ver la documentación de [Configuración](configuration.md).
