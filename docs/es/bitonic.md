# Bitonic - Panel de Terminal

**Bitonic** es el punto de entrada principal de ccBitTorrent, proporcionando un panel de terminal interactivo en vivo para monitorear y gestionar torrents, pares, velocidades y métricas del sistema.

- Punto de entrada: [ccbt/interface/terminal_dashboard.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3914)
- Definido en: [pyproject.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L81)
- Clase principal: [ccbt/interface/terminal_dashboard.py:TerminalDashboard](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3009)

## Iniciar Bitonic

Inicie Bitonic usando el punto de entrada dedicado:
```bash
uv run bitonic
```

O mediante la CLI:
```bash
uv run ccbt dashboard
```

Con opciones:
```bash
# Intervalo de actualización personalizado (segundos)
uv run bitonic --refresh 2.0

# Mediante CLI con reglas de alerta
uv run ccbt dashboard --rules /path/to/alert-rules.json
```

ImplementaciÃ³n: [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L20)

## Ejemplo Completo de Viaje del Usuario

```
Flujo de Acciones del Usuario:
─────────────────

1. El usuario presiona 'o' (Agregar Avanzado) en el panel principal
   ↓
2. Aparece el modal de la pantalla Agregar Torrent
   ↓
3. Paso 1: El usuario ingresa el enlace magnético
   → Entrada: "magnet:?xt=urn:btih:abc123..."
   → Valida: ✓ URI magnético válido
   → Carga: Metadatos del torrent
   → Clics: [Siguiente]
   ↓
4. Paso 2: El usuario ingresa el directorio de salida
   → Entrada: "/home/user/downloads"
   → Clics: [Siguiente]
   ↓
5. Paso 3: El usuario selecciona archivos
   → Selecciona: Archivos 0, 1, 3 (omite el archivo 2)
   → Establece: Prioridad del archivo 1 a "alta"
   → Clics: [Siguiente]
   ↓
6. Paso 4: El usuario establece límites de velocidad
   → Descarga: 1000 KiB/s
   → Carga: 500 KiB/s
   → Clics: [Siguiente]
   ↓
7. Paso 5: El usuario selecciona la prioridad de la cola
   → Selecciona: "Alta"
   → Clics: [Siguiente]
   ↓
8. Paso 6: El usuario habilita la reanudación
   → Interruptor: ACTIVADO
   → Clics: [Siguiente]
   ↓
9. Paso 7: El usuario habilita Xet con deduplicación
   → Habilitar Xet: ACTIVADO
   → Deduplicación: ACTIVADO
   → P2P CAS: DESACTIVADO
   → Compresión: DESACTIVADO
   → Clics: [Siguiente]
   ↓
10. Paso 8: El usuario omite IPFS
    → Habilitar IPFS: DESACTIVADO
    → Clics: [Siguiente]
    ↓
11. Paso 9: El usuario habilita el auto-scrape
    → Auto-scrape: ACTIVADO
    → Clics: [Siguiente]
    ↓
12. Paso 10: El usuario habilita uTP
    → Habilitar uTP: ACTIVADO
    → Clics: [Siguiente]
    ↓
13. Paso 11: El usuario habilita el mapeo NAT
    → Habilitar NAT: ACTIVADO
    → Clics: [Enviar]
    ↓
14. El formulario se envía
    → Diccionario de opciones construido
    → Modal descartado
    → dashboard._process_add_torrent() llamado
    → Torrent agregado con todas las opciones especificadas
```


## Terminal Dashboard Visualization

### Main Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Header (with clock)                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────┐  ┌──────────────────────────────────────┐ │
│  │ LEFT PANEL              │  │ RIGHT PANEL                          │ │
│  │                         │  │                                      │ │
│  │ ┌────────────────────┐  │  │ ┌──────────────────────────────────┐ │ │
│  │ │ Overview           │  │  │ │ Torrents Table                  │ │ │
│  │ │                    │  │  │ │ (2fr height)                    │ │ │
│  │ │ • Torrents         │  │  │ │                                 │ │ │
│  │ │ • Active           │  │  │ │ Info Hash | Name | Status | ... │ │ │
│  │ │ • Paused           │  │  │ │ ─────────────────────────────── │ │ │
│  │ │ • Seeding          │  │  │ │ abc123... | file.torrent | ... │ │ │
│  │ │ • Down Rate        │  │  │ │ def456... | movie.torrent | ... │ │ │
│  │ │ • Up Rate          │  │  │ │ ...                             │ │ │
│  │ │ • Avg Progress     │  │  │ │                                 │ │ │
│  │ │                    │  │  │ └──────────────────────────────────┘ │ │
│  │ └────────────────────┘  │  │                                      │ │
│  │                         │  │ ┌──────────────────────────────────┐ │ │
│  │ ┌────────────────────┐  │  │ │ Peers Table                     │ │ │
│  │ │ Speed Sparklines   │  │  │ │ (1fr height)                    │ │ │
│  │ │                    │  │  │ │                                 │ │ │
│  │ │ Download: ▁▂▃▅▆▇█  │  │  │ │ IP | Port | Down | Up | ...    │ │ │
│  │ │ Upload:   ▁▂▃▅▆▇█  │  │  │ │ ─────────────────────────────── │ │ │
│  │ │                    │  │  │ │ 192.168.1.1 | 6881 | ...       │ │ │
│  │ └────────────────────┘  │  │ │ ...                             │ │ │
│  │                         │  │ └──────────────────────────────────┘ │ │
│  │                         │  │                                      │ │
│  │                         │  │ ┌──────────────────────────────────┐ │ │
│  │                         │  │ │ Details                          │ │ │
│  │                         │  │ │ (1fr height)                     │ │ │
│  │                         │  │ │ Selected torrent details...     │ │ │
│  │                         │  │ └──────────────────────────────────┘ │ │
│  │                         │  │                                      │ │
│  │                         │  │ ┌──────────────────────────────────┐ │ │
│  │                         │  │ │ Logs (RichLog)                  │ │ │
│  │                         │  │ │ (1fr height)                     │ │ │
│  │                         │  │ │ [INFO] Connected to peer...     │ │ │
│  │                         │  │ │ [WARN] Tracker timeout...        │ │ │
│  │                         │  │ │ ...                             │ │ │
│  │                         │  │ └──────────────────────────────────┘ │ │
│  └──────────────────────────┘  └──────────────────────────────────────┘ │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ Status Bar                                                              │
├─────────────────────────────────────────────────────────────────────────┤
│ Alerts Container                                                        │
├─────────────────────────────────────────────────────────────────────────┤
│ Footer                                                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Bindings

#### Main Dashboard Actions
- `p` - Pause torrent
- `r` - Resume torrent
- `q` - Quit
- `i` - Quick add torrent
- `o` - Advanced add torrent
- `b` - Browse add torrent
- `?` - Help

#### Configuration
- `g` - Global config
- `t` - Torrent config

#### Monitoring Screens
- `s` - System Resources
- `m` - Performance Metrics
- `n` - Network Quality
- `h` - Historical Trends
- `a` - Alerts Dashboard
- `e` - Metrics Explorer
- `x` - Security Scan

#### Protocol Management
- `Ctrl+X` - Xet Management
- `Ctrl+I` - IPFS Management
- `Ctrl+S` - SSL Config
- `Ctrl+P` - Proxy Config
- `Ctrl+R` - Scrape Results
- `Ctrl+N` - NAT Management
- `Ctrl+U` - uTP Config

#### Navigation
- `Ctrl+M` - Navigation Menu

## Add a Torrent 

The Add Torrent Screen is a comprehensive 11-step modal form that guides users through adding a torrent with all available configuration options. It provides a structured, user-friendly interface for configuring torrent downloads with advanced features.

