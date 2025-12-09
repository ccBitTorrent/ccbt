# btbt CLI - Referencia de Comandos

**btbt** es la interfaz de línea de comandos mejorada para ccBitTorrent, proporcionando control completo sobre operaciones de torrent, monitoreo, configuración y características avanzadas.

- Punto de entrada: [ccbt/cli/main.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1463)
- Definido en: [pyproject.toml:80](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L80)
- Grupo CLI principal: [ccbt/cli/main.py:cli](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L243)

## Comandos Básicos

### download

Descargar un archivo torrent.

Implementación: [ccbt/cli/main.py:download](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L369)

Uso:
```bash
uv run btbt download <torrent_file> [options]
```

Opciones:
- `--output <dir>`: Directorio de salida
- `--interactive`: Modo interactivo
- `--monitor`: Modo de monitoreo
- `--resume`: Reanudar desde punto de control
- `--no-checkpoint`: Deshabilitar puntos de control
- `--checkpoint-dir <dir>`: Directorio de puntos de control
- `--files <indices...>`: Seleccionar archivos específicos para descargar (se puede especificar múltiples veces, ej., `--files 0 --files 1`)
- `--file-priority <spec>`: Establecer prioridad de archivo como `file_index=priority` (ej., `0=high,1=low`). Se puede especificar múltiples veces.

Opciones de red (ver [ccbt/cli/main.py:_apply_network_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L67)):
- `--listen-port <int>`: Puerto de escucha
- `--max-peers <int>`: Máximo de pares globales
- `--max-peers-per-torrent <int>`: Máximo de pares por torrent
- `--pipeline-depth <int>`: Profundidad del pipeline de solicitudes
- `--block-size-kib <int>`: Tamaño de bloque en KiB
- `--connection-timeout <float>`: Tiempo de espera de conexión
- `--global-down-kib <int>`: Límite global de descarga (KiB/s)
- `--global-up-kib <int>`: Límite global de carga (KiB/s)

Opciones de disco (ver [ccbt/cli/main.py:_apply_disk_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L179)):
- `--hash-workers <int>`: Número de trabajadores de verificación de hash
- `--disk-workers <int>`: Número de trabajadores de E/S de disco
- `--use-mmap`: Habilitar mapeo de memoria
- `--no-mmap`: Deshabilitar mapeo de memoria
- `--write-batch-kib <int>`: Tamaño de lote de escritura en KiB
- `--write-buffer-kib <int>`: Tamaño de búfer de escritura en KiB
- `--preallocate <str>`: Estrategia de preasignación (none|sparse|full)

Opciones de estrategia (ver [ccbt/cli/main.py:_apply_strategy_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L151)):
- `--piece-selection <str>`: Estrategia de selección de piezas (round_robin|rarest_first|sequential)
- `--endgame-duplicates <int>`: Solicitudes duplicadas de endgame
- `--endgame-threshold <float>`: Umbral de endgame
- `--streaming`: Habilitar modo de transmisión

Opciones de descubrimiento (ver [ccbt/cli/main.py:_apply_discovery_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L123)):
- `--enable-dht`: Habilitar DHT
- `--disable-dht`: Deshabilitar DHT
- `--enable-pex`: Habilitar PEX
- `--disable-pex`: Deshabilitar PEX
- `--enable-http-trackers`: Habilitar trackers HTTP
- `--disable-http-trackers`: Deshabilitar trackers HTTP
- `--enable-udp-trackers`: Habilitar trackers UDP
- `--disable-udp-trackers`: Deshabilitar trackers UDP

Opciones de observabilidad (ver [ccbt/cli/main.py:_apply_observability_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L217)):
- `--log-level <str>`: Nivel de registro (DEBUG|INFO|WARNING|ERROR|CRITICAL)
- `--log-file <path>`: Ruta del archivo de registro
- `--enable-metrics`: Habilitar recopilación de métricas
- `--disable-metrics`: Deshabilitar recopilación de métricas
- `--metrics-port <int>`: Puerto de métricas

