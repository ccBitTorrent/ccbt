"""Generate complete translation files for Spanish and Basque."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

# Spanish translations mapping
SPANISH_TRANSLATIONS = {
    "\nAvailable Commands:\n  help          - Show this help message\n  status        - Show current status\n  peers         - Show connected peers\n  files         - Show file information\n  pause         - Pause download\n  resume        - Resume download\n  stop          - Stop download\n  quit          - Quit application\n  clear         - Clear screen\n        ": "\nComandos disponibles:\n  help          - Mostrar este mensaje de ayuda\n  status        - Mostrar estado actual\n  peers         - Mostrar pares conectados\n  files         - Mostrar información de archivos\n  pause         - Pausar descarga\n  resume        - Reanudar descarga\n  stop          - Detener descarga\n  quit          - Salir de la aplicación\n  clear         - Limpiar pantalla\n        ",
    "\n[bold cyan]File Selection[/bold cyan]": "\n[bold cyan]Selección de archivos[/bold cyan]",
    "\n[bold]File selection[/bold]": "\n[bold]Selección de archivos[/bold]",
    "\n[yellow]Commands:[/yellow]": "\n[yellow]Comandos:[/yellow]",
    "\n[yellow]File selection cancelled, using defaults[/yellow]": "\n[yellow]Selección de archivos cancelada, usando valores por defecto[/yellow]",
    "\n[yellow]Tracker Scrape Statistics:[/yellow]": "\n[yellow]Estadísticas de scrape del tracker:[/yellow]",
    "\n[yellow]Use: files select <index>, files deselect <index>, files priority <index> <priority>[/yellow]": "\n[yellow]Uso: files select <index>, files deselect <index>, files priority <index> <priority>[/yellow]",
    "\n[yellow]Warning: No peers connected after 30 seconds[/yellow]": "\n[yellow]Advertencia: No hay pares conectados después de 30 segundos[/yellow]",
    "  [cyan]deselect <index>[/cyan] - Deselect a file": "  [cyan]deselect <index>[/cyan] - Deseleccionar un archivo",
    "  [cyan]deselect-all[/cyan] - Deselect all files": "  [cyan]deselect-all[/cyan] - Deseleccionar todos los archivos",
    "  [cyan]done[/cyan] - Finish selection and start download": "  [cyan]done[/cyan] - Finalizar selección y comenzar descarga",
    "  [cyan]priority <index> <priority>[/cyan] - Set priority (do_not_download/low/normal/high/maximum)": "  [cyan]priority <index> <priority>[/cyan] - Establecer prioridad (do_not_download/low/normal/high/maximum)",
    "  [cyan]select <index>[/cyan] - Select a file": "  [cyan]select <index>[/cyan] - Seleccionar un archivo",
    "  [cyan]select-all[/cyan] - Select all files": "  [cyan]select-all[/cyan] - Seleccionar todos los archivos",
    "  • Check if torrent has active seeders": "  • Verificar si el torrent tiene seeders activos",
    "  • Ensure DHT is enabled: --enable-dht": "  • Asegúrese de que DHT esté habilitado: --enable-dht",
    "  • Run 'btbt diagnose-connections' to check connection status": "  • Ejecute 'btbt diagnose-connections' para verificar el estado de la conexión",
    "  • Verify NAT/firewall settings": "  • Verificar configuración NAT/pare-fuego",
    " | Files: {selected}/{total} selected": " | Archivos: {selected}/{total} seleccionados",
    " | Private: {count}": " | Privado: {count}",
    "Active": "Activo",
    "Active Alerts": "Alertas activas",
    "Active: {count}": "Activo: {count}",
    "Advanced Add": "Agregar avanzado",
    "Alert Rules": "Reglas de alerta",
    "Alerts": "Alertas",
    "Announce: Failed": "Anuncio: Fallido",
    "Announce: {status}": "Anuncio: {status}",
    "Are you sure you want to quit?": "¿Está seguro de que desea salir?",
    "Automatically restart daemon if needed (without prompt)": "Reiniciar automáticamente el demonio si es necesario (sin solicitud)",
    "Browse": "Navegar",
    "Capability": "Capacidad",
    "Commands: ": "Comandos: ",
    "Completed": "Completado",
    "Completed (Scrape)": "Completado (Scrape)",
    "Component": "Componente",
    "Condition": "Condición",
    "Config Backups": "Copias de seguridad de configuración",
    "Configuration file path": "Ruta del archivo de configuración",
    "Confirm": "Confirmar",
    "Connected": "Conectado",
    "Connected Peers": "Pares conectados",
    "Count: {count}{file_info}{private_info}": "Contador: {count}{file_info}{private_info}",
    "Create backup before migration": "Crear copia de seguridad antes de la migración",
    "DHT": "DHT",
    "Description": "Descripción",
    "Details": "Detalles",
    "Disabled": "Deshabilitado",
    "Download": "Descargar",
    "Download Speed": "Velocidad de descarga",
    "Download paused": "Descarga pausada",
    "Download resumed": "Descarga reanudada",
    "Download stopped": "Descarga detenida",
    "Downloaded": "Descargado",
    "Downloading {name}": "Descargando {name}",
    "ETA": "Tiempo estimado",
    "Enable debug mode": "Habilitar modo de depuración",
    "Enable verbose output": "Habilitar salida detallada",
    "Enabled": "Habilitado",
    "Error reading scrape cache": "Error al leer la caché de scrape",
    "Explore": "Explorar",
    "Failed": "Fallido",
    "Failed to register torrent in session": "Error al registrar el torrent en la sesión",
    "File": "Archivo",
    "File Name": "Nombre del archivo",
    "File selection not available for this torrent": "Selección de archivos no disponible para este torrent",
    "Files": "Archivos",
    "Global Config": "Configuración global",
    "Help": "Ayuda",
    "History": "Historial",
    "ID": "ID",
    "IP": "IP",
    "IP Filter": "Filtro IP",
    "IPFS": "IPFS",
    "Info Hash": "Hash de información",
    "Interactive backup": "Copia de seguridad interactiva",
    "Invalid torrent file format": "Formato de archivo torrent inválido",
    "Key": "Clave",
    "Key not found: {key}": "Clave no encontrada: {key}",
    "Last Scrape": "Último scrape",
    "Leechers": "Leechers",
    "Leechers (Scrape)": "Leechers (Scrape)",
    "MIGRATED": "MIGRADO",
    "Menu": "Menú",
    "Metric": "Métrica",
    "NAT Management": "Gestión NAT",
    "Name": "Nombre",
    "Network": "Red",
    "No": "No",
    "No active alerts": "No hay alertas activas",
    "No alert rules": "No hay reglas de alerta",
    "No alert rules configured": "No hay reglas de alerta configuradas",
    "No backups found": "No se encontraron copias de seguridad",
    "No cached results": "No hay resultados en caché",
    "No checkpoints": "No hay puntos de control",
    "No config file to backup": "No hay archivo de configuración para respaldar",
    "No peers connected": "No hay pares conectados",
    "No profiles available": "No hay perfiles disponibles",
    "No templates available": "No hay plantillas disponibles",
    "No torrent active": "No hay torrent activo",
    "Nodes: {count}": "Nodos: {count}",
    "Not available": "No disponible",
    "Not configured": "No configurado",
    "Not supported": "No soportado",
    "OK": "OK",
    "Operation not supported": "Operación no soportada",
    "PEX: {status}": "PEX: {status}",
    "Pause": "Pausar",
    "Peers": "Pares",
    "Performance": "Rendimiento",
    "Pieces": "Piezas",
    "Port": "Puerto",
    "Port: {port}": "Puerto: {port}",
    "Priority": "Prioridad",
    "Private": "Privado",
    "Profiles": "Perfiles",
    "Progress": "Progreso",
    "Property": "Propiedad",
    "Proxy Config": "Configuración de proxy",
    "PyYAML is required for YAML output": "PyYAML es requerido para salida YAML",
    "Quick Add": "Agregar rápido",
    "Quit": "Salir",
    "Rate limits disabled": "Límites de velocidad deshabilitados",
    "Rate limits set to 1024 KiB/s": "Límites de velocidad establecidos a 1024 KiB/s",
    "Rehash: {status}": "Rehash: {status}",
    "Resume": "Reanudar",
    "Rule": "Regla",
    "Rule not found: {name}": "Regla no encontrada: {name}",
    "Rules: {rules}, IPv4: {ipv4}, IPv6: {ipv6}, Blocks: {blocks}": "Reglas: {rules}, IPv4: {ipv4}, IPv6: {ipv6}, Bloqueos: {blocks}",
    "Running": "En ejecución",
    "SSL Config": "Configuración SSL",
    "Scrape Results": "Resultados de scrape",
    "Scrape: {status}": "Scrape: {status}",
    "Section not found: {section}": "Sección no encontrada: {section}",
    "Security Scan": "Escaneo de seguridad",
    "Seeders": "Seeders",
    "Seeders (Scrape)": "Seeders (Scrape)",
    "Select files to download": "Seleccionar archivos para descargar",
    "Selected": "Seleccionado",
    "Session": "Sesión",
    "Set value in global config file": "Establecer valor en archivo de configuración global",
    "Set value in project local ccbt.toml": "Establecer valor en ccbt.toml local del proyecto",
    "Severity": "Severidad",
    "Show specific key path (e.g. network.listen_port)": "Mostrar ruta de clave específica (ej. network.listen_port)",
    "Show specific section key path (e.g. network)": "Mostrar ruta de clave de sección específica (ej. network)",
    "Size": "Tamaño",
    "Skip confirmation prompt": "Omitir solicitud de confirmación",
    "Skip daemon restart even if needed": "Omitir reinicio del demonio incluso si es necesario",
    "Snapshot failed: {error}": "Instantánea fallida: {error}",
    "Snapshot saved to {path}": "Instantánea guardada en {path}",
    "Status": "Estado",
    "Status: ": "Estado: ",
    "Supported": "Soportado",
    "System Capabilities": "Capacidades del sistema",
    "System Capabilities Summary": "Resumen de capacidades del sistema",
    "System Resources": "Recursos del sistema",
    "Templates": "Plantillas",
    "Timestamp": "Marca de tiempo",
    "Torrent Config": "Configuración del torrent",
    "Torrent Status": "Estado del torrent",
    "Torrent file not found": "Archivo torrent no encontrado",
    "Torrent not found": "Torrent no encontrado",
    "Torrents": "Torrents",
    "Torrents: {count}": "Torrents: {count}",
    "Tracker Scrape": "Scrape del tracker",
    "Type": "Tipo",
    "Unknown": "Desconocido",
    "Unknown subcommand": "Subcomando desconocido",
    "Unknown subcommand: {sub}": "Subcomando desconocido: {sub}",
    "Upload": "Subir",
    "Upload Speed": "Velocidad de subida",
    "Uptime: {uptime:.1f}s": "Tiempo de actividad: {uptime:.1f}s",
    "Usage: alerts list|list-active|add|remove|clear|load|save|test ...": "Uso: alerts list|list-active|add|remove|clear|load|save|test ...",
    "Usage: backup <info_hash> <dest>": "Uso: backup <info_hash> <dest>",
    "Usage: checkpoint list": "Uso: checkpoint list",
    "Usage: config [show|get|set|reload] ...": "Uso: config [show|get|set|reload] ...",
    "Usage: config get <key.path>": "Uso: config get <key.path>",
    "Usage: config set <key.path> <value>": "Uso: config set <key.path> <value>",
    "Usage: config_backup list|create [desc]|restore <file>": "Uso: config_backup list|create [desc]|restore <file>",
    "Usage: config_diff <file1> <file2>": "Uso: config_diff <file1> <file2>",
    "Usage: config_export <toml|json|yaml> <output>": "Uso: config_export <toml|json|yaml> <output>",
    "Usage: config_import <toml|json|yaml> <input>": "Uso: config_import <toml|json|yaml> <input>",
    "Usage: export <path>": "Uso: export <path>",
    "Usage: import <path>": "Uso: import <path>",
    "Usage: limits [show|set] <info_hash> [down up]": "Uso: limits [show|set] <info_hash> [down up]",
    "Usage: limits set <info_hash> <down_kib> <up_kib>": "Uso: limits set <info_hash> <down_kib> <up_kib>",
    "Usage: metrics show [system|performance|all] | metrics export [json|prometheus] [output]": "Uso: metrics show [system|performance|all] | metrics export [json|prometheus] [output]",
    "Usage: profile list | profile apply <name>": "Uso: profile list | profile apply <name>",
    "Usage: restore <backup_file>": "Uso: restore <backup_file>",
    "Usage: template list | template apply <name> [merge]": "Uso: template list | template apply <name> [merge]",
    "Use --confirm to proceed with reset": "Use --confirm para proceder con el reinicio",
    "VALID": "VÁLIDO",
    "Value": "Valor",
    "Welcome": "Bienvenido",
    "Xet": "Xet",
    "Yes": "Sí",
    "Yes (BEP 27)": "Sí (BEP 27)",
    "[cyan]Adding magnet link and fetching metadata...[/cyan]": "[cyan]Agregando enlace magnético y obteniendo metadatos...[/cyan]",
    "[cyan]Downloading: {progress:.1f}% ({peers} peers)[/cyan]": "[cyan]Descargando: {progress:.1f}% ({peers} pares)[/cyan]",
    "[cyan]Downloading: {progress:.1f}% ({rate:.2f} MB/s, {peers} peers)[/cyan]": "[cyan]Descargando: {progress:.1f}% ({rate:.2f} MB/s, {peers} pares)[/cyan]",
    "[cyan]Initializing session components...[/cyan]": "[cyan]Inicializando componentes de sesión...[/cyan]",
    "[cyan]Troubleshooting:[/cyan]": "[cyan]Solución de problemas:[/cyan]",
    "[cyan]Waiting for session components to be ready (max 60s)...[/cyan]": "[cyan]Esperando que los componentes de sesión estén listos (máx 60s)...[/cyan]",
    "[dim]Consider using daemon commands or stop the daemon first: 'btbt daemon exit'[/dim]": "[dim]Considere usar comandos del demonio o detener el demonio primero: 'btbt daemon exit'[/dim]",
    "[green]All files selected[/green]": "[green]Todos los archivos seleccionados[/green]",
    "[green]Applied auto-tuned configuration[/green]": "[green]Configuración auto-ajustada aplicada[/green]",
    "[green]Applied profile {name}[/green]": "[green]Perfil {name} aplicado[/green]",
    "[green]Applied template {name}[/green]": "[green]Plantilla {name} aplicada[/green]",
    "[green]Backup created: {path}[/green]": "[green]Copia de seguridad creada: {path}[/green]",
    "[green]Cleaned up {count} old checkpoints[/green]": "[green]{count} puntos de control antiguos limpiados[/green]",
    "[green]Cleared active alerts[/green]": "[green]Alertas activas eliminadas[/green]",
    "[green]Configuration reloaded[/green]": "[green]Configuración recargada[/green]",
    "[green]Configuration restored[/green]": "[green]Configuración restaurada[/green]",
    "[green]Connected to {count} peer(s)[/green]": "[green]Conectado a {count} par(es)[/green]",
    "[green]Daemon status: {status}[/green]": "[green]Estado del demonio: {status}[/green]",
    "[green]Download completed, stopping session...[/green]": "[green]Descarga completada, deteniendo sesión...[/green]",
    "[green]Download completed: {name}[/green]": "[green]Descarga completada: {name}[/green]",
    "[green]Exported checkpoint to {path}[/green]": "[green]Punto de control exportado a {path}[/green]",
    "[green]Exported configuration to {out}[/green]": "[green]Configuración exportada a {out}[/green]",
    "[green]Imported configuration[/green]": "[green]Configuración importada[/green]",
    "[green]Loaded {count} rules[/green]": "[green]{count} reglas cargadas[/green]",
    "[green]Magnet added successfully: {hash}...[/green]": "[green]Enlace magnético agregado exitosamente: {hash}...[/green]",
    "[green]Magnet added to daemon: {hash}[/green]": "[green]Enlace magnético agregado al demonio: {hash}[/green]",
    "[green]Metadata fetched successfully![/green]": "[green]¡Metadatos obtenidos exitosamente![/green]",
    "[green]Migrated checkpoint to {path}[/green]": "[green]Punto de control migrado a {path}[/green]",
    "[green]Monitoring started[/green]": "[green]Monitoreo iniciado[/green]",
    "[green]Resuming download from checkpoint...[/green]": "[green]Reanudando descarga desde punto de control...[/green]",
    "[green]Rule added[/green]": "[green]Regla agregada[/green]",
    "[green]Rule evaluated[/green]": "[green]Regla evaluada[/green]",
    "[green]Rule removed[/green]": "[green]Regla eliminada[/green]",
    "[green]Saved rules[/green]": "[green]Reglas guardadas[/green]",
    "[green]Selected file {idx}[/green]": "[green]Archivo {idx} seleccionado[/green]",
    "[green]Selected {count} file(s) for download[/green]": "[green]{count} archivo(s) seleccionado(s) para descargar[/green]",
    "[green]Set priority for file {idx} to {priority}[/green]": "[green]Prioridad establecida para archivo {idx} a {priority}[/green]",
    "[green]Starting web interface on http://{host}:{port}[/green]": "[green]Iniciando interfaz web en http://{host}:{port}[/green]",
    "[green]Torrent added to daemon: {hash}[/green]": "[green]Torrent agregado al demonio: {hash}[/green]",
    "[green]Updated runtime configuration[/green]": "[green]Configuración de tiempo de ejecución actualizada[/green]",
    "[green]Wrote metrics to {out}[/green]": "[green]Métricas escritas en {out}[/green]",
    "[red]Backup failed: {msgs}[/red]": "[red]Copia de seguridad fallida: {msgs}[/red]",
    "[red]Error: Could not parse magnet link[/red]": "[red]Error: No se pudo analizar el enlace magnético[/red]",
    "[red]Error: {error}[/red]": "[red]Error: {error}[/red]",
    "[red]Failed to add magnet link: {error}[/red]": "[red]Error al agregar enlace magnético: {error}[/red]",
    "[red]Failed to set config: {error}[/red]": "[red]Error al establecer configuración: {error}[/red]",
    "[red]File not found: {error}[/red]": "[red]Archivo no encontrado: {error}[/red]",
    "[red]Invalid arguments[/red]": "[red]Argumentos inválidos[/red]",
    "[red]Invalid file index: {idx}[/red]": "[red]Índice de archivo inválido: {idx}[/red]",
    "[red]Invalid file index[/red]": "[red]Índice de archivo inválido[/red]",
    "[red]Invalid info hash format: {hash}[/red]": "[red]Formato de hash de información inválido: {hash}[/red]",
    "[red]Invalid priority. Use: do_not_download/low/normal/high/maximum[/red]": "[red]Prioridad inválida. Use: do_not_download/low/normal/high/maximum[/red]",
    "[red]Invalid priority: {priority}. Use: do_not_download/low/normal/high/maximum[/red]": "[red]Prioridad inválida: {priority}. Use: do_not_download/low/normal/high/maximum[/red]",
    "[red]Invalid torrent file: {error}[/red]": "[red]Archivo torrent inválido: {error}[/red]",
    "[red]Key not found: {key}[/red]": "[red]Clave no encontrada: {key}[/red]",
    "[red]No checkpoint found for {hash}[/red]": "[red]No se encontró punto de control para {hash}[/red]",
    "[red]PyYAML not installed[/red]": "[red]PyYAML no instalado[/red]",
    "[red]Reload failed: {error}[/red]": "[red]Recarga fallida: {error}[/red]",
    "[red]Restore failed: {msgs}[/red]": "[red]Restauración fallida: {msgs}[/red]",
    "[red]{error}[/red]": "[red]{error}[/red]",
    "[yellow]All files deselected[/yellow]": "[yellow]Todos los archivos deseleccionados[/yellow]",
    "[yellow]Debug mode not yet implemented[/yellow]": "[yellow]Modo de depuración aún no implementado[/yellow]",
    "[yellow]Deselected file {idx}[/yellow]": "[yellow]Archivo {idx} deseleccionado[/yellow]",
    "[yellow]Download interrupted by user[/yellow]": "[yellow]Descarga interrumpida por el usuario[/yellow]",
    "[yellow]Fetching metadata from peers...[/yellow]": "[yellow]Obteniendo metadatos de pares...[/yellow]",
    "[yellow]Invalid priority spec '{spec}': {error}[/yellow]": "[yellow]Especificación de prioridad inválida '{spec}': {error}[/yellow]",
    "[yellow]Keeping session alive[/yellow]": "[yellow]Manteniendo sesión activa[/yellow]",
    "[yellow]No checkpoints found[/yellow]": "[yellow]No se encontraron puntos de control[/yellow]",
    "[yellow]Torrent session ended[/yellow]": "[yellow]Sesión de torrent finalizada[/yellow]",
    "[yellow]Unknown command: {cmd}[/yellow]": "[yellow]Comando desconocido: {cmd}[/yellow]",
    "[yellow]Warning: Daemon is running. Starting local session may cause port conflicts.[/yellow]": "[yellow]Advertencia: El demonio está en ejecución. Iniciar sesión local puede causar conflictos de puerto.[/yellow]",
    "[yellow]Warning: Error stopping session: {error}[/yellow]": "[yellow]Advertencia: Error al detener sesión: {error}[/yellow]",
    "[yellow]{warning}[/yellow]": "[yellow]{warning}[/yellow]",
    "ccBitTorrent Interactive CLI": "CLI interactivo de ccBitTorrent",
    "ccBitTorrent Status": "Estado de ccBitTorrent",
    "help, status, peers, files, pause, resume, stop, config, limits, strategy, discovery, checkpoint, metrics, alerts, export, import, backup, restore, capabilities, auto_tune, template, profile, config_backup, config_diff, config_export, config_import, config_schema": "help, status, peers, files, pause, resume, stop, config, limits, strategy, discovery, checkpoint, metrics, alerts, export, import, backup, restore, capabilities, auto_tune, template, profile, config_backup, config_diff, config_export, config_import, config_schema",
    "uTP Config": "Configuración uTP",
    "{count} features": "{count} características",
    "{count} items": "{count} elementos",
    "{elapsed:.0f}s ago": "hace {elapsed:.0f}s",
}

# Basque translations mapping (Euskara)
BASQUE_TRANSLATIONS = {
    "\nAvailable Commands:\n  help          - Show this help message\n  status        - Show current status\n  peers         - Show connected peers\n  files         - Show file information\n  pause         - Pause download\n  resume        - Resume download\n  stop          - Stop download\n  quit          - Quit application\n  clear         - Clear screen\n        ": "\nKomando erabilgarriak:\n  help          - Laguntza mezu hau erakusteko\n  status        - Egoera orain erakusteko\n  peers         - Konektatutako kideak erakusteko\n  files         - Fitxategi informazioa erakusteko\n  pause         - Deskarga pausatu\n  resume        - Deskarga berrekin\n  stop          - Deskarga gelditu\n  quit          - Aplikazioa irten\n  clear         - Pantaila garbitu\n        ",
    "\n[bold cyan]File Selection[/bold cyan]": "\n[bold cyan]Fitxategi hautaketa[/bold cyan]",
    "\n[bold]File selection[/bold]": "\n[bold]Fitxategi hautaketa[/bold]",
    "\n[yellow]Commands:[/yellow]": "\n[yellow]Komandoak:[/yellow]",
    "\n[yellow]File selection cancelled, using defaults[/yellow]": "\n[yellow]Fitxategi hautaketa bertan behera utzita, lehenetsiak erabiliz[/yellow]",
    "\n[yellow]Tracker Scrape Statistics:[/yellow]": "\n[yellow]Tracker Scrape estatistikak:[/yellow]",
    "\n[yellow]Use: files select <index>, files deselect <index>, files priority <index> <priority>[/yellow]": "\n[yellow]Erabilera: files select <index>, files deselect <index>, files priority <index> <priority>[/yellow]",
    "\n[yellow]Warning: No peers connected after 30 seconds[/yellow]": "\n[yellow]Abisua: 30 segundu ondoren kide konektaturik ez[/yellow]",
    "  [cyan]deselect <index>[/cyan] - Deselect a file": "  [cyan]deselect <index>[/cyan] - Fitxategi bat deshautatu",
    "  [cyan]deselect-all[/cyan] - Deselect all files": "  [cyan]deselect-all[/cyan] - Fitxategi guztiak deshautatu",
    "  [cyan]done[/cyan] - Finish selection and start download": "  [cyan]done[/cyan] - Hautaketa amaitu eta deskarga hasi",
    "  [cyan]priority <index> <priority>[/cyan] - Set priority (do_not_download/low/normal/high/maximum)": "  [cyan]priority <index> <priority>[/cyan] - Lehentasuna ezarri (do_not_download/low/normal/high/maximum)",
    "  [cyan]select <index>[/cyan] - Select a file": "  [cyan]select <index>[/cyan] - Fitxategi bat hautatu",
    "  [cyan]select-all[/cyan] - Select all files": "  [cyan]select-all[/cyan] - Fitxategi guztiak hautatu",
    "  • Check if torrent has active seeders": "  • Egiaztatu torrent-ak seeders aktiboak dituen",
    "  • Ensure DHT is enabled: --enable-dht": "  • Ziurtatu DHT gaituta dagoela: --enable-dht",
    "  • Run 'btbt diagnose-connections' to check connection status": "  • Exekutatu 'btbt diagnose-connections' konexio egoera egiaztatzeko",
    "  • Verify NAT/firewall settings": "  • Egiaztatu NAT/suhesi ezarpenak",
    " | Files: {selected}/{total} selected": " | Fitxategiak: {selected}/{total} hautatuta",
    " | Private: {count}": " | Pribatua: {count}",
    "Active": "Aktiboa",
    "Active Alerts": "Alerta aktiboak",
    "Active: {count}": "Aktiboa: {count}",
    "Advanced Add": "Gehitu aurreratua",
    "Alert Rules": "Alerta arauak",
    "Alerts": "Alertak",
    "Announce: Failed": "Iragarpena: Huts egin du",
    "Announce: {status}": "Iragarpena: {status}",
    "Are you sure you want to quit?": "Ziur zaude irten nahi duzula?",
    "Automatically restart daemon if needed (without prompt)": "Deabrua automatikoki berrabiarazi beharrezkoa bada (galdera gabe)",
    "Browse": "Arakatu",
    "Capability": "Gaitasuna",
    "Commands: ": "Komandoak: ",
    "Completed": "Osatuta",
    "Completed (Scrape)": "Osatuta (Scrape)",
    "Component": "Osagaia",
    "Condition": "Baldintza",
    "Config Backups": "Konfigurazio babeskopiak",
    "Configuration file path": "Konfigurazio fitxategi bidea",
    "Confirm": "Berretsi",
    "Connected": "Konektatuta",
    "Connected Peers": "Konektatutako kideak",
    "Count: {count}{file_info}{private_info}": "Zenbaketa: {count}{file_info}{private_info}",
    "Create backup before migration": "Babeskopia sortu migrazioa baino lehen",
    "DHT": "DHT",
    "Description": "Deskribapena",
    "Details": "Xehetasunak",
    "Disabled": "Desgaituta",
    "Download": "Deskargatu",
    "Download Speed": "Deskarga abiadura",
    "Download paused": "Deskarga pausatuta",
    "Download resumed": "Deskarga berrekin",
    "Download stopped": "Deskarga geldituta",
    "Downloaded": "Deskargatuta",
    "Downloading {name}": "{name} deskargatzen",
    "ETA": "Denbora estimatua",
    "Enable debug mode": "Arazketa modua gaitatu",
    "Enable verbose output": "Irteera zehatza gaitatu",
    "Enabled": "Gaituta",
    "Error reading scrape cache": "Errorea scrape cache irakurtzean",
    "Explore": "Esploratu",
    "Failed": "Huts egin du",
    "Failed to register torrent in session": "Errorea torrent saioan erregistratzean",
    "File": "Fitxategia",
    "File Name": "Fitxategi izena",
    "File selection not available for this torrent": "Fitxategi hautaketa ez dago eskuragarri torrent honentzat",
    "Files": "Fitxategiak",
    "Global Config": "Konfigurazio globala",
    "Help": "Laguntza",
    "History": "Historia",
    "ID": "ID",
    "IP": "IP",
    "IP Filter": "IP iragazkia",
    "IPFS": "IPFS",
    "Info Hash": "Info Hash",
    "Interactive backup": "Babeskopia interaktiboa",
    "Invalid torrent file format": "Torrent fitxategi formatu baliogabea",
    "Key": "Gakoa",
    "Key not found: {key}": "Gakoa ez da aurkitu: {key}",
    "Last Scrape": "Azken Scrape",
    "Leechers": "Leechers",
    "Leechers (Scrape)": "Leechers (Scrape)",
    "MIGRATED": "MIGRATUTA",
    "Menu": "Menua",
    "Metric": "Metrika",
    "NAT Management": "NAT kudeaketa",
    "Name": "Izena",
    "Network": "Sarea",
    "No": "Ez",
    "No active alerts": "Alerta aktiborik ez",
    "No alert rules": "Alerta araurik ez",
    "No alert rules configured": "Alerta araurik ez dago konfiguratuta",
    "No backups found": "Babeskopiarik ez aurkitu",
    "No cached results": "Emaitzarik ez cachean",
    "No checkpoints": "Checkpoint-ik ez",
    "No config file to backup": "Konfigurazio fitxategirik ez babesteko",
    "No peers connected": "Kide konektaturik ez",
    "No profiles available": "Profilik ez eskuragarri",
    "No templates available": "Txantiloirik ez eskuragarri",
    "No torrent active": "Torrent aktiborik ez",
    "Nodes: {count}": "Nodoak: {count}",
    "Not available": "Ez dago eskuragarri",
    "Not configured": "Ez dago konfiguratuta",
    "Not supported": "Ez dago onartuta",
    "OK": "OK",
    "Operation not supported": "Eragiketa ez dago onartuta",
    "PEX: {status}": "PEX: {status}",
    "Pause": "Pausatu",
    "Peers": "Kideak",
    "Performance": "Errendimendua",
    "Pieces": "Piezak",
    "Port": "Portua",
    "Port: {port}": "Portua: {port}",
    "Priority": "Lehentasuna",
    "Private": "Pribatua",
    "Profiles": "Profilak",
    "Progress": "Aurrerapena",
    "Property": "Propietatea",
    "Proxy Config": "Proxy konfigurazioa",
    "PyYAML is required for YAML output": "PyYAML beharrezkoa da YAML irteerarako",
    "Quick Add": "Gehitu azkarra",
    "Quit": "Irten",
    "Rate limits disabled": "Abiadura muga desgaituta",
    "Rate limits set to 1024 KiB/s": "Abiadura muga 1024 KiB/s-ra ezarrita",
    "Rehash: {status}": "Rehash: {status}",
    "Resume": "Berrekin",
    "Rule": "Araua",
    "Rule not found: {name}": "Araua ez da aurkitu: {name}",
    "Rules: {rules}, IPv4: {ipv4}, IPv6: {ipv6}, Blocks: {blocks}": "Arauak: {rules}, IPv4: {ipv4}, IPv6: {ipv6}, Blokeoak: {blocks}",
    "Running": "Exekutatzen",
    "SSL Config": "SSL konfigurazioa",
    "Scrape Results": "Scrape emaitzak",
    "Scrape: {status}": "Scrape: {status}",
    "Section not found: {section}": "Atala ez da aurkitu: {section}",
    "Security Scan": "Segurtasun eskaneatzea",
    "Seeders": "Seeders",
    "Seeders (Scrape)": "Seeders (Scrape)",
    "Select files to download": "Hautatu deskargatzeko fitxategiak",
    "Selected": "Hautatuta",
    "Session": "Saioa",
    "Set value in global config file": "Balioa ezarri konfigurazio fitxategi globalean",
    "Set value in project local ccbt.toml": "Balioa ezarri proiektu lokaleko ccbt.toml-en",
    "Severity": "Larritasuna",
    "Show specific key path (e.g. network.listen_port)": "Erakutsi gako bide zehatza (adib. network.listen_port)",
    "Show specific section key path (e.g. network)": "Erakutsi atal gako bide zehatza (adib. network)",
    "Size": "Tamaina",
    "Skip confirmation prompt": "Berrespena saltatu",
    "Skip daemon restart even if needed": "Deabrua berrabiaraztea saltatu beharrezkoa bada ere",
    "Snapshot failed: {error}": "Argazkia huts egin du: {error}",
    "Snapshot saved to {path}": "Argazkia {path}-ra gordeta",
    "Status": "Egoera",
    "Status: ": "Egoera: ",
    "Supported": "Onartuta",
    "System Capabilities": "Sistema gaitasunak",
    "System Capabilities Summary": "Sistema gaitasun laburpena",
    "System Resources": "Sistema baliabideak",
    "Templates": "Txantiloiak",
    "Timestamp": "Denbora zigilua",
    "Torrent Config": "Torrent konfigurazioa",
    "Torrent Status": "Torrent egoera",
    "Torrent file not found": "Torrent fitxategia ez da aurkitu",
    "Torrent not found": "Torrent-a ez da aurkitu",
    "Torrents": "Torrent-ak",
    "Torrents: {count}": "Torrent-ak: {count}",
    "Tracker Scrape": "Tracker Scrape",
    "Type": "Mota",
    "Unknown": "Ezezaguna",
    "Unknown subcommand": "Azpikomando ezezaguna",
    "Unknown subcommand: {sub}": "Azpikomando ezezaguna: {sub}",
    "Upload": "Igo",
    "Upload Speed": "Igo abiadura",
    "Uptime: {uptime:.1f}s": "Iraupena: {uptime:.1f}s",
    "Usage: alerts list|list-active|add|remove|clear|load|save|test ...": "Erabilera: alerts list|list-active|add|remove|clear|load|save|test ...",
    "Usage: backup <info_hash> <dest>": "Erabilera: backup <info_hash> <dest>",
    "Usage: checkpoint list": "Erabilera: checkpoint list",
    "Usage: config [show|get|set|reload] ...": "Erabilera: config [show|get|set|reload] ...",
    "Usage: config get <key.path>": "Erabilera: config get <key.path>",
    "Usage: config set <key.path> <value>": "Erabilera: config set <key.path> <value>",
    "Usage: config_backup list|create [desc]|restore <file>": "Erabilera: config_backup list|create [desc]|restore <file>",
    "Usage: config_diff <file1> <file2>": "Erabilera: config_diff <file1> <file2>",
    "Usage: config_export <toml|json|yaml> <output>": "Erabilera: config_export <toml|json|yaml> <output>",
    "Usage: config_import <toml|json|yaml> <input>": "Erabilera: config_import <toml|json|yaml> <input>",
    "Usage: export <path>": "Erabilera: export <path>",
    "Usage: import <path>": "Erabilera: import <path>",
    "Usage: limits [show|set] <info_hash> [down up]": "Erabilera: limits [show|set] <info_hash> [down up]",
    "Usage: limits set <info_hash> <down_kib> <up_kib>": "Erabilera: limits set <info_hash> <down_kib> <up_kib>",
    "Usage: metrics show [system|performance|all] | metrics export [json|prometheus] [output]": "Erabilera: metrics show [system|performance|all] | metrics export [json|prometheus] [output]",
    "Usage: profile list | profile apply <name>": "Erabilera: profile list | profile apply <name>",
    "Usage: restore <backup_file>": "Erabilera: restore <backup_file>",
    "Usage: template list | template apply <name> [merge]": "Erabilera: template list | template apply <name> [merge]",
    "Use --confirm to proceed with reset": "Erabili --confirm berrezartzeko",
    "VALID": "BALIOZKOA",
    "Value": "Balioa",
    "Welcome": "Ongi etorri",
    "Xet": "Xet",
    "Yes": "Bai",
    "Yes (BEP 27)": "Bai (BEP 27)",
    "[cyan]Adding magnet link and fetching metadata...[/cyan]": "[cyan]Magnet esteka gehitzen eta metadatuak eskuratzen...[/cyan]",
    "[cyan]Downloading: {progress:.1f}% ({peers} peers)[/cyan]": "[cyan]Deskargatzen: {progress:.1f}% ({peers} kide)[/cyan]",
    "[cyan]Downloading: {progress:.1f}% ({rate:.2f} MB/s, {peers} peers)[/cyan]": "[cyan]Deskargatzen: {progress:.1f}% ({rate:.2f} MB/s, {peers} kide)[/cyan]",
    "[cyan]Initializing session components...[/cyan]": "[cyan]Saio osagaiak hasieratzen...[/cyan]",
    "[cyan]Troubleshooting:[/cyan]": "[cyan]Arazoak konpontzen:[/cyan]",
    "[cyan]Waiting for session components to be ready (max 60s)...[/cyan]": "[cyan]Saio osagaien prest egotea itxaroten (gehienez 60s)...[/cyan]",
    "[dim]Consider using daemon commands or stop the daemon first: 'btbt daemon exit'[/dim]": "[dim]Kontuan hartu deabru komandoak erabiltzea edo deabrua lehenik gelditzea: 'btbt daemon exit'[/dim]",
    "[green]All files selected[/green]": "[green]Fitxategi guztiak hautatuta[/green]",
    "[green]Applied auto-tuned configuration[/green]": "[green]Auto-doinatutako konfigurazioa aplikatuta[/green]",
    "[green]Applied profile {name}[/green]": "[green]{name} profila aplikatuta[/green]",
    "[green]Applied template {name}[/green]": "[green]{name} txantiloia aplikatuta[/green]",
    "[green]Backup created: {path}[/green]": "[green]Babeskopia sortuta: {path}[/green]",
    "[green]Cleaned up {count} old checkpoints[/green]": "[green]{count} checkpoint zahar garbituak[/green]",
    "[green]Cleared active alerts[/green]": "[green]Alerta aktiboak garbituak[/green]",
    "[green]Configuration reloaded[/green]": "[green]Konfigurazioa birkargatuta[/green]",
    "[green]Configuration restored[/green]": "[green]Konfigurazioa berreskuratuta[/green]",
    "[green]Connected to {count} peer(s)[/green]": "[green]{count} kide(ra) konektatuta[/green]",
    "[green]Daemon status: {status}[/green]": "[green]Deabru egoera: {status}[/green]",
    "[green]Download completed, stopping session...[/green]": "[green]Deskarga osatuta, saioa gelditzen...[/green]",
    "[green]Download completed: {name}[/green]": "[green]Deskarga osatuta: {name}[/green]",
    "[green]Exported checkpoint to {path}[/green]": "[green]Checkpoint {path}-ra esportatuta[/green]",
    "[green]Exported configuration to {out}[/green]": "[green]Konfigurazioa {out}-ra esportatuta[/green]",
    "[green]Imported configuration[/green]": "[green]Konfigurazioa inportatuta[/green]",
    "[green]Loaded {count} rules[/green]": "[green]{count} arau kargatuta[/green]",
    "[green]Magnet added successfully: {hash}...[/green]": "[green]Magnet esteka arrakastaz gehituta: {hash}...[/green]",
    "[green]Magnet added to daemon: {hash}[/green]": "[green]Magnet esteka deabrura gehituta: {hash}[/green]",
    "[green]Metadata fetched successfully![/green]": "[green]Metadatuak arrakastaz eskuratuta![/green]",
    "[green]Migrated checkpoint to {path}[/green]": "[green]Checkpoint {path}-ra migratuta[/green]",
    "[green]Monitoring started[/green]": "[green]Monitorizazioa hasita[/green]",
    "[green]Resuming download from checkpoint...[/green]": "[green]Deskarga checkpoint-etik berrekin...[/green]",
    "[green]Rule added[/green]": "[green]Araua gehituta[/green]",
    "[green]Rule evaluated[/green]": "[green]Araua ebaluatuta[/green]",
    "[green]Rule removed[/green]": "[green]Araua kenduta[/green]",
    "[green]Saved rules[/green]": "[green]Arauak gordeta[/green]",
    "[green]Selected file {idx}[/green]": "[green]{idx} fitxategia hautatuta[/green]",
    "[green]Selected {count} file(s) for download[/green]": "[green]{count} fitxategi(a) hautatuta deskargatzeko[/green]",
    "[green]Set priority for file {idx} to {priority}[/green]": "[green]{idx} fitxategiaren lehentasuna {priority}-ra ezarrita[/green]",
    "[green]Starting web interface on http://{host}:{port}[/green]": "[green]Web interfazea http://{host}:{port}-n abiarazten[/green]",
    "[green]Torrent added to daemon: {hash}[/green]": "[green]Torrent-a deabrura gehituta: {hash}[/green]",
    "[green]Updated runtime configuration[/green]": "[green]Exekuzio denbora konfigurazioa eguneratuta[/green]",
    "[green]Wrote metrics to {out}[/green]": "[green]Metrikak {out}-ra idatzita[/green]",
    "[red]Backup failed: {msgs}[/red]": "[red]Babeskopia huts egin du: {msgs}[/red]",
    "[red]Error: Could not parse magnet link[/red]": "[red]Errorea: Ezin izan da magnet esteka analizatu[/red]",
    "[red]Error: {error}[/red]": "[red]Errorea: {error}[/red]",
    "[red]Failed to add magnet link: {error}[/red]": "[red]Errorea magnet esteka gehitzean: {error}[/red]",
    "[red]Failed to set config: {error}[/red]": "[red]Errorea konfigurazioa ezartzean: {error}[/red]",
    "[red]File not found: {error}[/red]": "[red]Fitxategia ez da aurkitu: {error}[/red]",
    "[red]Invalid arguments[/red]": "[red]Argumentu baliogabeak[/red]",
    "[red]Invalid file index: {idx}[/red]": "[red]Fitxategi indize baliogabea: {idx}[/red]",
    "[red]Invalid file index[/red]": "[red]Fitxategi indize baliogabea[/red]",
    "[red]Invalid info hash format: {hash}[/red]": "[red]Info hash formatu baliogabea: {hash}[/red]",
    "[red]Invalid priority. Use: do_not_download/low/normal/high/maximum[/red]": "[red]Lehentasun baliogabea. Erabili: do_not_download/low/normal/high/maximum[/red]",
    "[red]Invalid priority: {priority}. Use: do_not_download/low/normal/high/maximum[/red]": "[red]Lehentasun baliogabea: {priority}. Erabili: do_not_download/low/normal/high/maximum[/red]",
    "[red]Invalid torrent file: {error}[/red]": "[red]Torrent fitxategi baliogabea: {error}[/red]",
    "[red]Key not found: {key}[/red]": "[red]Gakoa ez da aurkitu: {key}[/red]",
    "[red]No checkpoint found for {hash}[/red]": "[red]Checkpoint-ik ez aurkitu {hash}-entzat[/red]",
    "[red]PyYAML not installed[/red]": "[red]PyYAML ez dago instalatuta[/red]",
    "[red]Reload failed: {error}[/red]": "[red]Birkargak huts egin du: {error}[/red]",
    "[red]Restore failed: {msgs}[/red]": "[red]Berreskuratzeak huts egin du: {msgs}[/red]",
    "[red]{error}[/red]": "[red]{error}[/red]",
    "[yellow]All files deselected[/yellow]": "[yellow]Fitxategi guztiak deshautatuta[/yellow]",
    "[yellow]Debug mode not yet implemented[/yellow]": "[yellow]Arazketa modua oraindik ez da inplementatuta[/yellow]",
    "[yellow]Deselected file {idx}[/yellow]": "[yellow]{idx} fitxategia deshautatuta[/yellow]",
    "[yellow]Download interrupted by user[/yellow]": "[yellow]Deskarga erabiltzaileak eten du[/yellow]",
    "[yellow]Fetching metadata from peers...[/yellow]": "[yellow]Metadatuak kideetatik eskuratzen...[/yellow]",
    "[yellow]Invalid priority spec '{spec}': {error}[/yellow]": "[yellow]Lehentasun zehaztapen baliogabea '{spec}': {error}[/yellow]",
    "[yellow]Keeping session alive[/yellow]": "[yellow]Saioa bizirik mantentzen[/yellow]",
    "[yellow]No checkpoints found[/yellow]": "[yellow]Checkpoint-ik ez aurkitu[/yellow]",
    "[yellow]Torrent session ended[/yellow]": "[yellow]Torrent saioa amaitu da[/yellow]",
    "[yellow]Unknown command: {cmd}[/yellow]": "[yellow]Komando ezezaguna: {cmd}[/yellow]",
    "[yellow]Warning: Daemon is running. Starting local session may cause port conflicts.[/yellow]": "[yellow]Abisua: Deabrua exekutatzen ari da. Saio lokala abiarazteak portu gatazkak eragin ditzake.[/yellow]",
    "[yellow]Warning: Error stopping session: {error}[/yellow]": "[yellow]Abisua: Errorea saioa gelditzean: {error}[/yellow]",
    "[yellow]{warning}[/yellow]": "[yellow]{warning}[/yellow]",
    "ccBitTorrent Interactive CLI": "ccBitTorrent CLI interaktiboa",
    "ccBitTorrent Status": "ccBitTorrent Egoera",
    "help, status, peers, files, pause, resume, stop, config, limits, strategy, discovery, checkpoint, metrics, alerts, export, import, backup, restore, capabilities, auto_tune, template, profile, config_backup, config_diff, config_export, config_import, config_schema": "help, status, peers, files, pause, resume, stop, config, limits, strategy, discovery, checkpoint, metrics, alerts, export, import, backup, restore, capabilities, auto_tune, template, profile, config_backup, config_diff, config_export, config_import, config_schema",
    "uTP Config": "uTP konfigurazioa",
    "{count} features": "{count} ezaugarri",
    "{count} items": "{count} elementu",
    "{elapsed:.0f}s ago": "duela {elapsed:.0f}s",
}


def generate_po_file(
    lang: str, translations: dict[str, str], template_path: Path, output_path: Path
) -> None:
    """Generate a complete .po file with translations."""
    with open(template_path, encoding="utf-8") as f:
        template_content = f.read()

    lines = template_content.split("\n")

    # Create header
    now = datetime.now().strftime("%Y-%m-%d %H:%M%z")
    lang_names = {
        "es": "Spanish",
        "eu": "Basque / Euskara",
    }

    header = f"""msgid ""