### Process Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Add Torrent Process                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Step 1: Torrent Input                                      │
│    ↓                                                        │
│  Step 2: Output Directory                                    │
│    ↓                                                        │
│  Step 3: File Selection (if applicable)                     │
│    ↓                                                        │
│  Step 4: Rate Limits                                        │
│    ↓                                                        │
│  Step 5: Queue Priority                                     │
│    ↓                                                        │
│  Step 6: Resume Option                                      │
│    ↓                                                        │
│  Step 7: Xet Protocol Options                               │
│    ↓                                                        │
│  Step 8: IPFS Protocol Options                              │
│    ↓                                                        │
│  Step 9: Scrape Options                                     │
│    ↓                                                        │
│  Step 10: uTP Protocol Options                              │
│    ↓                                                        │
│  Step 11: NAT Traversal Options                             │
│    ↓                                                        │
│  Submit → Process Torrent Addition                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Step 1: Torrent Input

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1/11: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Enter the path to a .torrent file or a magnet link:    │ │
│ │                                                         │ │
│ │ Examples:                                               │ │
│ │   /path/to/file.torrent                                │ │
│ │   magnet:?xt=urn:btih:...                              │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [magnet:?xt=urn:btih:abc123def456...________________]  │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Cancel]                    [Previous] [Next]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Features:
- Input field for torrent path or magnet URI
- Help text with examples
- Validation: Must be non-empty and valid torrent/magnet
- On Next: Loads torrent data for subsequent steps
- Keyboard: Input field is focused automatically
```

### Step 2: Output Directory

```
┌─────────────────────────────────────────────────────────────┐
│ Step 2/11: ✓ → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Enter the directory where files should be downloaded:  │ │
│ │                                                         │ │
│ │ Leave empty to use current directory.                  │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [/home/user/downloads_____________________________]     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Cancel]                    [Previous] [Next]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Features:
- Input field for output directory path
- Default: Current directory (.)
- Help text explaining default behavior
- Validation: Directory path (validated on submit)
- Keyboard: Input field is focused automatically
```

### Step 3: File Selection

```
┌─────────────────────────────────────────────────────────────┐
│ Step 3/11: ✓ → ✓ → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Select files to download and set priorities:            │ │
│ │   Space: Toggle selection                               │ │
│ │   P: Change priority                                    │ │
│ │   A: Select all                                        │ │
│ │   D: Deselect all                                      │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Select  Priority  Size        File Name                 │ │
│ │ ──────────────────────────────────────────────────────── │ │
│ │ ✓        normal    500.00 MB  movie.mp4                │ │
│ │ ✓        high      1.20 GB    movie.mkv                │ │
│ │          normal    300.00 MB  subtitles.srt            │ │
│ │ ✓        low       800.00 MB  trailer.avi              │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Cancel]                    [Previous] [Next]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Features:
- DataTable showing all files in torrent
- Columns: Select (✓/space), Priority, Size, File Name
- Interactive selection with keyboard shortcuts
- Default: All files selected with "normal" priority
- Validation: None (optional step)
- Special Cases:
  - If torrent has no files: Shows "This torrent has no files to select"
  - If torrent data not loaded: Shows error, prompts to go back
- Keyboard: Table is focused, supports navigation
```

### Step 4: Rate Limits

```
┌─────────────────────────────────────────────────────────────┐
│ Step 4/11: ✓ → ✓ → ✓ → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Set rate limits for this torrent:                      │ │
│ │                                                         │ │
│ │ Enter 0 or leave empty for unlimited.                  │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Download Limit (KiB/s):                                     │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [1000_____________________________________________]     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Upload Limit (KiB/s):                                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [500______________________________________________]     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Cancel]                    [Previous] [Next]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Features:
- Two input fields: Download and Upload limits
- Units: KiB/s (Kibibytes per second)
- Default: 0 (unlimited)
- Validation: Must be non-negative integers
- Help text explaining unlimited option
- Keyboard: Download limit field is focused first
```

### Step 5: Queue Priority

```
┌─────────────────────────────────────────────────────────────┐
│ Step 5/11: ✓ → ✓ → ✓ → ✓ → 5 → 6 → 7 → 8 → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Select queue priority for this torrent:                 │ │
│ │                                                         │ │
│ │ Higher priority torrents will be started first.         │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Priority: [▼ Normal                    ]               │ │
│ │                                                         │ │
│ │ Options:                                               │ │
│ │   • Maximum                                            │ │
│ │   • High                                               │ │
│ │   • Normal  ← Selected                                 │ │
│ │   • Low                                                │ │
│ │   • Paused                                             │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Cancel]                    [Previous] [Next]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Features:
- Select widget with priority options
- Options: Maximum, High, Normal, Low, Paused
- Default: Normal
- Help text explaining priority system
- Keyboard: Select widget is focused
```

### Step 6: Resume Option

```
┌─────────────────────────────────────────────────────────────┐
│ Step 6/11: ✓ → ✓ → ✓ → ✓ → ✓ → 6 → 7 → 8 → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Resume from checkpoint if available:                   │ │
│ │                                                         │ │
│ │ If enabled, the download will resume from the last     │ │
│ │ checkpoint.                                            │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Resume from checkpoint: [ ]                                │
│                          ↑                                  │
│                      Switch (OFF)                           │
│                                                             │
│ [Cancel]                    [Previous] [Next]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Features:
- Switch widget for resume option
- Default: False (disabled)
- Help text explaining checkpoint resume functionality
- Keyboard: Switch is focused
```

### Step 7: Xet Protocol Options

```
┌─────────────────────────────────────────────────────────────┐
│ Step 7/11: ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → 7 → 8 → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Xet Protocol Options:                                  │ │
│ │                                                         │ │
│ │ Xet enables content-defined chunking and deduplication.│ │
│ │ Useful for reducing storage when downloading similar   │ │
│ │ content.                                               │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Enable Xet Protocol:              [ ]                       │
│ Enable Deduplication:            [ ]                       │
│ Enable P2P Content-Addressed Storage: [ ]                  │
│ Enable Compression:               [ ]                      │
│                                                             │
│ Press Ctrl+X in main dashboard to manage Xet settings      │
│ globally                                                    │
│                                                             │
│ [Cancel]                    [Previous] [Next]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Features:
- Four switch widgets for Xet options:
  1. Enable Xet Protocol (main switch)
  2. Enable Deduplication
  3. Enable P2P Content-Addressed Storage
  4. Enable Compression
- Default: All disabled
- Help text explaining Xet protocol benefits
- Link to global Xet management screen (Ctrl+X)
- Keyboard: First switch (Enable Xet) is focused
```

### Step 8: IPFS Protocol Options

```
┌─────────────────────────────────────────────────────────────┐
│ Step 8/11: ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → 8 → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ IPFS Protocol Options:                                  │ │
│ │                                                         │ │
│ │ IPFS enables content-addressed storage and peer-to-peer │ │
│ │ content sharing. Content can be accessed via IPFS CID  │ │
│ │ after download.                                         │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Enable IPFS Protocol:          [ ]                         │
│ Pin Content in IPFS:           [ ]                         │
│                                                             │
│ Press Ctrl+I in main dashboard to manage IPFS content and  │
│ peers                                                       │
│                                                             │
│ [Cancel]                    [Previous] [Next]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Features:
- Two switch widgets for IPFS options:
  1. Enable IPFS Protocol (main switch)
  2. Pin Content in IPFS