### magnet

Descargar desde un enlace magnet.

Implementación: [ccbt/cli/main.py:magnet](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L608)

Uso:
```bash
uv run btbt magnet <magnet_link> [options]
```

Opciones: Igual que el comando `download`.

### interactive

Iniciar modo CLI interactivo.

Implementación: [ccbt/cli/main.py:interactive](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L767)

Uso:
```bash
uv run btbt interactive
```

CLI interactivo: [ccbt/cli/interactive.py:InteractiveCLI](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/interactive.py#L41)

### status

Mostrar el estado de la sesión actual.

Implementación: [ccbt/cli/main.py:status](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L789)

Uso:
```bash
uv run btbt status
```

## Comandos de Puntos de Control

Grupo de gestión de puntos de control: [ccbt/cli/main.py:checkpoints](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L849)

### checkpoints list

Listar todos los puntos de control disponibles.

Implementación: [ccbt/cli/main.py:list_checkpoints](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L863)

Uso:
```bash
uv run btbt checkpoints list [--format json|table]
```

### checkpoints clean

Limpiar puntos de control antiguos.

Implementación: [ccbt/cli/main.py:clean_checkpoints](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L930)

Uso:
```bash
uv run btbt checkpoints clean [--days <n>] [--dry-run]
```

### checkpoints delete

Eliminar un punto de control específico.

Implementación: [ccbt/cli/main.py:delete_checkpoint](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L978)

Uso:
```bash
uv run btbt checkpoints delete <info_hash>
```

### checkpoints verify

Verificar un punto de control.

Implementación: [ccbt/cli/main.py:verify_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1016)

Uso:
```bash
uv run btbt checkpoints verify <info_hash>
```

### checkpoints export

Exportar punto de control a archivo.

Implementación: [ccbt/cli/main.py:export_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1058)

Uso:
```bash
uv run btbt checkpoints export <info_hash> [--format json|binary] [--output <path>]
```

### checkpoints backup

Hacer copia de seguridad del punto de control a una ubicación.

Implementación: [ccbt/cli/main.py:backup_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1099)

Uso:
```bash
uv run btbt checkpoints backup <info_hash> <destination> [--compress] [--encrypt]
```

### checkpoints restore

Restaurar punto de control desde copia de seguridad.

Implementación: [ccbt/cli/main.py:restore_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1138)

Uso:
```bash
uv run btbt checkpoints restore <backup_file> [--info-hash <hash>]
```

### checkpoints migrate

Migrar punto de control entre formatos.

Implementación: [ccbt/cli/main.py:migrate_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1173)

Uso:
```bash
uv run btbt checkpoints migrate <info_hash> --from <format> --to <format>
```

### resume

Reanudar descarga desde punto de control.

Implementación: [ccbt/cli/main.py:resume](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1204)

Uso:
```bash
uv run btbt resume <info_hash> [--output <dir>] [--interactive]
```

## Comandos de Monitoreo

Grupo de comandos de monitoreo: [ccbt/cli/monitoring_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py)

### dashboard

Iniciar panel de monitoreo de terminal (Bitonic).

Implementación: [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L20)

Uso:
```bash
uv run btbt dashboard [--refresh <seconds>] [--rules <path>]
```

Ver [Guía de Bitonic](bitonic.md) para uso detallado.

### alerts

Gestionar reglas de alerta y alertas activas.

Implementación: [ccbt/cli/monitoring_commands.py:alerts](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L48)

Uso:
```bash
# Listar reglas de alerta
uv run btbt alerts --list

# Listar alertas activas
uv run btbt alerts --list-active

# Agregar regla de alerta
uv run btbt alerts --add --name <name> --metric <metric> --condition "<condition>" --severity <severity>

# Eliminar regla de alerta
uv run btbt alerts --remove --name <name>

# Limpiar todas las alertas activas
uv run btbt alerts --clear-active

# Probar regla de alerta
uv run btbt alerts --test --name <name> --value <value>

# Cargar reglas desde archivo
uv run btbt alerts --load <path>

# Guardar reglas en archivo
uv run btbt alerts --save <path>
```

Ver la [Referencia de API](API.md#monitoring) para más información.

### metrics

Recopilar y exportar métricas.

Implementación: [ccbt/cli/monitoring_commands.py:metrics](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L229)

Uso:
```bash
uv run btbt metrics [--format json|prometheus] [--output <path>] [--duration <seconds>] [--interval <seconds>] [--include-system] [--include-performance]
```

Ejemplos:
```bash
# Exportar métricas JSON
uv run btbt metrics --format json --include-system --include-performance

# Exportar formato Prometheus
uv run btbt metrics --format prometheus > metrics.txt
```

Ver la [Referencia de API](API.md#monitoring) para más información.

## Comandos de Selección de Archivos

Grupo de comandos de selección de archivos: [ccbt/cli/file_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py)

Gestionar selección de archivos y prioridades para torrents multiarchivo.

### files list

Listar todos los archivos en un torrent con su estado de selección, prioridades y progreso de descarga.

Implementación: [ccbt/cli/file_commands.py:files_list](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L28)

Uso:
```bash
uv run btbt files list <info_hash>
```

La salida incluye:
- Índice y nombre del archivo
- Tamaño del archivo
- Estado de selección (seleccionado/deseleccionado)
- Nivel de prioridad
- Progreso de descarga

### files select

Seleccionar uno o más archivos para descargar.

Implementación: [ccbt/cli/file_commands.py:files_select](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L72)

Uso:
```bash
uv run btbt files select <info_hash> <file_index> [<file_index> ...]
```

Ejemplos:
```bash
# Seleccionar archivos 0, 2 y 5
uv run btbt files select abc123... 0 2 5

# Seleccionar un solo archivo
uv run btbt files select abc123... 0
```

### files deselect

Deseleccionar uno o más archivos de la descarga.

Implementación: [ccbt/cli/file_commands.py:files_deselect](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L108)

Uso:
```bash
uv run btbt files deselect <info_hash> <file_index> [<file_index> ...]
```

### files select-all

Seleccionar todos los archivos del torrent.

Implementación: [ccbt/cli/file_commands.py:files_select_all](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L144)

Uso:
```bash
uv run btbt files select-all <info_hash>
```

### files deselect-all

Deseleccionar todos los archivos del torrent.

Implementación: [ccbt/cli/file_commands.py:files_deselect_all](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L161)

Uso:
```bash
uv run btbt files deselect-all <info_hash>
```

### files priority

Establecer prioridad para un archivo específico.

Implementación: [ccbt/cli/file_commands.py:files_priority](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L178)

Uso:
```bash
uv run btbt files priority <info_hash> <file_index> <priority>
```

Niveles de prioridad:
- `do_not_download`: No descargar (equivalente a deseleccionado)
- `low`: Prioridad baja
- `normal`: Prioridad normal (predeterminado)
- `high`: Prioridad alta
- `maximum`: Prioridad máxima

Ejemplos:
```bash
# Establecer archivo 0 a prioridad alta
uv run btbt files priority abc123... 0 high

# Establecer archivo 2 a prioridad máxima
uv run btbt files priority abc123... 2 maximum
```

## Comandos de Configuración

Grupo de comandos de configuración: [ccbt/cli/config_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/config_commands.py)

### config

Gestionar configuración.

Implementación: [ccbt/cli/main.py:config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L810)

Uso:
```bash
uv run btbt config [subcommand]
```

Comandos de configuración extendidos: [ccbt/cli/config_commands_extended.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/config_commands_extended.py)

Ver [Guía de Configuración](configuration.md) para opciones de configuración detalladas.

## Comandos Avanzados

Grupo de comandos avanzados: [ccbt/cli/advanced_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py)

### performance

Análisis de rendimiento y benchmarking.

Implementación: [ccbt/cli/advanced_commands.py:performance](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L73)

Uso:
```bash
uv run btbt performance [--analyze] [--benchmark]
```

### security

Análisis y validación de seguridad.

Implementación: [ccbt/cli/advanced_commands.py:security](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L170)

Uso:
```bash
uv run btbt security [options]
```

### recover

Operaciones de recuperación.

Implementación: [ccbt/cli/advanced_commands.py:recover](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L209)

Uso:
```bash
uv run btbt recover [options]
```

### test

Ejecutar pruebas y diagnósticos.

Implementación: [ccbt/cli/advanced_commands.py:test](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L248)

Uso:
```bash
uv run btbt test [options]
```

## Opciones de Línea de Comandos

### Opciones Globales

Opciones globales definidas en: [ccbt/cli/main.py:cli](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L243)

- `--config <path>`: Ruta del archivo de configuración
- `--verbose`: Salida detallada
- `--debug`: Modo de depuración

### Sobrescrituras CLI

Todas las opciones CLI sobrescriben la configuración en este orden:
1. Valores predeterminados de [ccbt/config/config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)
2. Archivo de configuración ([ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml))
3. Variables de entorno ([env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example))
4. Argumentos CLI

Implementación de sobrescritura: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L55)

## Ejemplos

### Descarga Básica
```bash
uv run btbt download movie.torrent
```

### Descarga con Opciones
```bash
uv run btbt download movie.torrent \
  --listen-port 7001 \
  --enable-dht \
  --use-mmap \
  --download-limit 1024 \
  --upload-limit 512
```

### Descarga Selectiva de Archivos
```bash
# Descargar solo archivos específicos
uv run btbt download torrent.torrent --files 0 --files 2 --files 5

# Descargar con prioridades de archivo
uv run btbt download torrent.torrent \
  --file-priority 0=high \
  --file-priority 1=maximum \
  --file-priority 2=low

# Combinado: seleccionar archivos y establecer prioridades
uv run btbt download torrent.torrent \
  --files 0 1 2 \
  --file-priority 0=maximum \
  --file-priority 1=high
```

### Descarga desde Magnet
```bash
uv run btbt magnet "magnet:?xt=urn:btih:..." \
  --download-limit 1024 \
  --upload-limit 256
```

### Gestión de Selección de Archivos
```bash
# Listar archivos en un torrent
uv run btbt files list abc123def456789...

# Seleccionar archivos específicos después de que comience la descarga
uv run btbt files select abc123... 3 4

# Establecer prioridades de archivo
uv run btbt files priority abc123... 0 high
uv run btbt files priority abc123... 2 maximum

# Seleccionar/deseleccionar todos los archivos
uv run btbt files select-all abc123...
uv run btbt files deselect-all abc123...
```

### Gestión de Puntos de Control
```bash
# Listar puntos de control
uv run btbt checkpoints list --format json

# Exportar punto de control
uv run btbt checkpoints export <infohash> --format json --output checkpoint.json

# Limpiar puntos de control antiguos
uv run btbt checkpoints clean --days 7
```

### Monitoreo
```bash
# Iniciar panel
uv run btbt dashboard --refresh 2.0

# Agregar regla de alerta
uv run btbt alerts --add --name cpu_high --metric system.cpu --condition "value > 80" --severity warning

# Exportar métricas
uv run btbt metrics --format json --include-system --include-performance
```

## Obtener Ayuda

Obtener ayuda para cualquier comando:
```bash
uv run btbt --help
uv run btbt <command> --help
```

Para más información:
- [Guía de Bitonic](bitonic.md) - Panel de terminal
- [Guía de Configuración](configuration.md) - Opciones de configuración
- [Referencia de API](API.md#monitoring) - Monitoreo y métricas
- [Ajuste de Rendimiento](performance.md) - Guía de optimización






**btbt** es la interfaz de línea de comandos mejorada para ccBitTorrent, proporcionando control completo sobre operaciones de torrent, monitoreo, configuración y características avanzadas.

- Punto de entrada: [ccbt/cli/main.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1463)
- Definido en: [pyproject.toml:80](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L80)
- Grupo CLI principal: [ccbt/cli/main.py:cli](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L243)

## Comandos Básicos

### download

Descargar un archivo torrent.

Implementación: [ccbt/cli/main.py:download](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L369)

Uso:
```bash
uv run btbt download <torrent_file> [options]
```

Opciones:
- `--output <dir>`: Directorio de salida
- `--interactive`: Modo interactivo
- `--monitor`: Modo de monitoreo
- `--resume`: Reanudar desde punto de control
- `--no-checkpoint`: Deshabilitar puntos de control
- `--checkpoint-dir <dir>`: Directorio de puntos de control
- `--files <indices...>`: Seleccionar archivos específicos para descargar (se puede especificar múltiples veces, ej., `--files 0 --files 1`)
- `--file-priority <spec>`: Establecer prioridad de archivo como `file_index=priority` (ej., `0=high,1=low`). Se puede especificar múltiples veces.

Opciones de red (ver [ccbt/cli/main.py:_apply_network_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L67)):
- `--listen-port <int>`: Puerto de escucha
- `--max-peers <int>`: Máximo de pares globales
- `--max-peers-per-torrent <int>`: Máximo de pares por torrent
- `--pipeline-depth <int>`: Profundidad del pipeline de solicitudes
- `--block-size-kib <int>`: Tamaño de bloque en KiB
- `--connection-timeout <float>`: Tiempo de espera de conexión
- `--global-down-kib <int>`: Límite global de descarga (KiB/s)
- `--global-up-kib <int>`: Límite global de carga (KiB/s)

Opciones de disco (ver [ccbt/cli/main.py:_apply_disk_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L179)):
- `--hash-workers <int>`: Número de trabajadores de verificación de hash
- `--disk-workers <int>`: Número de trabajadores de E/S de disco
- `--use-mmap`: Habilitar mapeo de memoria
- `--no-mmap`: Deshabilitar mapeo de memoria
- `--write-batch-kib <int>`: Tamaño de lote de escritura en KiB
- `--write-buffer-kib <int>`: Tamaño de búfer de escritura en KiB
- `--preallocate <str>`: Estrategia de preasignación (none|sparse|full)

Opciones de estrategia (ver [ccbt/cli/main.py:_apply_strategy_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L151)):
- `--piece-selection <str>`: Estrategia de selección de piezas (round_robin|rarest_first|sequential)
- `--endgame-duplicates <int>`: Solicitudes duplicadas de endgame
- `--endgame-threshold <float>`: Umbral de endgame
- `--streaming`: Habilitar modo de transmisión

Opciones de descubrimiento (ver [ccbt/cli/main.py:_apply_discovery_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L123)):
- `--enable-dht`: Habilitar DHT
- `--disable-dht`: Deshabilitar DHT
- `--enable-pex`: Habilitar PEX
- `--disable-pex`: Deshabilitar PEX
- `--enable-http-trackers`: Habilitar trackers HTTP
- `--disable-http-trackers`: Deshabilitar trackers HTTP
- `--enable-udp-trackers`: Habilitar trackers UDP
- `--disable-udp-trackers`: Deshabilitar trackers UDP

Opciones de observabilidad (ver [ccbt/cli/main.py:_apply_observability_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L217)):
- `--log-level <str>`: Nivel de registro (DEBUG|INFO|WARNING|ERROR|CRITICAL)
- `--log-file <path>`: Ruta del archivo de registro
- `--enable-metrics`: Habilitar recopilación de métricas
- `--disable-metrics`: Deshabilitar recopilación de métricas
- `--metrics-port <int>`: Puerto de métricas

### magnet

Descargar desde un enlace magnet.

Implementación: [ccbt/cli/main.py:magnet](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L608)

Uso:
```bash
uv run btbt magnet <magnet_link> [options]
```

Opciones: Igual que el comando `download`.

### interactive

Iniciar modo CLI interactivo.

Implementación: [ccbt/cli/main.py:interactive](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L767)

Uso:
```bash
uv run btbt interactive
```

CLI interactivo: [ccbt/cli/interactive.py:InteractiveCLI](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/interactive.py#L41)

### status

Mostrar el estado de la sesión actual.

Implementación: [ccbt/cli/main.py:status](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L789)

Uso:
```bash
uv run btbt status
```

## Comandos de Puntos de Control

Grupo de gestión de puntos de control: [ccbt/cli/main.py:checkpoints](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L849)

### checkpoints list

Listar todos los puntos de control disponibles.

Implementación: [ccbt/cli/main.py:list_checkpoints](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L863)

Uso:
```bash
uv run btbt checkpoints list [--format json|table]
```

### checkpoints clean

Limpiar puntos de control antiguos.

Implementación: [ccbt/cli/main.py:clean_checkpoints](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L930)

Uso:
```bash
uv run btbt checkpoints clean [--days <n>] [--dry-run]
```

### checkpoints delete

Eliminar un punto de control específico.

Implementación: [ccbt/cli/main.py:delete_checkpoint](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L978)

Uso:
```bash
uv run btbt checkpoints delete <info_hash>
```

### checkpoints verify

Verificar un punto de control.

Implementación: [ccbt/cli/main.py:verify_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1016)

Uso:
```bash
uv run btbt checkpoints verify <info_hash>
```

### checkpoints export

Exportar punto de control a archivo.

Implementación: [ccbt/cli/main.py:export_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1058)

Uso:
```bash
uv run btbt checkpoints export <info_hash> [--format json|binary] [--output <path>]
```

### checkpoints backup

Hacer copia de seguridad del punto de control a una ubicación.

Implementación: [ccbt/cli/main.py:backup_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1099)

Uso:
```bash
uv run btbt checkpoints backup <info_hash> <destination> [--compress] [--encrypt]
```

### checkpoints restore

Restaurar punto de control desde copia de seguridad.

Implementación: [ccbt/cli/main.py:restore_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1138)

Uso:
```bash
uv run btbt checkpoints restore <backup_file> [--info-hash <hash>]
```

### checkpoints migrate

Migrar punto de control entre formatos.

Implementación: [ccbt/cli/main.py:migrate_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1173)

Uso:
```bash
uv run btbt checkpoints migrate <info_hash> --from <format> --to <format>
```

### resume

Reanudar descarga desde punto de control.

Implementación: [ccbt/cli/main.py:resume](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1204)

Uso:
```bash
uv run btbt resume <info_hash> [--output <dir>] [--interactive]
```

## Comandos de Monitoreo

Grupo de comandos de monitoreo: [ccbt/cli/monitoring_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py)

### dashboard

Iniciar panel de monitoreo de terminal (Bitonic).

Implementación: [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L20)

Uso:
```bash
uv run btbt dashboard [--refresh <seconds>] [--rules <path>]
```

Ver [Guía de Bitonic](bitonic.md) para uso detallado.

### alerts

Gestionar reglas de alerta y alertas activas.

Implementación: [ccbt/cli/monitoring_commands.py:alerts](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L48)

Uso:
```bash
# Listar reglas de alerta
uv run btbt alerts --list

# Listar alertas activas
uv run btbt alerts --list-active

# Agregar regla de alerta
uv run btbt alerts --add --name <name> --metric <metric> --condition "<condition>" --severity <severity>

# Eliminar regla de alerta
uv run btbt alerts --remove --name <name>

# Limpiar todas las alertas activas
uv run btbt alerts --clear-active

# Probar regla de alerta
uv run btbt alerts --test --name <name> --value <value>

# Cargar reglas desde archivo
uv run btbt alerts --load <path>

# Guardar reglas en archivo
uv run btbt alerts --save <path>
```

Ver la [Referencia de API](API.md#monitoring) para más información.

### metrics

Recopilar y exportar métricas.

Implementación: [ccbt/cli/monitoring_commands.py:metrics](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L229)

Uso:
```bash
uv run btbt metrics [--format json|prometheus] [--output <path>] [--duration <seconds>] [--interval <seconds>] [--include-system] [--include-performance]
```

Ejemplos:
```bash
# Exportar métricas JSON
uv run btbt metrics --format json --include-system --include-performance

# Exportar formato Prometheus
uv run btbt metrics --format prometheus > metrics.txt
```

Ver la [Referencia de API](API.md#monitoring) para más información.

## Comandos de Selección de Archivos

Grupo de comandos de selección de archivos: [ccbt/cli/file_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py)

Gestionar selección de archivos y prioridades para torrents multiarchivo.

### files list

Listar todos los archivos en un torrent con su estado de selección, prioridades y progreso de descarga.

Implementación: [ccbt/cli/file_commands.py:files_list](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L28)

Uso:
```bash
uv run btbt files list <info_hash>
```

La salida incluye:
- Índice y nombre del archivo
- Tamaño del archivo
- Estado de selección (seleccionado/deseleccionado)
- Nivel de prioridad
- Progreso de descarga

### files select

Seleccionar uno o más archivos para descargar.

Implementación: [ccbt/cli/file_commands.py:files_select](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L72)

Uso:
```bash
uv run btbt files select <info_hash> <file_index> [<file_index> ...]
```

Ejemplos:
```bash
# Seleccionar archivos 0, 2 y 5
uv run btbt files select abc123... 0 2 5

# Seleccionar un solo archivo
uv run btbt files select abc123... 0
```

### files deselect

Deseleccionar uno o más archivos de la descarga.

Implementación: [ccbt/cli/file_commands.py:files_deselect](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L108)

Uso:
```bash
uv run btbt files deselect <info_hash> <file_index> [<file_index> ...]
```

### files select-all

Seleccionar todos los archivos del torrent.

Implementación: [ccbt/cli/file_commands.py:files_select_all](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L144)

Uso:
```bash
uv run btbt files select-all <info_hash>
```

### files deselect-all

Deseleccionar todos los archivos del torrent.

Implementación: [ccbt/cli/file_commands.py:files_deselect_all](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L161)

Uso:
```bash
uv run btbt files deselect-all <info_hash>
```

### files priority

Establecer prioridad para un archivo específico.

Implementación: [ccbt/cli/file_commands.py:files_priority](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L178)

Uso:
```bash
uv run btbt files priority <info_hash> <file_index> <priority>
```

Niveles de prioridad:
- `do_not_download`: No descargar (equivalente a deseleccionado)
- `low`: Prioridad baja
- `normal`: Prioridad normal (predeterminado)
- `high`: Prioridad alta
- `maximum`: Prioridad máxima

Ejemplos:
```bash
# Establecer archivo 0 a prioridad alta
uv run btbt files priority abc123... 0 high

# Establecer archivo 2 a prioridad máxima
uv run btbt files priority abc123... 2 maximum
```

## Comandos de Configuración

Grupo de comandos de configuración: [ccbt/cli/config_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/config_commands.py)

### config

Gestionar configuración.

Implementación: [ccbt/cli/main.py:config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L810)

Uso:
```bash
uv run btbt config [subcommand]
```

Comandos de configuración extendidos: [ccbt/cli/config_commands_extended.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/config_commands_extended.py)

Ver [Guía de Configuración](configuration.md) para opciones de configuración detalladas.

## Comandos Avanzados

Grupo de comandos avanzados: [ccbt/cli/advanced_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py)

### performance

Análisis de rendimiento y benchmarking.

Implementación: [ccbt/cli/advanced_commands.py:performance](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L73)

Uso:
```bash
uv run btbt performance [--analyze] [--benchmark]
```

### security

Análisis y validación de seguridad.

Implementación: [ccbt/cli/advanced_commands.py:security](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L170)

Uso:
```bash
uv run btbt security [options]
```

### recover

Operaciones de recuperación.

Implementación: [ccbt/cli/advanced_commands.py:recover](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L209)

Uso:
```bash
uv run btbt recover [options]
```

### test

Ejecutar pruebas y diagnósticos.

Implementación: [ccbt/cli/advanced_commands.py:test](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L248)

Uso:
```bash
uv run btbt test [options]
```

## Opciones de Línea de Comandos

### Opciones Globales

Opciones globales definidas en: [ccbt/cli/main.py:cli](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L243)

- `--config <path>`: Ruta del archivo de configuración
- `--verbose`: Salida detallada
- `--debug`: Modo de depuración

### Sobrescrituras CLI

Todas las opciones CLI sobrescriben la configuración en este orden:
1. Valores predeterminados de [ccbt/config/config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)
2. Archivo de configuración ([ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml))
3. Variables de entorno ([env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example))
4. Argumentos CLI

Implementación de sobrescritura: [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L55)

## Ejemplos

### Descarga Básica
```bash
uv run btbt download movie.torrent
```

### Descarga con Opciones
```bash
uv run btbt download movie.torrent \
  --listen-port 7001 \
  --enable-dht \
  --use-mmap \
  --download-limit 1024 \
  --upload-limit 512
```

### Descarga Selectiva de Archivos
```bash
# Descargar solo archivos específicos
uv run btbt download torrent.torrent --files 0 --files 2 --files 5

# Descargar con prioridades de archivo
uv run btbt download torrent.torrent \
  --file-priority 0=high \
  --file-priority 1=maximum \
  --file-priority 2=low

# Combinado: seleccionar archivos y establecer prioridades
uv run btbt download torrent.torrent \
  --files 0 1 2 \
  --file-priority 0=maximum \
  --file-priority 1=high
```

### Descarga desde Magnet
```bash
uv run btbt magnet "magnet:?xt=urn:btih:..." \
  --download-limit 1024 \
  --upload-limit 256
```

### Gestión de Selección de Archivos
```bash
# Listar archivos en un torrent
uv run btbt files list abc123def456789...

# Seleccionar archivos específicos después de que comience la descarga
uv run btbt files select abc123... 3 4

# Establecer prioridades de archivo
uv run btbt files priority abc123... 0 high
uv run btbt files priority abc123... 2 maximum

# Seleccionar/deseleccionar todos los archivos
uv run btbt files select-all abc123...
uv run btbt files deselect-all abc123...
```

### Gestión de Puntos de Control
```bash
# Listar puntos de control
uv run btbt checkpoints list --format json

# Exportar punto de control
uv run btbt checkpoints export <infohash> --format json --output checkpoint.json

# Limpiar puntos de control antiguos
uv run btbt checkpoints clean --days 7
```

### Monitoreo
```bash
# Iniciar panel
uv run btbt dashboard --refresh 2.0

# Agregar regla de alerta
uv run btbt alerts --add --name cpu_high --metric system.cpu --condition "value > 80" --severity warning

# Exportar métricas
uv run btbt metrics --format json --include-system --include-performance
```

## Obtener Ayuda

Obtener ayuda para cualquier comando:
```bash
uv run btbt --help
uv run btbt <command> --help
```

Para más información:
- [Guía de Bitonic](bitonic.md) - Panel de terminal
- [Guía de Configuración](configuration.md) - Opciones de configuración
- [Referencia de API](API.md#monitoring) - Monitoreo y métricas
- [Ajuste de Rendimiento](performance.md) - Guía de optimización




























































































































































