msgstr ""
"Project-Id-Version: ccBitTorrent 0.1.0\\n"
"Report-Msgid-Bugs-To: \\n"
"POT-Creation-Date: 2024-01-01 00:00+0000\\n"
"PO-Revision-Date: {now}\\n"
"Last-Translator: ccBitTorrent Team\\n"
"Language-Team: {lang_names[lang]}\\n"
"Language: {lang}\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"

"""

    # Process template and add translations
    output_lines = [header]
    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip header lines (already added)
        if line.startswith('msgid ""') and i < 10:
            i += 1
            continue
        if line.startswith('msgstr ""') and '"Content-Type:' in line:
            i += 1
            continue
        if line == "" and i < 10:
            i += 1
            continue

        # Find msgid
        if line.startswith('msgid "'):
            msgid = line[7:-1]  # Remove 'msgid "' and trailing '"'
            # Handle multiline msgid
            if msgid.endswith("\\n"):
                full_msgid = msgid
                i += 1
                while i < len(lines) and lines[i].startswith('"'):
                    full_msgid += (
                        lines[i][1:-1] if lines[i].endswith('"') else lines[i][1:]
                    )
                    i += 1
                msgid = full_msgid
            else:
                i += 1

            # Get msgstr (next line)
            if i < len(lines) and lines[i].startswith('msgstr "'):
                msgstr_line = lines[i]
                _ = msgstr_line[8:-1]  # Remove 'msgstr "' and trailing '"' (not used in this implementation)
                i += 1

                # Check if we have a translation
                if msgid in translations:
                    translation = translations[msgid]
                    # Escape the translation
                    escaped = (
                        translation.replace("\\", "\\\\")
                        .replace('"', '\\"')
                        .replace("\n", "\\n")
                    )
                    output_lines.append(f'msgid "{msgid}"')
                    output_lines.append(f'msgstr "{escaped}"')
                    output_lines.append("")
                else:
                    # No translation, use original
                    output_lines.append(f'msgid "{msgid}"')
                    output_lines.append(f'msgstr "{msgid}"')
                    output_lines.append("")
            else:
                # Empty msgstr
                if msgid in translations:
                    translation = translations[msgid]
                    escaped = (
                        translation.replace("\\", "\\\\")
                        .replace('"', '\\"')
                        .replace("\n", "\\n")
                    )
                    output_lines.append(f'msgid "{msgid}"')
                    output_lines.append(f'msgstr "{escaped}"')
                    output_lines.append("")
                else:
                    output_lines.append(f'msgid "{msgid}"')
                    output_lines.append('msgstr ""')
                    output_lines.append("")
                i += 1
        else:
            i += 1

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))


if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent / "locales"
    template_path = base_dir / "en" / "LC_MESSAGES" / "ccbt.pot"

    # Generate Spanish
    es_dir = base_dir / "es" / "LC_MESSAGES"
    es_dir.mkdir(parents=True, exist_ok=True)
    generate_po_file("es", SPANISH_TRANSLATIONS, template_path, es_dir / "ccbt.po")
    print(f"Generated Spanish translation: {es_dir / 'ccbt.po'}")

    # Generate Basque
    eu_dir = base_dir / "eu" / "LC_MESSAGES"
    eu_dir.mkdir(parents=True, exist_ok=True)
    generate_po_file("eu", BASQUE_TRANSLATIONS, template_path, eu_dir / "ccbt.po")
    print(f"Generated Basque translation: {eu_dir / 'ccbt.po'}")
