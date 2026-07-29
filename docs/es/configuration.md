# Guía de Configuración

ccBitTorrent utiliza un sistema de configuración completo con soporte TOML, validación, recarga en caliente y carga jerárquica desde múltiples fuentes.

Sistema de configuración: [ccbt/config/config.py:ConfigManager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L40)

## Fuentes de Configuración y Precedencia

La configuración se carga en este orden (las fuentes posteriores sobrescriben las anteriores):

1. **Valores Predeterminados**: Valores predeterminados integrados de [ccbt/models.py:Config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)
2. **Archivo de Configuración**: `ccbt.toml` en el directorio actual o `~/.config/ccbt/ccbt.toml`. Ver [ccbt/config/config.py:_find_config_file](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L55)
3. **Variables de Entorno**: Variables con prefijo `CCBT_*`. Ver [env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
4. **Argumentos CLI**: Sobrescrituras de línea de comandos. Ver [ccbt/cli/overrides.py:apply_cli_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/overrides.py#L1) {#cli-overrides}
5. **Por Torrent - Valores Predeterminados**: Valores predeterminados globales para opciones por torrent. Ver sección [Configuración por Torrent](#per-torrent-configuration)
6. **Por Torrent - Sobrescrituras**: Configuraciones individuales de torrent (definidas via CLI, TUI o programáticamente)

Carga de configuración: [ccbt/config/config.py:_load_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L76)

### Resolución de Rutas en Windows {#daemon-home-dir}

**CRÍTICO**: Use el ayudante `_get_daemon_home_dir()` de `ccbt/daemon/daemon_manager.py` para todas las rutas relacionadas con el demonio.

**Por qué**: Windows puede resolver `Path.home()` o `os.path.expanduser("~")` de manera diferente en diferentes procesos, especialmente con espacios en los nombres de usuario.

**Patrón**: El ayudante intenta múltiples métodos (`expanduser`, `USERPROFILE`, `HOME`, `Path.home()`) y usa `Path.resolve()` para la ruta canónica.

**Uso**: Use siempre el ayudante en lugar de `Path.home()` o `os.path.expanduser("~")` directamente para archivos PID del demonio, directorios de estado, archivos de configuración.

**Archivos afectados**: `DaemonManager`, `StateManager`, `IPCClient`, cualquier código que lea/escriba el archivo PID del demonio o el estado.

**Resultado**: Asegura que el demonio y la CLI usen la misma ruta canónica, evitando fallos de detección.

Implementación: [ccbt/daemon/daemon_manager.py:_get_daemon_home_dir](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/daemon_manager.py#L25)

## Archivo de Configuración

### Configuración Predeterminada

Consulta el archivo de configuración predeterminado: [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

La configuración está organizada en secciones:

### Configuración de Red

Configuración de red: [ccbt.toml:4-43](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L4-L43)

- Límites de conexión: [ccbt.toml:6-8](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L6-L8)
- Pipeline de solicitudes: [ccbt.toml:11-14](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L11-L14)
- Ajuste de socket: [ccbt.toml:17-19](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L17-L19)
- Timeouts: [ccbt.toml:22-26](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L22-L26)
- Configuración de escucha: [ccbt.toml:29-31](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L29-L31)
- Protocolos de transporte: [ccbt.toml:34-36](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L34-L36)
- Límites de velocidad: [ccbt.toml:39-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L39-L42)
- Estrategia de choking: [ccbt.toml:45-47](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L45-L47)
- Configuración de tracker: [ccbt.toml:50-54](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L50-L54)

Modelo de configuración de red: [ccbt/models.py:NetworkConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuración de Disco

Configuración de disco: [ccbt.toml:57-96](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L57-L96)

- Preasignación: [ccbt.toml:59-60](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L59-L60)
- Optimización de escritura: [ccbt.toml:63-67](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L63-L67)
- Verificación de hash: [ccbt.toml:70-73](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L70-L73)
- Threading de I/O: [ccbt.toml:76-78](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L76-L78)
- Configuración avanzada: [ccbt.toml:81-85](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L81-L85)
- Configuración del servicio de almacenamiento: [ccbt.toml:87-89](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb`: Límite máximo de tamaño de archivo en MB para el servicio de almacenamiento (0 o None = ilimitado, máximo 1048576 = 1TB). Previene escrituras de disco ilimitadas durante las pruebas y puede configurarse para uso en producción.
- Configuración de checkpoint: [ccbt.toml:91-96](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L91-L96)

Modelo de configuración de disco: [ccbt/models.py:DiskConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuración de Estrategia

Configuración de estrategia: [ccbt.toml:99-114](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L99-L114)

- Selección de piezas: [ccbt.toml:101-104](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L101-L104)
- Estrategia avanzada: [ccbt.toml:107-109](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L107-L109)
- Prioridades de piezas: [ccbt.toml:112-113](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L112-L113)

Modelo de configuración de estrategia: [ccbt/models.py:StrategyConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuración de Descubrimiento

Configuración de descubrimiento: [ccbt.toml:116-136](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L116-L136)

- Configuración DHT: [ccbt.toml:118-125](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L118-L125)
- Configuración PEX: [ccbt.toml:128-129](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L128-L129)
- Configuración de tracker: [ccbt.toml:132-135](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval`: Intervalo de anuncio del tracker en segundos (predeterminado: 1800.0, rango: 60.0-86400.0)
  - `tracker_scrape_interval`: Intervalo de scrape del tracker en segundos para scraping periódico (predeterminado: 3600.0, rango: 60.0-86400.0)
  - `tracker_auto_scrape`: Scrapear automáticamente los trackers cuando se agregan torrents (BEP 48) (predeterminado: false)
  - Variables de entorno: `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

Modelo de configuración de descubrimiento: [ccbt/models.py:DiscoveryConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuración de Límites

Límites de velocidad: [ccbt.toml:138-152](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L138-L152)

- Límites globales: [ccbt.toml:140-141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L140-L141)
- Límites por torrent: [ccbt.toml:144-145](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L144-L145)
- Límites por peer: [ccbt.toml:148](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L148)
- Configuración del programador: [ccbt.toml:151](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L151)

Modelo de configuración de límites: [ccbt/models.py:LimitsConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuración de Observabilidad

Configuración de observabilidad: [ccbt.toml:154-171](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L154-L171)

- Registro: [ccbt.toml:156-160](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L156-L160)
- Métricas: [ccbt.toml:163-165](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L163-L165)
- Trazado y alertas: [ccbt.toml:168-170](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L168-L170)

Modelo de configuración de observabilidad: [ccbt/models.py:ObservabilityConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuración de Optimización {#optimization-profile}

Los perfiles de optimización proporcionan configuraciones preconfiguradas para diferentes casos de uso.

::: ccbt.models.OptimizationProfile
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3

**Perfiles Disponibles:**
- `BALANCED`: Rendimiento y uso de recursos equilibrado (predeterminado)
- `SPEED`: Velocidad de descarga máxima
- `EFFICIENCY`: Eficiencia de ancho de banda máxima
- `LOW_RESOURCE`: Optimizado para sistemas de bajos recursos
- `CUSTOM`: Usar configuraciones personalizadas sin sobrescrituras de perfil

Modelo de configuración de optimización: [ccbt/models.py:OptimizationConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuración de Seguridad

Configuración de seguridad: [ccbt.toml:173-178](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L173-L178)

Modelo de configuración de seguridad: [ccbt/models.py:SecurityConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

#### Configuración de Cifrado

ccBitTorrent soporta BEP 3 Message Stream Encryption (MSE) y Protocol Encryption (PE) para conexiones seguras entre peers.

**Configuración de Cifrado:**

- `enable_encryption` (bool, predeterminado: `false`): Habilitar soporte de cifrado de protocolo
- `encryption_mode` (str, predeterminado: `"preferred"`): Modo de cifrado
  - `"disabled"`: Sin cifrado (solo conexiones planas)
  - `"preferred"`: Intentar cifrado, retroceder a plano si no está disponible
  - `"required"`: Cifrado obligatorio, la conexión falla si el cifrado no está disponible
- `encryption_dh_key_size` (int, predeterminado: `768`): Tamaño de clave Diffie-Hellman en bits (768 o 1024)
- `encryption_prefer_rc4` (bool, predeterminado: `true`): Preferir cifrado RC4 para compatibilidad con clientes antiguos
- `encryption_allowed_ciphers` (list[str], predeterminado: `["rc4", "aes"]`): Tipos de cifrado permitidos
  - `"rc4"`: Cifrado de flujo RC4 (más compatible)
  - `"aes"`: Cifrado AES en modo CFB (más seguro)
  - `"chacha20"`: Cifrado ChaCha20 (aún no implementado)
- `encryption_allow_plain_fallback` (bool, predeterminado: `true`): Permitir retroceso a conexión plana si el cifrado falla (solo se aplica cuando `encryption_mode` es `"preferred"`)

**Variables de Entorno:**

- `CCBT_ENABLE_ENCRYPTION`: Habilitar/deshabilitar cifrado (`true`/`false`)
- `CCBT_ENCRYPTION_MODE`: Modo de cifrado (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE`: Tamaño de clave DH (`768` o `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4`: Preferir RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS`: Lista separada por comas (ej., `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK`: Permitir retroceso plano (`true`/`false`)

**Ejemplo de Configuración:**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**Consideraciones de Seguridad:**

1. **Compatibilidad RC4**: RC4 es compatible pero criptográficamente débil. Usa AES para mejor seguridad cuando sea posible.
2. **Tamaño de Clave DH**: Las claves DH de 768 bits proporcionan seguridad adecuada para la mayoría de casos de uso. 1024 bits proporciona mayor seguridad pero aumenta la latencia del handshake.
3. **Modos de Cifrado**:
   - `preferred`: Mejor para compatibilidad - intenta cifrado pero retrocede elegantemente
   - `required`: Más seguro pero puede fallar al conectar con peers que no soportan cifrado
4. **Impacto en el Rendimiento**: El cifrado agrega sobrecarga mínima (~1-5% para RC4, ~2-8% para AES) pero mejora la privacidad y ayuda a evitar el traffic shaping.

**Detalles de Implementación:**

Implementación de cifrado: [ccbt/security/encryption.py:EncryptionManager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/encryption.py#L131)

- Handshake MSE: [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/mse_handshake.py#L45)
- Suites de Cifrado: [ccbt/security/ciphers/__init__.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Intercambio Diffie-Hellman: [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/dh_exchange.py)

### Configuración ML

Configuración de machine learning: [ccbt.toml:180-183](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L180-L183)

Modelo de configuración ML: [ccbt/models.py:MLConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuración del Dashboard

Configuración del dashboard: [ccbt.toml:185-191](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L185-L191)

Modelo de configuración del dashboard: [ccbt/models.py:DashboardConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

## Variables de Entorno

Las variables de entorno usan el prefijo `CCBT_` y siguen un esquema de nombres jerárquico.

Referencia: [env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example)

Formato: `CCBT_<SECTION>_<OPTION>=<value>`

Ejemplos:
- Red: [env.example:10-58](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L10-L58)
- Disco: [env.example:62-102](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L62-L102)
- Estrategia: [env.example:106-121](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L106-L121)
- Descubrimiento: [env.example:125-141](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L125-L141)
- Observabilidad: [env.example:145-162](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L145-L162)
- Límites: [env.example:166-180](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L166-L180)
- Seguridad: [env.example:184-189](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L184-L189)
- ML: [env.example:193-196](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L193-L196)

Análisis de variables de entorno: [ccbt/config/config.py:_get_env_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)

## Esquema de Configuración

Esquema de configuración y validación: [ccbt/config/config_schema.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_schema.py)

El esquema define:
- Tipos de campo y restricciones
- Valores predeterminados
- Reglas de validación
- Documentación

## Capacidades de Configuración

Capacidades de configuración y detección de características: [ccbt/config/config_capabilities.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_capabilities.py)

## Plantillas de Configuración

Plantillas de configuración predefinidas: [ccbt/config/config_templates.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_templates.py)

Plantillas para:
- Configuración de alto rendimiento
- Configuración de bajo recurso
- Configuración centrada en seguridad
- Configuración de desarrollo

## Ejemplos de Configuración

Las configuraciones de ejemplo están disponibles en el directorio [examples/](examples/):

- Configuración básica: [example-config-basic.toml](examples/example-config-basic.toml)
- Configuración avanzada: [example-config-advanced.toml](examples/example-config-advanced.toml)
- Configuración de rendimiento: [example-config-performance.toml](examples/example-config-performance.toml)
- Configuración de seguridad: [example-config-security.toml](examples/example-config-security.toml)

## Recarga en Caliente

Soporte de recarga en caliente de configuración: [ccbt/config/config.py:ConfigManager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L40)

El sistema de configuración soporta recargar cambios sin reiniciar el cliente.

## Migración de Configuración

Utilidades de migración de configuración: [ccbt/config/config_migration.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_migration.py)

Herramientas para migrar entre versiones de configuración.

## Respaldo y Diff de Configuración

Utilidades de gestión de configuración:
- Respaldo: [ccbt/config/config_backup.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_backup.py)
- Diff: [ccbt/config/config_diff.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_diff.py)

## Configuración Condicional

Soporte de configuración condicional: [ccbt/config/config_conditional.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_conditional.py)

## Configuración por Torrent

La configuración por torrent le permite sobrescribir configuraciones globales para torrents individuales. Estas configuraciones se persisten en puntos de control y el estado del demonio, asegurando que sobrevivan a los reinicios.

### Opciones por Torrent

Las opciones por torrent se almacenan en `AsyncTorrentSession.options` y pueden incluir:

- `piece_selection`: Estrategia de selección de piezas (`"rarest_first"`, `"sequential"`, `"random"`)
- `streaming_mode`: Habilitar modo streaming para archivos multimedia (`true`/`false`)
- `sequential_window_size`: Tamaño de la ventana de descarga secuencial (bytes)
- `max_peers_per_torrent`: Número máximo de pares para este torrent
- Opciones personalizadas según sea necesario

Implementación: [ccbt/session/session.py:AsyncTorrentSession](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py#L63)

### Límites de Velocidad por Torrent

Los límites de velocidad se pueden establecer por torrent usando `AsyncSessionManager.set_rate_limits()`:

- `down_kib`: Límite de velocidad de descarga en KiB/s (0 = ilimitado)
- `up_kib`: Límite de velocidad de carga en KiB/s (0 = ilimitado)

Implementación: [ccbt/session/session.py:set_rate_limits](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py#L1735)

### Valores Predeterminados Globales por Torrent

Puede establecer opciones predeterminadas por torrent en su archivo `ccbt.toml`:

```toml
[per_torrent_defaults]
piece_selection = "rarest_first"
streaming_mode = false
max_peers_per_torrent = 50
sequential_window_size = 10485760  # 10 MiB
```

Estos valores predeterminados se fusionan en las opciones de cada torrent cuando se crea la sesión del torrent.

Modelo: [ccbt/models.py:PerTorrentDefaultsConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Establecer Opciones por Torrent

#### Via CLI

```bash
# Establecer una opción por torrent
uv run btbt torrent config set <info_hash> piece_selection sequential

# Establecer límites de velocidad (via gestor de sesión)
# Nota: Los límites de velocidad generalmente se establecen via TUI o programáticamente
```

Ver [Referencia CLI](btbt-cli.md#per-torrent-configuration) para documentación CLI completa.

#### Via TUI

El panel de terminal proporciona una interfaz interactiva para gestionar la configuración por torrent:

- Navegar a la pantalla de configuración de torrent
- Editar opciones y límites de velocidad
- Los cambios se guardan automáticamente en puntos de control

Implementación: [ccbt/interface/screens/config/torrent_config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/screens/config/torrent_config.py)

#### Programáticamente

```python
# Establecer opciones por torrent
torrent_session.options["piece_selection"] = "sequential"
torrent_session.options["streaming_mode"] = True
torrent_session._apply_per_torrent_options()

# Establecer límites de velocidad
await session_manager.set_rate_limits(info_hash_hex, down_kib=100, up_kib=50)
```

### Persistencia

La configuración por torrent se persiste en:

1. **Puntos de Control**: Guardados automáticamente cuando se crean puntos de control. Restaurados al reanudar desde un punto de control.
   - Modelo: [ccbt/models.py:TorrentCheckpoint](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py#L2017)
   - Guardar: [ccbt/session/checkpointing.py:save_checkpoint_state](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/checkpointing.py)
   - Cargar: [ccbt/session/session.py:_resume_from_checkpoint](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py#L947)

2. **Estado del Demonio**: Guardado cuando se persiste el estado del demonio. Restaurado cuando el demonio se reinicia.
   - Modelo: [ccbt/daemon/state_models.py:TorrentState](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/state_models.py)
   - Guardar: [ccbt/daemon/state_manager.py:_build_state](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/state_manager.py#L212)
   - Cargar: [ccbt/daemon/main.py:_restore_torrent_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/main.py#L29)

## Consejos y Mejores Prácticas

### Ajuste de Rendimiento

- Aumenta `disk.write_buffer_kib` para escrituras secuenciales grandes: [ccbt.toml:64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L64)
- Habilita `direct_io` en Linux/NVMe para mejor rendimiento de escritura: [ccbt.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L81)
- Ajusta `network.pipeline_depth` y `network.block_size_kib` para tu red: [ccbt.toml:11-13](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L11-L13)

### Optimización de Recursos

- Ajusta `disk.hash_workers` según los núcleos de CPU: [ccbt.toml:70](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L70)
- Configura `disk.cache_size_mb` según la RAM disponible: [ccbt.toml:78](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L78)
- Establece `network.max_global_peers` según el ancho de banda: [ccbt.toml:6](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L6)

### Configuración de Red

- Configura timeouts según las condiciones de red: [ccbt.toml:22-26](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L22-L26)
- Habilita/deshabilita protocolos según sea necesario: [ccbt.toml:34-36](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L34-L36)
- Establece límites de velocidad apropiadamente: [ccbt.toml:39-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L39-L42)

Para un ajuste de rendimiento detallado, consulta la [Guía de Ajuste de Rendimiento](performance.md).