- Default: Both disabled
- Help text explaining IPFS protocol benefits
- Link to global IPFS management screen (Ctrl+I)
- Keyboard: First switch (Enable IPFS) is focused
```

### Step 9: Scrape Options

```
┌─────────────────────────────────────────────────────────────┐
│ Step 9/11: ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Scrape Options:                                         │ │
│ │                                                         │ │
│ │ Scraping queries tracker statistics (seeders, leechers, │ │
│ │ completed downloads). Auto-scrape will automatically   │ │
│ │ scrape the tracker when the torrent is added.           │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Auto-scrape on Add:            [ ]                         │
│                                                             │
│ Press Ctrl+R in main dashboard to view scrape results      │
│                                                             │
│ [Cancel]                    [Previous] [Next]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Features:
- Single switch widget for auto-scrape option
- Default: Disabled
- Help text explaining scraping functionality
- Link to scrape results screen (Ctrl+R)
- Keyboard: Switch is focused
```

### Step 10: uTP Protocol Options

```
┌─────────────────────────────────────────────────────────────┐
│ Step 10/11: ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → 10 → 11 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ uTP (uTorrent Transport Protocol) Options:             │ │
│ │                                                         │ │
│ │ uTP provides reliable, ordered delivery over UDP with  │ │
│ │ delay-based congestion control (BEP 29). Useful for    │ │
│ │ better performance on networks with high latency or     │ │
│ │ packet loss.                                            │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Enable uTP Transport:          [ ]                        │
│                                                             │
│ Press Ctrl+U in main dashboard to configure uTP settings   │
│ globally                                                    │
│                                                             │
│ [Cancel]                    [Previous] [Next]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Features:
- Single switch widget for uTP option
- Default: Disabled
- Help text explaining uTP protocol benefits (BEP 29)
- Link to global uTP configuration screen (Ctrl+U)
- Keyboard: Switch is focused
```

### Step 11: NAT Traversal Options

```
┌─────────────────────────────────────────────────────────────┐
│ Step 11/11: ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → 11  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ NAT Traversal Options:                                  │ │
│ │                                                         │ │
│ │ NAT traversal (NAT-PMP/UPnP) automatically maps ports  │ │
│ │ on your router. This allows peers to connect to you    │ │
│ │ directly, improving download speeds.                    │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Enable NAT Port Mapping:       [ ]                        │
│                                                             │
│ Press Ctrl+N in main dashboard to manage NAT settings      │
│ globally                                                    │
│                                                             │
│ [Cancel]                    [Previous] [Submit]            │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Features:
- Single switch widget for NAT mapping option
- Default: Disabled
- Help text explaining NAT traversal benefits
- Link to global NAT management screen (Ctrl+N)
- Keyboard: Switch is focused
- Note: "Next" button changes to "Submit" on final step
```



## Widget Hierarchy

```
TerminalDashboard (App)
├── Header (with clock)
├── Horizontal (#body)
│   ├── Container (#left)
│   │   ├── Overview (#overview)
│   │   │   └── Rich Table (Torrents, Active, Paused, Seeding, Rates, Progress)
│   │   └── SpeedSparklines (#speeds)
│   │       ├── Sparkline (Download)
│   │       └── Sparkline (Upload)
│   └── Container (#right)
│       ├── TorrentsTable (#torrents)
│       │   └── DataTable columns: Info Hash, Name, Status, Progress, Down/Up
│       ├── PeersTable (#peers)
│       │   └── DataTable columns: IP, Port, Down, Up, Latency, Quality, Health, Choked, Client
│       ├── Static (#details)
│       └── RichLog (#logs)
├── Static (#statusbar)
├── Container
│   └── Static (#alerts)
└── Footer
```


## Available Screens

### Monitoring Screens
1. **SystemResourcesScreen** - CPU, memory, disk, network usage
2. **PerformanceMetricsScreen** - Performance metrics from MetricsCollector
3. **NetworkQualityScreen** - Network quality metrics for peers
4. **HistoricalTrendsScreen** - Historical trends with sparklines
5. **AlertsDashboardScreen** - Enhanced alerts with filtering
6. **MetricsExplorerScreen** - Explore all metrics with export
7. **QueueMetricsScreen** - Queue metrics (position, priority, waiting time)
8. **DiskIOMetricsScreen** - Disk I/O statistics
9. **TrackerMetricsScreen** - Tracker metrics (announce/scrape success)
10. **PerformanceAnalysisScreen** - Performance analysis from CLI
11. **DiskAnalysisScreen** - Disk analysis from disk-detect/stats

### Configuration Screens
1. **GlobalConfigMainScreen** - Main global config with section selector
2. **GlobalConfigDetailScreen** - Detail screen for global config sections
3. **PerTorrentConfigMainScreen** - Main per-torrent config with torrent selector
4. **TorrentConfigDetailScreen** - Detail screen for per-torrent config

### Protocol Management Screens
1. **XetManagementScreen** - Xet protocol management
2. **IPFSManagementScreen** - IPFS protocol management
3. **SSLConfigScreen** - SSL/TLS configuration
4. **ProxyConfigScreen** - Proxy configuration
5. **ScrapeResultsScreen** - View cached scrape results
6. **NATManagementScreen** - NAT traversal (NAT-PMP, UPnP)
7. **UTPConfigScreen** - uTP configuration

### Utility Screens
1. **HelpScreen** - Keyboard shortcuts and help
2. **NavigationMenuScreen** - Navigation menu/sidebar
3. **AddTorrentScreen** - Advanced torrent addition (multi-step form)
4. **FileSelectionScreen** - File selection management
5. **ConfirmationDialog** - Modal confirmation dialog

## Screen Layout Examples

### System Resources Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ System Resources                                     │ │
│ │ Resource    Usage    Progress                        │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ CPU         75.0%    ████████████████░░░░░░░░        │ │
│ │ Memory      85.0%    ████████████████████░░░░        │ │
│ │ Disk        60.0%    ████████████░░░░░░░░░░░░        │ │
│ │ Processes   142      (no progress bar)               │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Network I/O                                          │ │
│ │ Direction   Bytes          Formatted                │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Sent        1,234,567,890  1.15 GB                   │ │
│ │ Received    987,654,321    941.89 MB                 │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Performance Metrics Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Performance Metrics                                 │ │
│ │ Metric              Value      Description          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Peer Connections    45         Total connected...   │ │
│ │ Download Speed      2.5 MB/s   Global download...   │ │
│ │ Upload Speed        1.2 MB/s   Global upload...     │ │
│ │ Pieces Completed    1,234      Successfully...       │ │
│ │ Pieces Failed       5          Failed piece...       │ │
│ │ Tracker Requests    89         Total tracker...      │ │
│ │ Tracker Responses   87         Successful...         │ │
│ │ Tracker Success     97.8%      Response success...  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Event-Driven Metrics (MetricsPlugin)                │ │
│ │ Metric          Count  Avg    Min    Max    Sum     │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ download_speed  1000   2.5MB  0.1MB  5.0MB  2.5GB   │ │
│ │ upload_speed    1000   1.2MB  0.05MB 3.0MB  1.2GB   │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Statistics                                          │ │
│ │ Metric              Value                            │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total Metrics       25                              │ │
│ │ Active Metrics      20                              │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Network Quality Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Global Network Statistics                          │ │
│ │ Metric                  Value                      │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total Torrents          5                          │ │
│ │ Active Torrents         3                          │ │
│ │ Global Download Rate    2.5 MB/s                   │ │
│ │ Global Upload Rate      1.2 MB/s                   │ │
│ │ Download Utilization    62.5%                      │ │
│ │ Upload Utilization      60.0%                      │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Per-Torrent Network Quality                        │ │
│ │ Torrent        Down Rate  Up Rate  Progress Status │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ example.torrent 1.2 MB/s  500 KB/s  45%   Active   │ │
│ │ movie.torrent   800 KB/s  300 KB/s  78%   Seeding  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Peer Metrics Summary                                │ │
│ │ Metric                      Value                   │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total Peers                  25                     │ │
│ │ Choked Peers                 8                      │ │
│ │ Unchoke Ratio                68.0%                   │ │
│ │ Average Latency               45.2 ms                │ │
│ │ Piece Request Success Rate    95.5%                  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Peer Quality (Torrent: abc123...)                   │ │
│ │ IP            Down      Up      Quality            │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ 192.168.1.1   1.2 MB/s  500 KB/s  85% ████████     │ │
│ │ 10.0.0.5      800 KB/s  300 KB/s  70% ██████░░     │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Historical Trends Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Historical Trends                                  │ │
│ │ Metric              Current    Trend               │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Download Speed      2.5 MB/s   ▁▂▃▅▆▇█            │ │
│ │ Upload Speed        1.2 MB/s   ▁▂▃▅▆▇█            │ │
│ │ Peer Connections    45         ▁▂▃▅▆▇█            │ │
│ │ Pieces Completed    1,234       ▁▂▃▅▆▇█            │ │
│ │ Tracker Success     97.8%       ▁▂▃▅▆▇█            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Sparklines Group                                    │ │
│ │ [Download Speed Sparkline]                          │ │
│ │ [Upload Speed Sparkline]                            │ │
│ │ [Peer Connections Sparkline]                       │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Alerts Dashboard Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Alert Rules                                         │ │
│ │ Name        Metric          Condition    Severity  │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ high_cpu    cpu_usage        > 80%        WARNING   │ │
│ │ low_disk    disk_usage      > 90%        ERROR      │ │
│ │ slow_dl     download_speed   < 100 KB/s  WARNING   │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Active Alerts                                       │ │
│ │ Severity  Rule        Metric        Value    Time   │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ WARNING   high_cpu    cpu_usage     85%      14:32  │ │
│ │ ERROR     low_disk    disk_usage    92%      14:30  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Alert History (Last 50)                             │ │
│ │ Severity  Rule        Value    Time      Resolved  │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ WARNING   high_cpu    85%      14:32:15  No        │ │
│ │ ERROR     low_disk    92%      14:30:10  No        │ │
│ │ WARNING   slow_dl     50 KB/s  14:25:00  Yes       │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Alert Statistics                                    │ │
│ │ Statistic              Value                       │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Alerts Triggered       15                          │ │
│ │ Alerts Resolved        8                           │ │
│ │ Notifications Sent     12                          │ │
│ │ Notification Failures  0                           │ │
│ │ Suppressed Alerts      2                           │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Metrics Explorer Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ Filter: [download________________________________]      │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Metrics Table                                       │ │
│ │ Metric Name        Type      Current Value  Desc   │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ download_speed     gauge     2.5 MB/s       ...    │ │
│ │ upload_speed       gauge     1.2 MB/s       ...    │ │
│ │ peer_connections   counter   45             ...    │ │
│ │ pieces_completed   counter   1,234          ...    │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Metric Details                                      │ │
│ │ Name: download_speed                                │ │
│ │ Type: gauge                                         │ │
│ │ Current Value: 2.5 MB/s                            │ │
│ │ Description: Global download speed in bytes/sec     │ │
│ │ Unit: bytes/sec                                     │ │
│ │ Min: 0.0                                            │ │
│ │ Max: 10.0 MB/s                                      │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q, Export: e/p)               │
└─────────────────────────────────────────────────────────┘
```

### Queue Metrics Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Queue Statistics                                    │ │
│ │ Metric              Value      Description          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total Torrents      10         Total torrents...    │ │
│ │ Active Downloading  3          Currently...         │ │
│ │ Active Seeding      2          Currently...         │ │
│ │ Queued              5          Torrents waiting... │ │
│ │ Paused              0          Paused torrents      │ │
│ │                                                     │ │
│ │ By Priority                                         │ │
│ │   Maximum           1          Torrents with...     │ │
│ │   High              2          Torrents with...     │ │
│ │   Normal            5          Torrents with...     │ │
│ │   Low               2          Torrents with...     │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Queue Summary                                       │ │
│ │ Metric              Value                          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Queue Length        10                             │ │
│ │ Queued (Waiting)    5                              │ │
│ │ Active              5                              │ │
│ │ Avg Waiting Time    15m                            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Queue Entries                                       │ │
│ │ Pos  Torrent        Priority  Status    Wait  Down │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ 1    example.torrent Maximum   Active   0s    1000 │ │
│ │ 2    movie.torrent   High      Active   5m    800   │ │
│ │ 3    file.torrent    Normal    Queued   10m   -    │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Disk I/O Metrics Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Disk I/O Statistics                                 │ │
│ │ Metric              Value      Description          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total Writes        1,234,567  Number of write...   │ │
│ │ Bytes Written       5.2 GB     Total bytes...       │ │
│ │ Queue Full Errors   5          Times write...        │ │
│ │ Preallocations      100        File preallocation... │ │
│ │ io_uring Operations 50,000     Operations using...   │ │
│ │ Queue Depth         15/100     Current queue...      │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Cache Statistics                                    │ │
│ │ Metric              Value      Description          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Cache Entries       500        Number of cached...  │ │
│ │ Cache Size          2.5 GB     Total size of...      │ │
│ │ Cache Hits          10,000     Successful cache...  │ │
│ │ Cache Misses        500        Failed cache...       │ │
│ │ Hit Rate            95.2%      Cache hit percentage │ │
│ │ Bytes Served        1.5 GB     Bytes served from...  │ │
│ │ Cache Efficiency    92.5%      Cache efficiency...  │ │
│ │ Evictions           50         Cache entries...      │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Disk I/O Configuration                              │ │
│ │ Setting              Value                          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Max Workers         8                              │ │
│ │ Queue Size          100                            │ │
│ │ Cache Size          512 MB                         │ │
│ │ Storage Type        NVME                           │ │
│ │ io_uring Enabled    Yes                            │ │
│ │ Direct I/O Enabled  Yes                            │ │
│ │ NVMe Optimized      Yes                            │ │
│ │ Write Cache Enabled Yes                            │ │
│ │ Adaptive Workers    Active                         │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Tracker Metrics Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Tracker Statistics                                  │ │
│ │ Tracker        Requests  Avg Response  Error  Reuse │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ tracker1.com   1,234     45.2 ms       0.00%  95%   │ │
│ │ tracker2.org  567       120.5 ms      2.50%  90%   │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Summary                                             │ │
│ │ Metric              Value                          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total Trackers      2                              │ │
│ │ Total Requests      1,801                          │ │
│ │ Total Errors        14                             │ │
│ │ Success Rate        99.22%                         │ │
│ │ Avg Response Time   67.8 ms                        │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Tracker Sessions                                    │ │
│ │ URL            Last Announce  Interval  Fail Status│ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ tracker1.com   2m ago         30m       0   Healthy │ │
│ │ tracker2.org   5m ago         60m       1   Degraded │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Navigation Menu Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Navigation Menu                                      │ │
│ │ Category      Screen              Shortcut          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Monitoring    System Resources    s                │ │
│ │ Monitoring    Performance Metrics m                │ │
│ │ Monitoring    Network Quality     n                │ │
│ │ Monitoring    Historical Trends   h                │ │
│ │ Monitoring    Alerts Dashboard    a                │ │
│ │ Monitoring    Metrics Explorer    e                │ │
│ │ Monitoring    Queue Metrics      u                │ │
│ │ Monitoring    Disk I/O Metrics   j                │ │
│ │ Monitoring    Tracker Metrics    k                │ │
│ │ Configuration Global Config      g                │ │
│ │ Configuration Torrent Config     t                │ │
│ │ Protocols     Xet Management     Ctrl+X            │ │
│ │ Protocols     IPFS Management    Ctrl+I            │ │
│ │ Protocols     SSL Config         Ctrl+S            │ │
│ │ Protocols     Proxy Config       Ctrl+P            │ │
│ │ Protocols     NAT Management     Ctrl+N            │ │
│ │ Protocols     uTP Config         Ctrl+U            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Navigation Menu                                      │ │
│ │ Select a screen to open. Press Enter to navigate,  │ │
│ │ Escape to go back.                                  │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Help Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Keyboard Shortcuts                                  │ │
│ │ Key         Action              Description         │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ p           Pause torrent       Pause selected...   │ │
│ │ r           Resume torrent      Resume selected...  │ │
│ │ q           Quit                 Exit dashboard      │ │
│ │ i           Quick Add           Quick torrent add   │ │
│ │ o           Advanced Add         Advanced torrent... │ │
│ │ g           Global Config        Open global...      │ │
│ │ t           Torrent Config       Open per-torrent... │ │
│ │ s           System Resources     Open system...      │ │
│ │ m           Performance Metrics Open performance... │ │
│ │ n           Network Quality      Open network...     │ │
│ │ h           Historical Trends   Open historical...  │ │
│ │ a           Alerts Dashboard     Open alerts...      │ │
│ │ e           Metrics Explorer    Open metrics...      │ │
│ │ ?           Help                 Show this help     │ │
│ │ Ctrl+M      Navigation Menu     Open navigation...  │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Global Config Main Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Configuration Sections                              │ │
│ │ Section              Description          Modified │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ network              Network configuration...        │ │
│ │ network.protocol_v2  BitTorrent Protocol...         │ │
│ │ network.utp          uTP transport...               │ │
│ │ disk                 Disk I/O configuration...       │ │
│ │ disk.attributes      File attributes...              │ │
│ │ disk.xet             Xet protocol...                │ │
│ │ strategy             Piece selection...              │ │
│ │ discovery            Peer discovery...               │ │
│ │ observability        Logging, metrics...             │ │
│ │ limits               Rate limit...                   │ │
│ │ security             Security settings...            │ │
│ │ security.ip_filter   IP filtering...                │ │
│ │ security.ssl         SSL/TLS settings...            │ │
│ │ proxy                Proxy configuration            │ │
│ │ ml                   Machine learning...             │ │
│ │ dashboard            Dashboard/web UI...             │ │
│ │ queue                Torrent queue...                │ │
│ │ nat                  NAT traversal...                │ │
│ │ ipfs                 IPFS protocol...                │ │
│ │ webtorrent           WebTorrent protocol...          │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Global Configuration                                │ │
│ │ Select a section to configure. Press Enter to edit, │ │
│ │ Escape to go back.                                  │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Global Config Detail Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Network Configuration                               │ │
│ │ Option          Current Value    Type               │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ max_connections 200              number             │ │
│ │ max_peers       50                number             │ │
│ │ connect_timeout 30                number             │ │
│ │ enable_utp       true              bool               │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Performance Metrics                                 │ │
│ │ [Metrics displayed here]                            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Configuration Editors                               │ │
│ │ max_connections: Network max connections            │ │
│ │ [200________________________________]              │ │
│ │ max_peers: Maximum peers per torrent                │ │
│ │ [50_________________________________]              │ │
│ │ connect_timeout: Connection timeout in seconds     │ │
│ │ [30_________________________________]              │ │
│ │ enable_utp: Enable uTP transport                    │ │
│ │ [✓] Enable uTP                                      │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Errors                                              │ │
│ │ (Validation errors appear here)                    │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Save (Runtime)] [Save to File] [Cancel]               │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Per-Torrent Config Main Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────┐ ┌────────────────┐ │
│ │ Torrents                         │ │ Summary        │ │
│ │ Info Hash  Name      Status ...   │ │ Key      Value │ │
│ │ ──────────────────────────────── │ │ ─────────────── │ │
│ │ abc123...  example   Active 45%   │ │ Total    10    │ │
│ │ def456...  movie     Seeding 100% │ │ With     5     │ │
│ │ ghi789...  file      Active 78%   │ │ Without  5     │ │
│ │ ...                               │ │                │ │
│ └──────────────────────────────────┘ └────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Per-Torrent Configuration                           │ │
│ │ Select a torrent to configure. Press Enter to edit, │ │
│ │ Escape to go back.                                  │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Torrent Config Detail Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Rate Limit Configuration                            │ │
│ │ Setting         Current Value    Description        │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Download Limit  1000 KiB/s      Per-torrent...      │ │
│ │ Upload Limit    500 KiB/s       Per-torrent...      │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Torrent: example.torrent                            │ │
│ │ Key              Value                              │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Info Hash        abc123...                          │ │
│ │ Status           Active                             │ │
│ │ Progress         45.0%                              │ │
│ │ Current Down     1.2 MB/s (1171.9 KiB/s)          │ │
│ │ Current Up       500 B/s (0.5 KiB/s)               │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Performance Metrics                                 │ │
│ │ [Metrics displayed here]                            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Configuration Inputs                                │ │
│ │ Download Limit (KiB/s, 0 = unlimited):              │ │
│ │ [1000________________________________]              │ │
│ │ Upload Limit (KiB/s, 0 = unlimited):                │ │
│ │ [500_________________________________]              │ │
│ │ Queue Priority:                                     │ │
│ │ [normal________________________________]            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Queue Configuration                                 │ │
│ │ Key              Value                              │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Queue Status     Priority: NORMAL, Position: 3     │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Files Section                                       │ │
│ │ [File information displayed here]                  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Operations                                          │ │
│ │ [Announce] [Scrape] [PEX] [Rehash] [Pause] [Resume] │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Save] [Reset Limits] [Manage Files] [Cancel]          │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q, Announce: a, Scrape: s...) │
└─────────────────────────────────────────────────────────┘
```

### File Selection Screen
```
┌─────────────────────────────────────────────────────────┐
│ File Selection                                           │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Files Table                                         │ │
│ │ #  Selected  Priority  Progress  Size    File Name │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ 0  ✓         normal    100.0%    500 MB  file1.mp4 │ │
│ │ 1  ✓         high      45.0%     1.2 GB  file2.mkv │ │
│ │ 2            normal    0.0%      300 MB  file3.srt  │ │
│ │ 3  ✓         low       78.0%     800 MB  file4.avi  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ File Selection Status                               │ │
│ │ Total: 4 | Selected: 3 | Deselected: 1              │ │
│ └─────────────────────────────────────────────────────┘ │
│ Commands: Space=Toggle, A=Select All, D=Deselect All,  │
│           P=Priority, S=Save, Esc=Back                  │
└─────────────────────────────────────────────────────────┘
```

### Add Torrent Screen (Multi-step Form)
```
┌─────────────────────────────────────────────────────────┐
│ Step 1/11: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11│
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Step 1: Torrent Input                               │ │
│ │                                                     │ │
│ │ Enter torrent path or magnet URI:                  │ │
│ │ [magnet:?xt=urn:btih:abc123...________________]    │ │
│ │                                                     │ │
│ │ Or browse for .torrent file                         │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ [Cancel]                    [Previous] [Next] [Submit] │
└─────────────────────────────────────────────────────────┘

Step 2: Output Directory
Step 3: File Selection
Step 4: Rate Limits
Step 5: Queue Priority
Step 6: Resume Option
Step 7: Xet Options
Step 8: IPFS Options
Step 9: Scrape Options
Step 10: uTP Options
Step 11: NAT Options
```

### Xet Management Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Xet Protocol Status                                 │ │
│ │ Enabled: Yes                                        │ │
│ │ Deduplication: Enabled                              │ │
│ │ P2P CAS: Enabled                                    │ │
│ │ Compression: Enabled                                │ │
│ │ Chunk size range: 512-16384 bytes                   │ │
│ │ Target chunk size: 8192 bytes                       │ │
│ │ Cache DB: /path/to/cache.db                         │ │
│ │ Chunk store: /path/to/chunks                        │ │
│ │                                                     │ │
│ │ Runtime Status:                                     │ │
│ │   Protocol state: active                            │ │
│ │   P2P CAS client: Active                            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Xet Deduplication Cache Statistics                  │ │
│ │ Metric              Value                           │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total chunks        10,000                          │ │
│ │ Unique chunks       5,000                           │ │
│ │ Total size          5.2 GB                          │ │
│ │ Cache size          2.6 GB                          │ │
│ │ Average chunk size  8192 bytes                      │ │
│ │ Deduplication ratio 2.0                            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Xet Performance Metrics                             │ │
│ │ Metric                      Value                   │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Deduplication Efficiency    50.0%                   │ │
│ │ Space Saved                 2.6 GB (50.0%)         │ │
│ │ Deduplication Ratio         2.0x                    │ │
│ │ Average Chunk Size          8.0 KB                  │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Enable] [Disable] [Refresh] [Cache Info] [Cleanup]    │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q, Enable: e, Disable: d...)  │
└─────────────────────────────────────────────────────────┘
```

### IPFS Management Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ IPFS Protocol Status                                │ │
│ │ Connection: Connected                               │ │
│ │ Protocol state: active                              │ │
│ │ IPFS API URL: http://localhost:5001                 │ │
│ │ Gateway URLs: 2                                      │ │
│ │ Connected: Yes                                      │ │
│ │ Connected peers: 15                                 │ │
│ │ Content items: 25                                   │ │
│ │ Pinned items: 10                                    │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ IPFS Performance Metrics                            │ │
│ │ [Performance metrics displayed here]                │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌──────────────────────────┐ ┌──────────────────────┐ │
│ │ IPFS Content             │ │ IPFS Peers            │ │
│ │ CID          Size  Pin   │ │ Peer ID    Multiaddr │ │
│ │ ──────────── ───── ───── │ │ ────────── ──────────│ │
│ │ QmAbc123...  500MB  Yes  │ │ 12D3Koo... /ip4/... │ │
│ │ QmDef456...  1.2GB  No   │ │ 12D3Koo... /ip6/... │ │
│ └──────────────────────────┘ └──────────────────────┘ │
│ [Add File] [Get Content] [Pin] [Unpin] [Refresh]      │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q, Add: a, Get: g, Pin: p...) │
└─────────────────────────────────────────────────────────┘
```

### SSL Config Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ SSL/TLS Status                                      │ │
│ │ Tracker SSL: Enabled                                │ │
│ │ Peer SSL: Enabled                                   │ │
│ │ Certificate Verification: Enabled                   │ │
│ │ Protocol Version: TLSv1.3                           │ │
│ │ CA Certificates: /path/to/ca.crt                   │ │
│ │ Client Certificate: /path/to/client.crt             │ │
│ │ Client Key: Set                                     │ │
│ │ Allow Insecure Peers: No                            │ │
│ │ Cipher Suites: System default                       │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ SSL/TLS Configuration                               │ │
│ │ Setting              Current Value    Action        │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Tracker SSL          Enabled          Press 1/2    │ │
│ │ Peer SSL             Enabled          Press 3/4    │ │
│ │ Certificate Verify   Enabled          Press v/V    │ │
│ │ Protocol Version     TLSv1.3          Click Set... │ │
│ │ CA Certificates      /path/to/ca.crt   Click Set... │ │
│ │ Client Certificate   /path/to/client.crt Click...  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ SSL Performance Metrics                             │ │
│ │ [Performance metrics displayed here]                │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Enable Trackers] [Disable Trackers] [Enable Peers]     │
│ [Disable Peers] [Set CA Certs] [Set Client Cert]        │
│ [Set Protocol] [Verify On] [Verify Off] [Refresh]       │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q, Refresh: r, Enable: 1/3...)│
└─────────────────────────────────────────────────────────┘
```

### Proxy Config Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Proxy Status                                        │ │
│ │ Enabled: Yes                                        │ │
│ │ Type: SOCKS5                                        │ │
│ │ Host: proxy.example.com                             │ │
│ │ Port: 1080                                          │ │
│ │ Username: user                                      │ │
│ │ Password: ***                                      │ │
│ │ For Trackers: Yes                                  │ │
│ │ For Peers: Yes                                     │ │
│ │ For WebSeeds: No                                   │ │
│ │ Bypass List: localhost, 127.0.0.1                  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Proxy Statistics                                    │ │
│ │ Metric              Value                           │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total Connections   1,234                          │ │
│ │ Successful          1,200                          │ │
│ │ Failed              34                             │ │
│ │ Auth Failures       2                              │ │
│ │ Timeouts            5                              │ │
│ │ Bytes Sent          500 MB                         │ │
│ │ Bytes Received      2.5 GB                         │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Proxy Performance Metrics                           │ │
│ │ [Performance metrics displayed here]                │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Set Proxy] [Test Connection] [Disable] [Refresh]       │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q, Test: t, Refresh: r)       │
└─────────────────────────────────────────────────────────┘
```

### Scrape Results Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Scrape Cache Status                                 │ │
│ │ Total cached results: 25                            │ │
│ │                                                     │ │
│ │ Scrape results show tracker statistics (seeders,   │ │
│ │ leechers, completed downloads).                    │ │
│ │ Results are cached to avoid excessive tracker...    │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Cached Scrape Results                               │ │
│ │ Info Hash      Seeders  Leechers  Completed  Count │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ abc123...      1,234    567       5,678     15     │ │
│ │ def456...      890      234       3,456     12     │ │
│ │ ghi789...      567      123       2,345     8      │ │
│ │ ...                                                │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Refresh] [Scrape All]                                   │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q, Refresh: r)                 │
└─────────────────────────────────────────────────────────┘
```

### NAT Management Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ NAT Traversal Status                                │ │
│ │ Active Protocol: UPnP                               │ │
│ │ External IP: 203.0.113.42                          │ │
│ │                                                     │ │
│ │ Configuration:                                      │ │
│ │   Auto-map ports: Yes                              │ │
│ │   NAT-PMP enabled: Yes                             │ │
│ │   UPnP enabled: Yes                                 │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ NAT Performance Metrics                             │ │
│ │ [Performance metrics displayed here]                │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Active Port Mappings                                │ │
│ │ Protocol  Internal  External  Source    Expires    │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ TCP       6881      6881      UPnP      3600s      │ │
│ │ UDP       6881      6881      UPnP      3600s      │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Discover] [Map Port] [Unmap Port] [External IP] [Refresh]│
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q, Discover: d, Refresh: r)    │
└─────────────────────────────────────────────────────────┘
```

### uTP Config Screen
```
┌─────────────────────────────────────────────────────────┐
│ Header                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ uTP Status                                          │ │
│ │ Enabled: Yes                                        │ │
│ │                                                     │ │
│ │ uTP provides reliable, ordered delivery over UDP    │ │
│ │ with delay-based congestion control (BEP 29).      │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ uTP Configuration                                   │ │
│ │ Setting                  Value          Description │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Prefer over TCP          true           Prefer uTP..│ │
│ │ Connection Timeout       30s            Connection..│ │
│ │ Max Window Size          2,097,152 bytes Max receive│ │
│ │ MTU                      1,500 bytes    Maximum...  │ │
│ │ Initial Rate             64,000 B/s     Initial...  │ │
│ │ Min Rate                 1,000 B/s      Minimum...  │ │
│ │ Max Rate                 10,000,000 B/s Maximum...  │ │
│ │ ACK Interval             0.1s           ACK packet..│ │
│ │ Retransmit Timeout       2.0            RTT...      │ │
│ │ Max Retransmits          5              Maximum...  │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Enable] [Disable] [Config Get] [Config Set] [Config   │
│ Reset] [Refresh]                                         │
├─────────────────────────────────────────────────────────┤
│ Footer (Back: Esc, Quit: q, Enable: e, Disable: d...)   │
└─────────────────────────────────────────────────────────┘
```

### Confirmation Dialog (Modal)
```
┌─────────────────────────────────────────────────────────┐
│                                                          │
│              ┌────────────────────────────┐              │
│              │ Confirmation              │              │
│              ├────────────────────────────┤              │
│              │                            │              │
│              │ Are you sure you want to   │              │
│              │ delete this torrent?        │              │
│              │                            │              │
│              │                            │              │
│              │    [Yes]        [No]       │              │
│              └────────────────────────────┘              │
│                                                          │
└─────────────────────────────────────────────────────────┘
```



## Features

### Real-time Updates
Live torrent status and progress tracking, updated at configurable intervals. See [ccbt/interface/terminal_dashboard.py:_poll_once](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L389).

### Peer Monitoring
View connected peers, their speeds, and client information. See [ccbt/interface/terminal_dashboard.py:PeersTable](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L228).

### Speed Visualization
Download/upload speed graphs with sparklines. See [ccbt/interface/terminal_dashboard.py:SpeedSparklines](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L250).

### Alert System
Real-time notifications for important events. See [ccbt/interface/terminal_dashboard.py:491](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L491) for alert display.

### Interactive Controls
Keyboard shortcuts for common operations. See [ccbt/interface/terminal_dashboard.py:on_key](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3240).

### Multi-torrent Support
Monitor multiple downloads simultaneously. See [ccbt/interface/terminal_dashboard.py:TorrentsTable](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L221).

### Monitoring Screens
Specialized screens for detailed monitoring metrics:
- **System Resources** (`s`) - CPU, memory, disk, network I/O usage
- **Performance Metrics** (`m`) - Performance data from MetricsCollector and MetricsPlugin
- **Network Quality** (`n`) - Peer connection quality and network statistics
- **Historical Trends** (`h`) - Historical metric trends with sparklines
- **Alerts Dashboard** (`a`) - Alert rules, active alerts, and alert history
- **Metrics Explorer** (`e`) - Browse and explore all available metrics

See [Monitoring Screens](#monitoring-screens) section for details.

## Dashboard Layout

The dashboard is built with [Textual](https://textual.textualize.io/) and organized into panels:

### Layout Structure
- **Header**: Clock and application title. See [ccbt/interface/terminal_dashboard.py:323](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L323)
- **Body**: Split into left and right sections. See [ccbt/interface/terminal_dashboard.py:324](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L324)
- **Left Panel**: Overview and speed graphs
- **Right Panel**: Torrents, peers, details, and logs
- **Footer**: Status bar and alerts. See [ccbt/interface/terminal_dashboard.py:333-334](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L333-L334)

CSS styling: [ccbt/interface/terminal_dashboard.py:279-297](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L279-L297)

### Panels

#### Overview Panel
Displays global statistics. ImplementaciÃ³n: [ccbt/interface/terminal_dashboard.py:Overview](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L174)
- Download Speed: Current global download rate
- Upload Speed: Current global upload rate
- Connected Peers: Total number of connected peers
- Active Torrents: Number of downloading/seeding torrents
- Average Progress: Overall progress percentage

#### Torrents Panel
Shows all active torrents in a table. ImplementaciÃ³n: [ccbt/interface/terminal_dashboard.py:TorrentsTable](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L196)
- Info Hash: Torrent identifier
- Name: Torrent name
- Status: Current status (downloading, seeding, paused)
- Progress: Completion percentage
- Down/Up Rates: Transfer speeds

#### Peers Panel
Displays peers for the selected torrent. ImplementaciÃ³n: [ccbt/interface/terminal_dashboard.py:PeersTable](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L228)
- IP Address: Peer's IP address
- Port: Peer's port
- Down/Up Rates: Transfer speeds to/from peer
- Choked: Whether peer is choked
- Client: BitTorrent client identification

#### Speed Sparklines
Real-time speed visualization. ImplementaciÃ³n: [ccbt/interface/terminal_dashboard.py:SpeedSparklines](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L250)
- Download Graph: Sparkline showing download speed history
- Upload Graph: Sparkline showing upload speed history
- Maintains last 120 samples (~2 minutes at 1s refresh). See [ccbt/interface/terminal_dashboard.py:269](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L269)

#### Details Panel
Shows detailed information for the selected torrent. ImplementaciÃ³n: [ccbt/interface/terminal_dashboard.py:428-439](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L428-L439)

#### Alerts Panel
Displays alert rules and active alerts. ImplementaciÃ³n: [ccbt/interface/terminal_dashboard.py:3059-3102](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3059-L3102)

## Monitoring Screens

Bitonic provides specialized monitoring screens accessible from the main dashboard. Each screen focuses on a specific monitoring domain with detailed metrics and visualizations.

### System Resources Screen

**Access**: Press `s` from main dashboard

**Purpose**: Display system resource usage (CPU, memory, disk, network I/O).

**Features**:
- CPU usage percentage with progress bar
- Memory usage percentage with progress bar
- Disk usage percentage with progress bar
- Process count
- Network I/O statistics (bytes sent/received)

**Implementation**: [ccbt/interface/terminal_dashboard.py:SystemResourcesScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L690)

**Navigation**: Press `Escape` or `q` to return to main dashboard

### Performance Metrics Screen

**Access**: Press `m` from main dashboard

**Purpose**: Display performance metrics from MetricsCollector and MetricsPlugin.

**Features**:
- Peer connections count
- Download/upload speeds
- Pieces completed/failed statistics
- Tracker request/response statistics
- Event-driven metrics from MetricsPlugin (if available)
- Metrics collection statistics

**Implementation**: [ccbt/interface/terminal_dashboard.py:PerformanceMetricsScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L811)

**Data Sources**:
- `MetricsCollector.get_performance_metrics()`
- `MetricsCollector.get_metrics_statistics()`
- `MetricsPlugin.get_aggregates()` (if available)

**Navigation**: Press `Escape` or `q` to return to main dashboard

### Network Quality Screen

**Access**: Press `n` from main dashboard

**Purpose**: Display network quality metrics for peers and connections.

**Features**:
- Global network statistics
- Per-torrent network quality table
- Peer connection quality metrics with visual indicators
- Connection quality scoring (0-100)

**Implementation**: [ccbt/interface/terminal_dashboard.py:NetworkQualityScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L889)

**Quality Calculation**:
- Based on peer speeds and choke status
- Visual indicators: ████████ (excellent), ██████░░ (good), ████░░░░ (fair), ██░░░░░░ (poor)

**Navigation**: Press `Escape` or `q` to return to main dashboard

### Historical Trends Screen

**Access**: Press `h` from main dashboard

**Purpose**: Display historical trends for various metrics using sparklines.

**Features**:
- Multiple sparkline widgets for different metrics
- Historical data storage (last 120 samples, ~2 minutes)
- Summary table with current, min, max, and average values
- Automatic metric formatting (rates, percentages, counts)

**Metrics Tracked**:
- Download/upload rates
- CPU usage
- Memory usage
- Peer connections

**Implementation**: [ccbt/interface/terminal_dashboard.py:HistoricalTrendsScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L1059)

**Navigation**: Press `Escape` or `q` to return to main dashboard

### Alerts Dashboard Screen

**Access**: Press `a` from main dashboard

**Purpose**: Enhanced alerts display with filtering and management.

**Features**:
- Alert rules table (name, metric, condition, severity, enabled status)
- Active alerts table (severity, rule, metric, value, timestamp)
- Alert history (last 50 alerts with resolution status)
- Alert statistics (triggered, resolved, notifications sent)

**Implementation**: [ccbt/interface/terminal_dashboard.py:AlertsDashboardScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L1201)

**Severity Formatting**:
- **CRITICAL**: Bold red
- **ERROR**: Red
- **WARNING**: Yellow
- **INFO**: Dim

**Navigation**: Press `Escape` or `q` to return to main dashboard

### Metrics Explorer Screen

**Access**: Press `e` from main dashboard

**Purpose**: Explore all available metrics with filtering and detailed views.

**Features**:
- Complete metrics list from MetricsCollector
- Filter/search by metric name or description
- Detailed metric information panel
- Metric type, description, aggregation, retention
- Current and aggregated values
- Labels and metadata

**Implementation**: [ccbt/interface/terminal_dashboard.py:MetricsExplorerScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L1376)

**Usage**:
- Type in filter input and press `Enter` to filter metrics
- Navigate with arrow keys to select metrics
- View detailed information in the details panel below

**Navigation**: Press `Escape` or `q` to return to main dashboard

## Configuration Screens

Bitonic provides configuration screens for managing global and per-torrent settings.

### Global Configuration Screen

**Access**: Press `g` from main dashboard

**Purpose**: Configure global application settings.

**Features**:
- Section-based configuration navigation
- Editable configuration fields with validation
- Save to runtime or file
- Unsaved changes detection with confirmation dialog

**Implementation**: [ccbt/interface/terminal_dashboard.py:GlobalConfigMainScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L1793)

**Sections Available**:
- Network configuration
- Disk I/O settings
- Discovery (DHT, PEX, trackers)
- Observability (logging, metrics, tracing)
- Security settings
- And more...

**Navigation**: Press `Escape` or `q` to return to main dashboard

### Per-Torrent Configuration Screen

**Access**: Press `t` from main dashboard

**Purpose**: Configure settings for individual torrents.

**Features**:
- Torrent selection interface
- Rate limit configuration (download/upload)
- Queue priority management
- File selection status
- Torrent operations (announce, scrape, pause, resume, etc.)

**Implementation**: [ccbt/interface/terminal_dashboard.py:PerTorrentConfigMainScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L2241)

**Operations Available**:
- Set rate limits (KiB/s, 0 = unlimited)
- Change queue priority
- Force announce (`a` key)
- Force scrape (`s` key)
- Refresh PEX (`e` key)
- Rehash torrent (`h` key)
- Pause/Resume torrent (`p`/`r` keys)
- Remove torrent (`Delete` key)

**Navigation**: Press `Escape` or `q` to return to main dashboard

## Keyboard Shortcuts

All keyboard shortcuts are defined in [ccbt/interface/terminal_dashboard.py:on_key](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L505) and [ccbt/interface/terminal_dashboard.py:BINDINGS](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L337).

### Navigation
- `↑/↓` - Navigate torrent list (DataTable navigation)
- `Enter` - Handle file browser selection. See [ccbt/interface/terminal_dashboard.py:714](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L714)

### Torrent Control
- `P` / `p` - Pause selected torrent. See [ccbt/interface/terminal_dashboard.py:534](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L534)
- `R` / `r` - Resume selected torrent. See [ccbt/interface/terminal_dashboard.py:541](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L541)
- `Delete` - Delete selected torrent (with confirmation). See [ccbt/interface/terminal_dashboard.py:510](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L510)
- `y` - Confirm deletion. See [ccbt/interface/terminal_dashboard.py:523](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L523)
- `n` - Cancel deletion. See [ccbt/interface/terminal_dashboard.py:530](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L530)

### Advanced Actions
- `a` / `A` - Force announce (when torrent selected). See [ccbt/interface/terminal_dashboard.py:3182](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3182)
- `s` / `S` - Force scrape (when torrent selected). See [ccbt/interface/terminal_dashboard.py:3197](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3197)
- `e` / `E` - Refresh PEX (when torrent selected). See [ccbt/interface/terminal_dashboard.py:3207](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3207)
- `h` / `H` - Rehash torrent (when torrent selected). See [ccbt/interface/terminal_dashboard.py:3217](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3217)
- `x` / `X` - Export session snapshot. See [ccbt/interface/terminal_dashboard.py:3227](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3227)

### Monitoring Screens Navigation
- `s` - Open System Resources screen. See [ccbt/interface/terminal_dashboard.py:action_system_resources](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3880)
- `m` - Open Performance Metrics screen. See [ccbt/interface/terminal_dashboard.py:action_performance_metrics](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3884)
- `n` - Open Network Quality screen. See [ccbt/interface/terminal_dashboard.py:action_network_quality](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3888)
- `h` - Open Historical Trends screen. See [ccbt/interface/terminal_dashboard.py:action_historical_trends](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3892)
- `a` - Open Alerts Dashboard screen. See [ccbt/interface/terminal_dashboard.py:action_alerts_dashboard](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3896)
- `e` - Open Metrics Explorer screen. See [ccbt/interface/terminal_dashboard.py:action_metrics_explorer](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3900)

### Configuration Screens
- `g` - Open Global Configuration screen. See [ccbt/interface/terminal_dashboard.py:action_global_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3870)
- `t` - Open Per-Torrent Configuration screen. See [ccbt/interface/terminal_dashboard.py:action_torrent_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3875)

### Rate Limiting
- `1` - Disable rate limits. See [ccbt/interface/terminal_dashboard.py:627](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L627)
- `2` - Set rate limits to 1024 KiB/s. See [ccbt/interface/terminal_dashboard.py:635](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L635)

### Dashboard Control
- `Q` / `q` - Quit dashboard. See [ccbt/interface/terminal_dashboard.py:507](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L507)
- `/` - Open filter input. See [ccbt/interface/terminal_dashboard.py:548](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L548)
- `:` - Open command palette. See [ccbt/interface/terminal_dashboard.py:561](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L561)
- `m` / `M` - Toggle metrics collection interval. See [ccbt/interface/terminal_dashboard.py:645](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L645)
- `R` - Toggle dashboard refresh interval. See [ccbt/interface/terminal_dashboard.py:659](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L659)
- `t` / `T` - Toggle light/dark theme. See [ccbt/interface/terminal_dashboard.py:673](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L673)
- `c` / `C` - Toggle compact mode. See [ccbt/interface/terminal_dashboard.py:681](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L681)
- `k` / `K` - Acknowledge all active alerts. See [ccbt/interface/terminal_dashboard.py:723](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L723)

### Adding Torrents
- `i` / `I` - Quick add torrent. See [ccbt/interface/terminal_dashboard.py:702](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L702)
- `o` / `O` - Advanced add torrent. See [ccbt/interface/terminal_dashboard.py:706](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L706)
- `b` / `B` - Browse for torrent file. See [ccbt/interface/terminal_dashboard.py:710](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L710)

## Configuration

Dashboard settings are configured in [ccbt.toml:185-191](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L185-L191):

- `refresh_interval`: UI refresh interval in seconds (default: 1.0)
- `default_view`: Default dashboard view

Alert rules are loaded from the path specified in [ccbt.toml:170](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L170) (`alerts_rules_path`). See [ccbt/interface/terminal_dashboard.py:363-381](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L363-L381) for automatic loading.

## Command Palette

Press `:` to open the command palette. Available commands:
- `pause` - Pause selected torrent
- `resume` - Resume selected torrent
- `remove` - Remove selected torrent
- `announce` - Force announce
- `scrape` - Force scrape
- `pex` - Refresh PEX
- `rehash` - Rehash torrent
- `limit <down> <up>` - Set rate limits (KiB/s)
- `backup <path>` - Backup checkpoint
- `restore <path>` - Restore checkpoint

ImplementaciÃ³n: [ccbt/interface/terminal_dashboard.py:_run_command](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L776)

## Filtering

Press `/` to filter torrents by name or status. ImplementaciÃ³n: [ccbt/interface/terminal_dashboard.py:_apply_filter_and_update](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L762)

## Integration with Monitoring

Bitonic integrates with ccBitTorrent's monitoring system:
- Metrics collection via [ccbt/monitoring/metrics_collector.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/monitoring/metrics_collector.py)
- Alert management via [ccbt/monitoring/alert_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/monitoring/alert_manager.py)
- Plugin system via [ccbt/plugins/base.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/plugins/base.py)
- MetricsPlugin integration for event-driven metrics. See [ccbt/interface/terminal_dashboard.py:_get_metrics_plugin](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L626)
- System metrics tracking. See [ccbt/interface/terminal_dashboard.py:3001-3019](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3001-L3019)

### Metrics Sources

Bitonic displays metrics from multiple sources:

1. **MetricsCollector**: System-level and performance metrics
   - CPU, memory, disk usage
   - Network I/O statistics
   - Peer connections, speeds, pieces statistics

2. **MetricsPlugin**: Event-driven metrics
   - Piece download speeds
   - Torrent average speeds
   - Event-based aggregations

3. **AsyncSessionManager**: Session-level statistics
   - Global download/upload rates
   - Per-torrent status
   - Peer information

### Plugin Manager Integration

Bitonic uses the global plugin manager singleton to access plugins:
- Access via `get_plugin_manager()` function. See [ccbt/plugins/base.py:get_plugin_manager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/plugins/base.py#L403)
- MetricsPlugin discovery through multiple methods (PluginManager, event bus, session attributes)
- Graceful handling when plugins are not available

## Troubleshooting

### Dashboard Won't Start
1. Check if Textual is installed: `uv pip install textual>=0.73.0`
2. Verify terminal supports Unicode and colors
3. Check error messages in the terminal

Implementation handles Textual availability: [ccbt/interface/terminal_dashboard.py:46-172](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L46-L172)

### Performance Issues
1. Increase refresh interval: `--refresh 2.0` or press `R` to cycle intervals
2. Use compact mode: Press `c` to toggle
3. Disable speed graphs if not needed

### Missing Data
1. Ensure torrents are actively downloading
2. Check network connectivity
3. Verify peer connections are established

## Architecture

Bitonic uses:
- **Textual**: Terminal UI framework. See [ccbt/interface/terminal_dashboard.py:47-60](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L47-L60)
- **Rich**: Rich text and beautiful formatting
- **AsyncSessionManager**: Session management. See [ccbt/session/session.py:AsyncSessionManager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py#L605)
- **MetricsCollector**: Metrics collection (singleton via `get_metrics_collector()`)
- **AlertManager**: Alert management (singleton via `get_alert_manager()`)
- **PluginManager**: Plugin management (singleton via `get_plugin_manager()`)

### Screen Architecture

Bitonic follows a hierarchical screen structure:

```
TerminalDashboard (Main App)
├── ConfigScreen (Base class)
│   ├── GlobalConfigMainScreen
│   ├── GlobalConfigDetailScreen
│   ├── PerTorrentConfigMainScreen
│   └── TorrentConfigDetailScreen
└── MonitoringScreen (Base class)
    ├── SystemResourcesScreen
    ├── PerformanceMetricsScreen
    ├── NetworkQualityScreen
    ├── HistoricalTrendsScreen
    ├── AlertsDashboardScreen
    └── MetricsExplorerScreen
```

**Base Classes**:
- **MonitoringScreen**: Base class for all monitoring screens with common functionality (refresh intervals, navigation, error handling). See [ccbt/interface/terminal_dashboard.py:MonitoringScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L558)
- **ConfigScreen**: Base class for configuration screens with unsaved changes detection. See [ccbt/interface/terminal_dashboard.py:ConfigScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L433)

**Reusable Widgets**:
- **ProgressBarWidget**: Progress bars for percentages. See [ccbt/interface/terminal_dashboard.py:ProgressBarWidget](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L309)
- **MetricsTableWidget**: Metrics display in table format. See [ccbt/interface/terminal_dashboard.py:MetricsTableWidget](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L335)
- **SparklineGroup**: Multiple sparklines with labels. See [ccbt/interface/terminal_dashboard.py:SparklineGroup](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L379)

**Confirmation Dialogs**:
- **ConfirmationDialog**: Modal dialog for confirmation prompts (e.g., unsaved changes). See [ccbt/interface/terminal_dashboard.py:ConfirmationDialog](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L471)

For more information, see:
- [API Reference](API.md) - Python API documentation including monitoring features
- [btbt CLI Reference](btbt-cli.md) - Command-line interface