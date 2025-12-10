# Comenzar

¡Bienvenido a ccBitTorrent! Esta guía te ayudará a comenzar rápidamente con nuestro cliente BitTorrent de alto rendimiento.

!!! tip "Característica Clave: Extensión del Protocolo BEP XET"
    ccBitTorrent incluye la **Extensión del Protocolo Xet (BEP XET)**, que permite el chunking definido por contenido y la deduplicación entre torrents. Esto transforma BitTorrent en un sistema de archivos peer-to-peer súper rápido y actualizable optimizado para colaboración. [Aprende más sobre BEP XET →](bep_xet.md)

## Instalación

### Requisitos Previos

- Python 3.8 o superior
- Gestor de paquetes [UV](https://astral.sh/uv) (recomendado)

### Instalar UV

Instala UV desde el script de instalación oficial:
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### Instalar ccBitTorrent

Instalar desde PyPI:
```bash
uv pip install ccbittorrent
```

O instalar desde el código fuente:
```bash
git clone https://github.com/ccBittorrent/ccbt.git
cd ccbt
uv pip install -e .
```

Los puntos de entrada están definidos en [pyproject.toml:79-81](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L79-L81).

## Puntos de Entrada Principales

ccBitTorrent proporciona tres puntos de entrada principales:

### 1. Bitonic (Recomendado)

**Bitonic** es la interfaz principal del panel de terminal. Proporciona una vista interactiva en vivo de todos los torrents, peers y métricas del sistema.

- Punto de entrada: [ccbt/interface/terminal_dashboard.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- Definido en: [pyproject.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L81)
- Iniciar: `uv run bitonic` o `uv run ccbt dashboard`

Consulta la [Guía de Bitonic](bitonic.md) para uso detallado.

### 2. btbt CLI

**btbt** es la interfaz de línea de comandos mejorada con funciones avanzadas.

- Punto de entrada: [ccbt/cli/main.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1463)
- Definido en: [pyproject.toml:80](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L80)
- Iniciar: `uv run btbt`

Consulta la [Referencia de btbt CLI](btbt-cli.md) para todos los comandos disponibles.

### 3. ccbt (CLI Básico)

**ccbt** es la interfaz de línea de comandos básica.

- Punto de entrada: [ccbt/__main__.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/__main__.py#L18)
- Definido en: [pyproject.toml:79](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L79)
- Iniciar: `uv run ccbt`

## Inicio Rápido

### Iniciar el Demonio {#start-daemon}

ccBitTorrent puede ejecutarse en modo demonio para operación en segundo plano, o localmente para descargas de sesión única.

**Iniciar el demonio (recomendado para múltiples torrents):**
```bash
# Iniciar demonio en segundo plano
uv run btbt daemon start

# Iniciar demonio en primer plano (para depuración)
uv run btbt daemon start --foreground

# Verificar estado del demonio
uv run btbt daemon status
```

El demonio se ejecuta en segundo plano y gestiona todas las sesiones de torrent. Los comandos CLI se conectan automáticamente al demonio cuando está en ejecución.

**Ejecutar localmente (sin demonio):**
```bash
# Los comandos se ejecutarán en modo local si el demonio no está en ejecución
uv run btbt download movie.torrent
```

### Iniciar Bitonic (Recomendado)

Inicia el panel de terminal:
```bash
uv run bitonic
```

O mediante la CLI:
```bash
uv run ccbt dashboard
```

Con tasa de actualización personalizada:
```bash
uv run ccbt dashboard --refresh 2.0
```

### Descargar un Torrent {#download-torrent}

Usando la CLI:
```bash
# Descargar desde archivo torrent
uv run btbt download movie.torrent

# Descargar desde enlace magnet
uv run btbt magnet "magnet:?xt=urn:btih:..."

# Con límites de velocidad
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512

# Reanudar desde punto de control
uv run btbt download movie.torrent --resume
```

Consulta la [Referencia de btbt CLI](btbt-cli.md) para todas las opciones de descarga.

### Configurar ccBitTorrent {#configure}

Crea un archivo `ccbt.toml` en tu directorio de trabajo. Consulta la configuración de ejemplo:
- Configuración predeterminada: [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Variables de entorno: [env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
- Sistema de configuración: [ccbt/config/config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)

!!! warning "Resolución de Rutas en Windows"
    En Windows, las rutas relacionadas con el demonio (archivos PID, directorios de estado) usan el ayudante `_get_daemon_home_dir()` de `ccbt/daemon/daemon_manager.py` para una resolución de ruta consistente, especialmente con espacios en los nombres de usuario. Ver [Guía de Configuración - Resolución de Rutas en Windows](configuration.md#daemon-home-dir) para más detalles.

Consulta la [Guía de Configuración](configuration.md) para opciones de configuración detalladas.

## Informes del Proyecto

Ver métricas de calidad del proyecto e informes:

- **Cobertura de Código**: [reports/coverage.md](reports/coverage.md) - Análisis completo de cobertura de código
- **Informe de Seguridad**: [reports/bandit/index.md](reports/bandit/index.md) - Resultados del escaneo de seguridad de Bandit
- **Benchmarks**: [reports/benchmarks/index.md](reports/benchmarks/index.md) - Resultados de benchmarks de rendimiento

Estos informes se generan y actualizan automáticamente como parte de nuestro proceso de integración continua.

## Próximos Pasos

- [Bitonic](bitonic.md) - Aprende sobre la interfaz del panel de terminal
- [btbt CLI](btbt-cli.md) - Referencia completa de la interfaz de línea de comandos
- [Configuración](configuration.md) - Opciones de configuración detalladas
- [Ajuste de Rendimiento](performance.md) - Guía de optimización
- [Referencia de API](API.md) - Documentación de la API de Python incluyendo funciones de monitoreo

## Obtener Ayuda

- Usa `uv run bitonic --help` o `uv run btbt --help` para ayuda de comandos
- Consulta la [Referencia de btbt CLI](btbt-cli.md) para opciones detalladas
- Visita nuestro [repositorio de GitHub](https://github.com/ccBittorrent/ccbt) para problemas y discusiones
