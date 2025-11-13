"""Generate complete translation files for Swahili, Yoruba, and Hausa.

This script reads the English .po file and generates complete translations
for all three African languages.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Callable


# Translation functions for each language
def translate_swahili(msgid: str) -> str:
    """Translate English string to Swahili."""
    # Core translations - preserving Rich markup and format strings
    translations = {
        "Active": "Inafanya kazi",
        "Active Alerts": "Onyo Zinazofanya Kazi",
        "Active: {count}": "Inafanya kazi: {count}",
        "Advanced Add": "Ongeza Kwa Kina",
        "Alert Rules": "Kanuni za Onyo",
        "Alerts": "Onyo",
        "Announce: Failed": "Tangaza: Imeshindwa",
        "Announce: {status}": "Tangaza: {status}",
        "Are you sure you want to quit?": "Je, una uhakika unataka kuondoka?",
        "Automatically restart daemon if needed (without prompt)": "Anza upya daemon kiotomatiki ikiwa inahitajika (bila kuuliza)",
        "Browse": "Vinjari",
        "Capability": "Uwezo",
        "Commands: ": "Amri: ",
        "Completed": "Imekamilika",
        "Completed (Scrape)": "Imekamilika (Scrape)",
        "Component": "Sehemu",
        "Condition": "Hali",
        "Config Backups": "Nakala za Usalama za Usanidi",
        "Configuration file path": "Njia ya faili ya usanidi",
        "Confirm": "Thibitisha",
        "Connected": "Imeunganishwa",
        "Connected Peers": "Wanaohusiana Wameunganishwa",
        "Count: {count}{file_info}{private_info}": "Hesabu: {count}{file_info}{private_info}",
        "Create backup before migration": "Unda nakala ya usalama kabla ya uhamishaji",
        "DHT": "DHT",
        "Description": "Maelezo",
        "Details": "Maelezo ya kina",
        "Disabled": "Imezimwa",
        "Download": "Pakua",
        "Download Speed": "Kasi ya Upakuaji",
        "Download paused": "Upakuaji umezimwa",
        "Download resumed": "Upakuaji umeendelezwa",
        "Download stopped": "Upakuaji umeacha",
        "Downloaded": "Imechukuliwa",
        "Downloading {name}": "Inapakua {name}",
        "ETA": "Muda wa Kukamilika",
        "Enable debug mode": "Washa hali ya utatuzi",
        "Enable verbose output": "Washa matokeo ya kina",
        "Enabled": "Imeamilishwa",
        "Error reading scrape cache": "Hitilafu katika kusoma cache ya scrape",
        "Explore": "Chunguza",
        "Failed": "Imeshindwa",
        "Failed to register torrent in session": "Kushindwa kusajili torrent katika kikao",
        "File": "Faili",
        "File Name": "Jina la Faili",
        "File selection not available for this torrent": "Uchaguzi wa faili haupatikani kwa torrent hii",
        "Files": "Faili",
        "Global Config": "Usanidi wa Ulimwengu",
        "Help": "Msaada",
        "History": "Historia",
        "ID": "Kitambulisho",
        "IP": "IP",
        "IP Filter": "Kichujio cha IP",
        "IPFS": "IPFS",
        "Info Hash": "Hash ya Taarifa",
        "Interactive backup": "Nakala ya usalama ya kuingiliana",
        "Invalid torrent file format": "Muundo wa faili ya torrent si sahihi",
        "Key": "Ufunguo",
        "Key not found: {key}": "Ufunguo haujapatikana: {key}",
        "Last Scrape": "Scrape ya Mwisho",
        "Leechers": "Wanachukua",
        "Leechers (Scrape)": "Wanachukua (Scrape)",
        "MIGRATED": "IMEHAMISHWA",
        "Menu": "Menyu",
        "Metric": "Kipimo",
        "NAT Management": "Usimamizi wa NAT",
        "Name": "Jina",
        "Network": "Mtandao",
        "No": "Hapana",
        "No active alerts": "Hakuna onyo zinazofanya kazi",
        "No alert rules": "Hakuna kanuni za onyo",
        "No alert rules configured": "Hakuna kanuni za onyo zimepangwa",
        "No backups found": "Hakuna nakala za usalama zilizopatikana",
        "No cached results": "Hakuna matokeo yaliyohifadhiwa",
        "No checkpoints": "Hakuna sehemu za kuangalia",
        "No config file to backup": "Hakuna faili ya usanidi ya kutengeneza nakala ya usalama",
        "No peers connected": "Hakuna wanaohusiana wameunganishwa",
        "No profiles available": "Hakuna wasifu zinazopatikana",
        "No templates available": "Hakuna viwango zinazopatikana",
        "No torrent active": "Hakuna torrent inayofanya kazi",
        "Nodes: {count}": "Nodi: {count}",
        "Not available": "Haipatikani",
        "Not configured": "Haijapangwa",
        "Not supported": "Haitegemezi",
        "OK": "Sawa",
        "Operation not supported": "Operesheni haitegemezi",
        "PEX: {status}": "PEX: {status}",  # PEX is technical acronym
        "Pause": "Simamisha",
        "Peers": "Wanaohusiana",
        "Performance": "Utendaji",
        "Pieces": "Vipande",
        "Port": "Bandari",
        "Port: {port}": "Bandari: {port}",
        "Priority": "Kipaumbele",
        "Private": "Binafsi",
        "Profiles": "Wasifu",
        "Progress": "Maendeleo",
        "Property": "Mali",
        "Proxy Config": "Usanidi wa Proxy",
        "PyYAML is required for YAML output": "PyYAML inahitajika kwa matokeo ya YAML",
        "Quick Add": "Ongeza Haraka",
        "Quit": "Toka",
        "Rate limits disabled": "Mipaka ya kasi imezimwa",
        "Rate limits set to 1024 KiB/s": "Mipaka ya kasi imewekwa kwa 1024 KiB/s",
        "Rehash: {status}": "Rehash: {status}",  # Technical term
        "Resume": "Endelea",
        "Rule": "Kanuni",
        "Rule not found: {name}": "Kanuni haijapatikana: {name}",
        "Rules: {rules}, IPv4: {ipv4}, IPv6: {ipv6}, Blocks: {blocks}": "Kanuni: {rules}, IPv4: {ipv4}, IPv6: {ipv6}, Vizuizi: {blocks}",
        "Running": "Inaendesha",
        "SSL Config": "Usanidi wa SSL",
        "Scrape Results": "Matokeo ya Scrape",
        "Scrape: {status}": "Scrape: {status}",  # Technical term
        "Section not found: {section}": "Sehemu haijapatikana: {section}",
        "Security Scan": "Uchunguzi wa Usalama",
        "Seeders": "Wanapanda",
        "Seeders (Scrape)": "Wanapanda (Scrape)",
        "Select files to download": "Chagua faili za kupakua",
        "Selected": "Imechaguliwa",
        "Session": "Kikao",
        "Set value in global config file": "Weka thamani katika faili ya usanidi ya ulimwengu",
        "Set value in project local ccbt.toml": "Weka thamani katika ccbt.toml ya mradi ya ndani",
        "Severity": "Ukali",
        "Show specific key path (e.g. network.listen_port)": "Onyesha njia maalum ya ufunguo (mfano. network.listen_port)",
        "Show specific section key path (e.g. network)": "Onyesha njia ya ufunguo wa sehemu maalum (mfano. network)",
        "Size": "Ukubwa",
        "Skip confirmation prompt": "Ruka ujumbe wa uthibitishaji",
        "Skip daemon restart even if needed": "Ruka kuanza upya daemon hata ikiwa inahitajika",
        "Snapshot failed: {error}": "Picha ya wakati imeshindwa: {error}",
        "Snapshot saved to {path}": "Picha ya wakati imehifadhiwa kwa {path}",
        "Status": "Hali",
        "Status: ": "Hali: ",
        "Supported": "Inategemezi",
        "System Capabilities": "Uwezo wa Mfumo",
        "System Capabilities Summary": "Muhtasari wa Uwezo wa Mfumo",
        "System Resources": "Rasilimali za Mfumo",
        "Templates": "Viwango",
        "Timestamp": "Alama ya Wakati",
        "Torrent Config": "Usanidi wa Torrent",
        "Torrent Status": "Hali ya Torrent",
        "Torrent file not found": "Faili ya torrent haijapatikana",
        "Torrent not found": "Torrent haijapatikana",
        "Torrents": "Torrents",  # Technical term - commonly used as-is
        "Torrents: {count}": "Torrents: {count}",  # Technical term
        "Tracker Scrape": "Scrape ya Tracker",
        "Type": "Aina",
        "Unknown": "Haijulikani",
        "Unknown subcommand": "Amri ndogo haijulikani",
        "Unknown subcommand: {sub}": "Amri ndogo haijulikani: {sub}",
        "Upload": "Pakia",
        "Upload Speed": "Kasi ya Kupakia",
        "Uptime: {uptime:.1f}s": "Muda wa kufanya kazi: {uptime:.1f}s",
        "Use --confirm to proceed with reset": "Tumia --confirm kuendelea na kuanzisha upya",
        "VALID": "SAHIHI",
        "Value": "Thamani",
        "Welcome": "Karibu",
        "Xet": "Xet",  # Technical term/brand name
        "Yes": "Ndiyo",
        "Yes (BEP 27)": "Ndiyo (BEP 27)",
        "uTP Config": "Usanidi wa uTP",
        "{count} features": "Vipengele {count}",
        "{count} items": "Vitu {count}",
        "{elapsed:.0f}s ago": "Sekunde {elapsed:.0f} zilizopita",
        # Rich markup strings
        "[cyan]Adding magnet link and fetching metadata...[/cyan]": "[cyan]Inaongeza kiungo cha magnet na inapata metadata...[/cyan]",
        "[cyan]Downloading: {progress:.1f}% ({peers} peers)[/cyan]": "[cyan]Inapakua: {progress:.1f}% ({peers} wanaohusiana)[/cyan]",
        "[cyan]Downloading: {progress:.1f}% ({rate:.2f} MB/s, {peers} peers)[/cyan]": "[cyan]Inapakua: {progress:.1f}% ({rate:.2f} MB/s, {peers} wanaohusiana)[/cyan]",
        "[cyan]Initializing session components...[/cyan]": "[cyan]Inaanzisha sehemu za kikao...[/cyan]",
        "[cyan]Troubleshooting:[/cyan]": "[cyan]Kutatua matatizo:[/cyan]",
        "[cyan]Waiting for session components to be ready (max 60s)...[/cyan]": "[cyan]Inasubiri sehemu za kikao ziwe tayari (kiwango cha juu sekunde 60)...[/cyan]",
        "[dim]Consider using daemon commands or stop the daemon first: 'btbt daemon exit'[/dim]": "[dim]Fikiria kutumia amri za daemon au simamisha daemon kwanza: 'btbt daemon exit'[/dim]",
        "[green]All files selected[/green]": "[green]Faili zote zimechaguliwa[/green]",
        "[green]Applied auto-tuned configuration[/green]": "[green]Usanidi wa kurekebisha kiotomatiki umetumika[/green]",
        "[green]Applied profile {name}[/green]": "[green]Wasifu {name} umetumika[/green]",
        "[green]Applied template {name}[/green]": "[green]Kiwango {name} kimetumika[/green]",
        "[green]Backup created: {path}[/green]": "[green]Nakala ya usalama imeundwa: {path}[/green]",
        "[green]Cleaned up {count} old checkpoints[/green]": "[green]Imesafisha sehemu za kuangalia {count} za zamani[/green]",
        "[green]Cleared active alerts[/green]": "[green]Onyo zinazofanya kazi zimefutwa[/green]",
        "[green]Configuration reloaded[/green]": "[green]Usanidi umeonyeshwa tena[/green]",
        "[green]Configuration restored[/green]": "[green]Usanidi umerudishwa[/green]",
        "[green]Connected to {count} peer(s)[/green]": "[green]Imeunganishwa na {count} mwenyehusika[/green]",
        "[green]Daemon status: {status}[/green]": "[green]Hali ya daemon: {status}[/green]",
        "[green]Download completed, stopping session...[/green]": "[green]Upakuaji umekamilika, kusimamisha kikao...[/green]",
        "[green]Download completed: {name}[/green]": "[green]Upakuaji umekamilika: {name}[/green]",
        "[green]Exported checkpoint to {path}[/green]": "[green]Sehemu ya kuangalia imehamishwa kwa {path}[/green]",
        "[green]Exported configuration to {out}[/green]": "[green]Usanidi umehamishwa kwa {out}[/green]",
        "[green]Imported configuration[/green]": "[green]Usanidi umeingizwa[/green]",
        "[green]Loaded {count} rules[/green]": "[green]Kanuni {count} zimepakuliwa[/green]",
        "[green]Magnet added successfully: {hash}...[/green]": "[green]Kiungo cha magnet kimeongezwa kwa mafanikio: {hash}...[/green]",
        "[green]Magnet added to daemon: {hash}[/green]": "[green]Kiungo cha magnet kimeongezwa kwa daemon: {hash}[/green]",
        "[green]Metadata fetched successfully![/green]": "[green]Metadata imepatikana kwa mafanikio![/green]",
        "[green]Migrated checkpoint to {path}[/green]": "[green]Sehemu ya kuangalia imehamishwa kwa {path}[/green]",
        "[green]Monitoring started[/green]": "[green]Ufuatiliaji umeanza[/green]",
        "[green]Resuming download from checkpoint...[/green]": "[green]Kuendeleza upakuaji kutoka sehemu ya kuangalia...[/green]",
        "[green]Rule added[/green]": "[green]Kanuni imeongezwa[/green]",
        "[green]Rule evaluated[/green]": "[green]Kanuni imetathminiwa[/green]",
        "[green]Rule removed[/green]": "[green]Kanuni imeondolewa[/green]",
        "[green]Saved rules[/green]": "[green]Kanuni zimehifadhiwa[/green]",
        "[green]Selected file {idx}[/green]": "[green]Faili {idx} imechaguliwa[/green]",
        "[green]Selected {count} file(s) for download[/green]": "[green]Faili {count} zimechaguliwa kwa upakuaji[/green]",
        "[green]Set priority for file {idx} to {priority}[/green]": "[green]Kipaumbele cha faili {idx} kimewekwa kwa {priority}[/green]",
        "[green]Starting web interface on http://{host}:{port}[/green]": "[green]Inaanzisha kiolesura cha wavuti kwenye http://{host}:{port}[/green]",
        "[green]Torrent added to daemon: {hash}[/green]": "[green]Torrent imeongezwa kwa daemon: {hash}[/green]",
        "[green]Updated runtime configuration[/green]": "[green]Usanidi wa wakati wa utendaji umehakikishwa[/green]",
        "[green]Wrote metrics to {out}[/green]": "[green]Vipimo vimeandikwa kwa {out}[/green]",
        "[red]Backup failed: {msgs}[/red]": "[red]Nakala ya usalama imeshindwa: {msgs}[/red]",
        "[red]Error: Could not parse magnet link[/red]": "[red]Hitilafu: Haikuweza kuchanganua kiungo cha magnet[/red]",
        "[red]Error: {error}[/red]": "[red]Hitilafu: {error}[/red]",
        "[red]Failed to add magnet link: {error}[/red]": "[red]Kushindwa kuongeza kiungo cha magnet: {error}[/red]",
        "[red]Failed to set config: {error}[/red]": "[red]Kushindwa kuweka usanidi: {error}[/red]",
        "[red]File not found: {error}[/red]": "[red]Faili haijapatikana: {error}[/red]",
        "[red]Invalid arguments[/red]": "[red]Hoja si sahihi[/red]",
        "[red]Invalid file index: {idx}[/red]": "[red]Fahirisi ya faili si sahihi: {idx}[/red]",
        "[red]Invalid file index[/red]": "[red]Fahirisi ya faili si sahihi[/red]",
        "[red]Invalid info hash format: {hash}[/red]": "[red]Muundo wa hash ya taarifa si sahihi: {hash}[/red]",
        "[red]Invalid priority. Use: do_not_download/low/normal/high/maximum[/red]": "[red]Kipaumbele si sahihi. Tumia: do_not_download/low/normal/high/maximum[/red]",
        "[red]Invalid priority: {priority}. Use: do_not_download/low/normal/high/maximum[/red]": "[red]Kipaumbele si sahihi: {priority}. Tumia: do_not_download/low/normal/high/maximum[/red]",
        "[red]Invalid torrent file: {error}[/red]": "[red]Faili ya torrent si sahihi: {error}[/red]",
        "[red]Key not found: {key}[/red]": "[red]Ufunguo haujapatikana: {key}[/red]",
        "[red]No checkpoint found for {hash}[/red]": "[red]Hakuna sehemu ya kuangalia iliyopatikana kwa {hash}[/red]",
        "[red]PyYAML not installed[/red]": "[red]PyYAML haijasakinishwa[/red]",
        "[red]Reload failed: {error}[/red]": "[red]Kuonyesha tena kumeshindwa: {error}[/red]",
        "[red]Restore failed: {msgs}[/red]": "[red]Kurudisha kumeshindwa: {msgs}[/red]",
        "[red]{error}[/red]": "[red]{error}[/red]",  # Format string - error variable will be translated separately
        "[yellow]All files deselected[/yellow]": "[yellow]Faili zote zimeachwa[/yellow]",
        "[yellow]Debug mode not yet implemented[/yellow]": "[yellow]Hali ya utatuzi bado haijatekelezwa[/yellow]",
        "[yellow]Deselected file {idx}[/yellow]": "[yellow]Faili {idx} imeachwa[/yellow]",
        "[yellow]Download interrupted by user[/yellow]": "[yellow]Upakuaji umevurugwa na mtumiaji[/yellow]",
        "[yellow]Fetching metadata from peers...[/yellow]": "[yellow]Inapata metadata kutoka kwa wanaohusiana...[/yellow]",
        "[yellow]Invalid priority spec '{spec}': {error}[/yellow]": "[yellow]Kipaumbele '{spec}' si sahihi: {error}[/yellow]",
        "[yellow]Keeping session alive[/yellow]": "[yellow]Inaendeleza kikao hai[/yellow]",
        "[yellow]No checkpoints found[/yellow]": "[yellow]Hakuna sehemu za kuangalia zilizopatikana[/yellow]",
        "[yellow]Torrent session ended[/yellow]": "[yellow]Kikao cha torrent kimeisha[/yellow]",
        "[yellow]Unknown command: {cmd}[/yellow]": "[yellow]Amri haijulikani: {cmd}[/yellow]",
        "[yellow]Warning: Daemon is running. Starting local session may cause port conflicts.[/yellow]": "[yellow]Onyo: Daemon inaendesha. Kuanza kikao cha ndani kunaweza kusababisha migogoro ya bandari.[/yellow]",
        "[yellow]Warning: Error stopping session: {error}[/yellow]": "[yellow]Onyo: Hitilafu katika kusimamisha kikao: {error}[/yellow]",
        "[yellow]{warning}[/yellow]": "[yellow]{warning}[/yellow]",
        # Multi-line strings
        "\nAvailable Commands:\n  help          - Show this help message\n  status        - Show current status\n  peers         - Show connected peers\n  files         - Show file information\n  pause         - Pause download\n  resume        - Resume download\n  stop          - Stop download\n  quit          - Quit application\n  clear         - Clear screen\n        ": "\nAmri Zinazopatikana:\n  help          - Onyesha ujumbe huu wa msaada\n  status        - Onyesha hali ya sasa\n  peers         - Onyesha wanaohusiana\n  files         - Onyesha taarifa za faili\n  pause         - Simamisha upakuaji\n  resume        - Endelea upakuaji\n  stop          - Acha upakuaji\n  quit          - Toka kwenye programu\n  clear         - Safisha skrini\n        ",
        "\n[bold cyan]File Selection[/bold cyan]": "\n[bold cyan]Uchaguzi wa Faili[/bold cyan]",
        "\n[bold]File selection[/bold]": "\n[bold]Uchaguzi wa faili[/bold]",
        "\n[yellow]Commands:[/yellow]": "\n[yellow]Amri:[/yellow]",
        "\n[yellow]File selection cancelled, using defaults[/yellow]": "\n[yellow]Uchaguzi wa faili umeghairiwa, kutumia chaguo-msingi[/yellow]",
        "\n[yellow]Tracker Scrape Statistics:[/yellow]": "\n[yellow]Takwimu za Tracker Scrape:[/yellow]",
        "\n[yellow]Use: files select <index>, files deselect <index>, files priority <index> <priority>[/yellow]": "\n[yellow]Tumia: files select <index>, files deselect <index>, files priority <index> <priority>[/yellow]",
        "\n[yellow]Warning: No peers connected after 30 seconds[/yellow]": "\n[yellow]Onyo: Hakuna wanaohusiana wameunganishwa baada ya sekunde 30[/yellow]",
        "  [cyan]deselect <index>[/cyan] - Deselect a file": "  [cyan]deselect <index>[/cyan] - Acha kuchagua faili",
        "  [cyan]deselect-all[/cyan] - Deselect all files": "  [cyan]deselect-all[/cyan] - Acha kuchagua faili zote",
        "  [cyan]done[/cyan] - Finish selection and start download": "  [cyan]done[/cyan] - Maliza uchaguzi na anza upakuaji",
        "  [cyan]priority <index> <priority>[/cyan] - Set priority (do_not_download/low/normal/high/maximum)": "  [cyan]priority <index> <priority>[/cyan] - Weka kipaumbele (do_not_download/low/normal/high/maximum)",
        "  [cyan]select <index>[/cyan] - Select a file": "  [cyan]select <index>[/cyan] - Chagua faili",
        "  [cyan]select-all[/cyan] - Select all files": "  [cyan]select-all[/cyan] - Chagua faili zote",
        "  • Check if torrent has active seeders": "  • Angalia ikiwa torrent ina seeders zinazofanya kazi",
        "  • Ensure DHT is enabled: --enable-dht": "  • Hakikisha DHT imewezeshwa: --enable-dht",
        "  • Run 'btbt diagnose-connections' to check connection status": "  • Endesha 'btbt diagnose-connections' kuangalia hali ya muunganisho",
        "  • Verify NAT/firewall settings": "  • Thibitisha mipangilio ya NAT/firewall",
        " | Files: {selected}/{total} selected": " | Faili: {selected}/{total} zimechaguliwa",
        " | Private: {count}": " | Binafsi: {count}",
        "ccBitTorrent Interactive CLI": "ccBitTorrent CLI ya Kuingiliana",
        "ccBitTorrent Status": "Hali ya ccBitTorrent",
        "help, status, peers, files, pause, resume, stop, config, limits, strategy, discovery, checkpoint, metrics, alerts, export, import, backup, restore, capabilities, auto_tune, template, profile, config_backup, config_diff, config_export, config_import, config_schema": "help, status, peers, files, pause, resume, stop, config, limits, strategy, discovery, checkpoint, metrics, alerts, export, import, backup, restore, capabilities, auto_tune, template, profile, config_backup, config_diff, config_export, config_import, config_schema",
        "Usage: alerts list|list-active|add|remove|clear|load|save|test ...": "Matumizi: alerts list|list-active|add|remove|clear|load|save|test ...",
        "Usage: backup <info_hash> <dest>": "Matumizi: backup <info_hash> <dest>",
        "Usage: checkpoint list": "Matumizi: checkpoint list",
        "Usage: config [show|get|set|reload] ...": "Matumizi: config [show|get|set|reload] ...",
        "Usage: config get <key.path>": "Matumizi: config get <key.path>",
        "Usage: config set <key.path> <value>": "Matumizi: config set <key.path> <value>",
        "Usage: config_backup list|create [desc]|restore <file>": "Matumizi: config_backup list|create [desc]|restore <file>",
        "Usage: config_diff <file1> <file2>": "Matumizi: config_diff <file1> <file2>",
        "Usage: config_export <toml|json|yaml> <output>": "Matumizi: config_export <toml|json|yaml> <output>",
        "Usage: config_import <toml|json|yaml> <input>": "Matumizi: config_import <toml|json|yaml> <input>",
        "Usage: export <path>": "Matumizi: export <path>",
        "Usage: import <path>": "Matumizi: import <path>",
        "Usage: limits [show|set] <info_hash> [down up]": "Matumizi: limits [show|set] <info_hash> [down up]",
        "Usage: limits set <info_hash> <down_kib> <up_kib>": "Matumizi: limits set <info_hash> <down_kib> <up_kib>",
        "Usage: metrics show [system|performance|all] | metrics export [json|prometheus] [output]": "Matumizi: metrics show [system|performance|all] | metrics export [json|prometheus] [output]",
        "Usage: profile list | profile apply <name>": "Matumizi: profile list | profile apply <name>",
        "Usage: restore <backup_file>": "Matumizi: restore <backup_file>",
        "Usage: template list | template apply <name> [merge]": "Matumizi: template list | template apply <name> [merge]",
    }

    # Handle Rich markup strings - preserve markup, translate content
    if msgid.startswith("[") and "]" in msgid:
        # First check if we have a direct translation for the full string
        if msgid in translations:
            return translations[msgid]

        # Extract markup and content
        markup_match = re.match(r"^(\[[^\]]+\])(.*?)(\[/[^\]]+\])?$", msgid)
        if markup_match:
            open_tag = markup_match.group(1)
            content = markup_match.group(2)
            close_tag = markup_match.group(3) or ""

            # Translate content if available, otherwise use original
            translated_content = translations.get(content, content)
            return f"{open_tag}{translated_content}{close_tag}"

    # First check for direct translation (including multi-line strings)
    if msgid in translations:
        return translations[msgid]

    # Handle multi-line strings - try to translate line by line if no direct match
    if "\n" in msgid:
        lines = msgid.split("\n")
        translated_lines = []
        for line in lines:
            # Check if line has translation
            if line.strip() in translations:
                translated_lines.append(translations[line.strip()])
            elif any(key in line for key in translations):
                # Try to match partial
                for key, val in translations.items():
                    if key in line:
                        translated_lines.append(line.replace(key, val))
                        break
                else:
                    translated_lines.append(line)
            else:
                translated_lines.append(line)
        return "\n".join(translated_lines)

    # Direct translation
    return translations.get(msgid, msgid)


def translate_yoruba(msgid: str) -> str:
    """Translate English string to Yoruba."""
    translations = {
        "Active": "Nṣiṣẹ",
        "Active Alerts": "Àkíyèsí Tó Nṣiṣẹ",
        "Active: {count}": "Nṣiṣẹ: {count}",
        "Advanced Add": "Ìròpò Àtẹ̀lẹ̀",
        "Alert Rules": "Àwọn Ìlànà Àkíyèsí",
        "Alerts": "Àkíyèsí",
        "Announce: Failed": "Ìfihàn: Kò ṣe",
        "Announce: {status}": "Ìfihàn: {status}",
        "Are you sure you want to quit?": "Ṣé o dájú pé o fẹ́ jáde?",
        "Automatically restart daemon if needed (without prompt)": "Tún bẹ̀rẹ̀ daemon laifọwọ́yí tí ó bá wúlò (láìsí ìbéèrè)",
        "Browse": "Ṣàwárí",
        "Capability": "Agbára",
        "Commands: ": "Àwọn Àṣẹ: ",
        "Completed": "Tí Parí",
        "Completed (Scrape)": "Tí Parí (Scrape)",
        "Component": "Apá",
        "Condition": "Ìpàdé",
        "Config Backups": "Àwọn Ìgbàgbẹ́ Ètò",
        "Configuration file path": "Ọ̀nà fáìlì ètò",
        "Confirm": "Jẹ́rìí",
        "Connected": "Tí Dípọ̀",
        "Connected Peers": "Àwọn Ẹgbẹ́ Tí Dípọ̀",
        "Count: {count}{file_info}{private_info}": "Ìka: {count}{file_info}{private_info}",
        "Create backup before migration": "Ṣẹ̀dá ìgbàgbẹ́ ṣáájú ìgbérí",
        "DHT": "DHT",
        "Description": "Àpèjúwe",
        "Details": "Àwọn Àlàyé",
        "Disabled": "Tí Dínkù",
        "Download": "Ìgbàsílẹ̀",
        "Download Speed": "Ìyára Ìgbàsílẹ̀",
        "Download paused": "Ìgbàsílẹ̀ dínkù",
        "Download resumed": "Ìgbàsílẹ̀ tún bẹ̀rẹ̀",
        "Download stopped": "Ìgbàsílẹ̀ dákẹ́",
        "Downloaded": "Tí Gbà",
        "Downloading {name}": "Ń Gbà {name}",
        "ETA": "Àkókò Tí Ó Parí",
        "Enable debug mode": "Mú àwọn ìṣòro ṣiṣẹ́",
        "Enable verbose output": "Mú ìjádé tó pọ̀ ṣiṣẹ́",
        "Enabled": "Tí Mú Ṣiṣẹ́",
        "Error reading scrape cache": "Àṣìṣe nínú kíkà scrape cache",
        "Explore": "Ṣàwárí",
        "Failed": "Kò Ṣe",
        "Failed to register torrent in session": "Kò ṣeé fi torrent forúkọ sílé nínú àkókò",
        "File": "Fáìlì",
        "File Name": "Orúkọ Fáìlì",
        "File selection not available for this torrent": "Ìyàn fáìlì kò sí fún torrent yìí",
        "Files": "Àwọn Fáìlì",
        "Global Config": "Ètò Gbogbogbò",
        "Help": "Ìrànlọ́wọ́",
        "History": "Ìtàn",
        "ID": "ID",
        "IP": "IP",
        "IP Filter": "Àtẹ̀jáde IP",
        "IPFS": "IPFS",
        "Info Hash": "Hash Àlàyé",
        "Interactive backup": "Ìgbàgbẹ́ ìbaraẹnisọrọ̀",
        "Invalid torrent file format": "Àwọn ètò fáìlì torrent kò tọ́",
        "Key": "Ọ̀nà",
        "Key not found: {key}": "Ọ̀nà kò rí: {key}",
        "Last Scrape": "Scrape Tó Kẹ́hìn",
        "Leechers": "Àwọn Olùgbà",
        "Leechers (Scrape)": "Àwọn Olùgbà (Scrape)",
        "MIGRATED": "TÍ GBÉRÍ",
        "Menu": "Àtòjọ",
        "Metric": "Métíríkì",
        "NAT Management": "Ìṣàkóso NAT",
        "Name": "Orúkọ",
        "Network": "Nẹ́tíwọ̀kì",
        "No": "Bẹ́ẹ̀ kọ́",
        "No active alerts": "Kò sí àkíyèsí tó nṣiṣẹ́",
        "No alert rules": "Kò sí àwọn ìlànà àkíyèsí",
        "No alert rules configured": "Kò sí àwọn ìlànà àkíyèsí tí a ṣètò",
        "No backups found": "Kò sí àwọn ìgbàgbẹ́ tí a rí",
        "No cached results": "Kò sí àwọn èsì tí a ṣàkójọ",
        "No checkpoints": "Kò sí àwọn ibi ìgbéyẹ̀wò",
        "No config file to backup": "Kò sí fáìlì ètò láti ṣe ìgbàgbẹ́",
        "No peers connected": "Kò sí àwọn ẹgbẹ́ tí dípọ̀",
        "No profiles available": "Kò sí àwọn àkọlé tí wà",
        "No templates available": "Kò sí àwọn àpẹrẹ tí wà",
        "No torrent active": "Kò sí torrent tó nṣiṣẹ́",
        "Nodes: {count}": "Àwọn Nóòdù: {count}",
        "Not available": "Kò Wà",
        "Not configured": "Kò ṣètò",
        "Not supported": "Kò ṣeé gbà",
        "OK": "Dájú",
        "Operation not supported": "Ìṣẹ́ kò ṣeé gbà",
        "PEX: {status}": "PEX: {status}",  # PEX is technical acronym
        "Pause": "Dúró",
        "Peers": "Àwọn Ẹgbẹ́",
        "Performance": "Ìṣẹ́",
        "Pieces": "Àwọn Ẹyà",
        "Port": "Pọ́ọ̀tì",
        "Port: {port}": "Pọ́ọ̀tì: {port}",
        "Priority": "Àkànkàn",
        "Private": "Ìkọ̀kọ̀",
        "Profiles": "Àwọn Àkọlé",
        "Progress": "Ìlọsíwájú",
        "Property": "Ohun",
        "Proxy Config": "Ètò Proxy",
        "PyYAML is required for YAML output": "PyYAML wúlò fún ìjádé YAML",
        "Quick Add": "Ìròpò Kíákíá",
        "Quit": "Jáde",
        "Rate limits disabled": "Àwọn ààlà ìyára dínkù",
        "Rate limits set to 1024 KiB/s": "Àwọn ààlà ìyára ṣètò sí 1024 KiB/s",
        "Rehash: {status}": "Rehash: {status}",  # Technical term
        "Resume": "Tún Bẹ̀rẹ̀",
        "Rule": "Ìlànà",
        "Rule not found: {name}": "Ìlànà kò rí: {name}",
        "Rules: {rules}, IPv4: {ipv4}, IPv6: {ipv6}, Blocks: {blocks}": "Àwọn Ìlànà: {rules}, IPv4: {ipv4}, IPv6: {ipv6}, Àwọn Dídì: {blocks}",
        "Running": "Ń Ṣiṣẹ́",
        "SSL Config": "Ètò SSL",
        "Scrape Results": "Àwọn Èsì Scrape",
        "Scrape: {status}": "Scrape: {status}",  # Technical term
        "Section not found: {section}": "Apá kò rí: {section}",
        "Security Scan": "Ìwádìí Ààbò",
        "Seeders": "Àwọn Olùgbìn",
        "Seeders (Scrape)": "Àwọn Olùgbìn (Scrape)",
        "Select files to download": "Yàn àwọn fáìlì láti gbà",
        "Selected": "Tí A Yàn",
        "Session": "Àkókò",
        "Set value in global config file": "Ṣètò ìye nínú fáìlì ètò gbogbogbò",
        "Set value in project local ccbt.toml": "Ṣètò ìye nínú ccbt.toml agbègbè iṣẹ́",
        "Severity": "Ìwọ̀n",
        "Show specific key path (e.g. network.listen_port)": "Fihàn ọ̀nà ọ̀nà pàtàkì (àpẹrẹ. network.listen_port)",
        "Show specific section key path (e.g. network)": "Fihàn ọ̀nà ọ̀nà apá pàtàkì (àpẹrẹ. network)",
        "Size": "Ìwọ̀n",
        "Skip confirmation prompt": "Fò ìbéèrè ìjẹ́rìí",
        "Skip daemon restart even if needed": "Fò títún bẹ̀rẹ̀ daemon bí ó tilẹ̀ jẹ́ pé ó wúlò",
        "Snapshot failed: {error}": "Àwòrán kò ṣe: {error}",
        "Snapshot saved to {path}": "Àwòrán tí a fipamọ́ sí {path}",
        "Status": "Ìpàdé",
        "Status: ": "Ìpàdé: ",
        "Supported": "Tí A Gbà",
        "System Capabilities": "Àwọn Agbára Ètò",
        "System Capabilities Summary": "Àkójọ Àwọn Agbára Ètò",
        "System Resources": "Àwọn Ohun Ètò",
        "Templates": "Àwọn Àpẹrẹ",
        "Timestamp": "Àkókò Àmì",
        "Torrent Config": "Ètò Torrent",
        "Torrent Status": "Ìpàdé Torrent",
        "Torrent file not found": "Fáìlì torrent kò rí",
        "Torrent not found": "Torrent kò rí",
        "Torrents": "Àwọn Torrent",  # Technical term
        "Torrents: {count}": "Àwọn Torrent: {count}",
        "Tracker Scrape": "Scrape Tracker",
        "Type": "Ìrí",
        "Unknown": "Àìmọ̀",
        "Unknown subcommand": "Àṣẹ kékeré àìmọ̀",
        "Unknown subcommand: {sub}": "Àṣẹ kékeré àìmọ̀: {sub}",
        "Upload": "Ìgbékalẹ̀",
        "Upload Speed": "Ìyára Ìgbékalẹ̀",
        "Uptime: {uptime:.1f}s": "Àkókò Ṣiṣẹ́: {uptime:.1f}s",
        "Use --confirm to proceed with reset": "Lo --confirm láti tẹ̀síwájú pẹ̀lú títún ṣètò",
        "VALID": "TỌ́",
        "Value": "Ìye",
        "Welcome": "Káàbọ̀",
        "Xet": "Xet",  # Technical term/brand name
        "Yes": "Bẹ́ẹ̀ni",
        "Yes (BEP 27)": "Bẹ́ẹ̀ni (BEP 27)",
        "uTP Config": "Ètò uTP",
        "{count} features": "{count} àwọn ẹ̀yà",
        "{count} items": "{count} àwọn nǹkan",
        "{elapsed:.0f}s ago": "Ọjọ́ {elapsed:.0f}s sẹ́yìn",
        # Rich markup strings
        "[cyan]Adding magnet link and fetching metadata...[/cyan]": "[cyan]Ń ṣàfikún ìjápọ̀ magnet àti gbà metadata...[/cyan]",
        "[cyan]Downloading: {progress:.1f}% ({peers} peers)[/cyan]": "[cyan]Ń Gbà: {progress:.1f}% ({peers} àwọn ẹgbẹ́)[/cyan]",
        "[cyan]Downloading: {progress:.1f}% ({rate:.2f} MB/s, {peers} peers)[/cyan]": "[cyan]Ń Gbà: {progress:.1f}% ({rate:.2f} MB/s, {peers} àwọn ẹgbẹ́)[/cyan]",
        "[cyan]Initializing session components...[/cyan]": "[cyan]Ń bẹ̀rẹ̀ àwọn apá àkókò...[/cyan]",
        "[cyan]Troubleshooting:[/cyan]": "[cyan]Ìṣọdọtun:[/cyan]",
        "[cyan]Waiting for session components to be ready (max 60s)...[/cyan]": "[cyan]Ń dúró fún àwọn apá àkókò láti ṣeé ṣe (ààlà 60s)...[/cyan]",
        "[dim]Consider using daemon commands or stop the daemon first: 'btbt daemon exit'[/dim]": "[dim]Rò pé o lo àwọn àṣẹ daemon tàbí dákẹ́ daemon kíákíá: 'btbt daemon exit'[/dim]",
        "[green]All files selected[/green]": "[green]Àwọn fáìlì gbogbo tí a yàn[/green]",
        "[green]Applied auto-tuned configuration[/green]": "[green]Ètò tí a ṣàtúnṣe laifọwọ́yí ti wà[/green]",
        "[green]Applied profile {name}[/green]": "[green]Àkọlé {name} ti wà[/green]",
        "[green]Applied template {name}[/green]": "[green]Àpẹrẹ {name} ti wà[/green]",
        "[green]Backup created: {path}[/green]": "[green]Ìgbàgbẹ́ ti ṣẹ̀dá: {path}[/green]",
        "[green]Cleaned up {count} old checkpoints[/green]": "[green]A ti ṣe ìmọ́tẹ̀ {count} àwọn ibi ìgbéyẹ̀wò tí ó kù[/green]",
        "[green]Cleared active alerts[/green]": "[green]Àwọn àkíyèsí tó nṣiṣẹ́ ti pa[/green]",
        "[green]Configuration reloaded[/green]": "[green]Ètò ti tún ṣe[/green]",
        "[green]Configuration restored[/green]": "[green]Ètò ti padà[/green]",
        "[green]Connected to {count} peer(s)[/green]": "[green]Tí dípọ̀ sí {count} ẹgbẹ́[/green]",
        "[green]Daemon status: {status}[/green]": "[green]Ìpàdé daemon: {status}[/green]",
        "[green]Download completed, stopping session...[/green]": "[green]Ìgbàsílẹ̀ ti parí, ń dákẹ́ àkókò...[/green]",
        "[green]Download completed: {name}[/green]": "[green]Ìgbàsílẹ̀ ti parí: {name}[/green]",
        "[green]Exported checkpoint to {path}[/green]": "[green]Ibi ìgbéyẹ̀wò ti jádé sí {path}[/green]",
        "[green]Exported configuration to {out}[/green]": "[green]Ètò ti jádé sí {out}[/green]",
        "[green]Imported configuration[/green]": "[green]Ètò ti wọlé[/green]",
        "[green]Loaded {count} rules[/green]": "[green]{count} ìlànà ti wọlé[/green]",
        "[green]Magnet added successfully: {hash}...[/green]": "[green]Ìjápọ̀ magnet ti ṣàfikún ní àṣeyọrí: {hash}...[/green]",
        "[green]Magnet added to daemon: {hash}[/green]": "[green]Ìjápọ̀ magnet ti ṣàfikún sí daemon: {hash}[/green]",
        "[green]Metadata fetched successfully![/green]": "[green]Metadata ti gbà ní àṣeyọrí![/green]",
        "[green]Migrated checkpoint to {path}[/green]": "[green]Ibi ìgbéyẹ̀wò ti gbérí sí {path}[/green]",
        "[green]Monitoring started[/green]": "[green]Ìtọ́sọ́nà ti bẹ̀rẹ̀[/green]",
        "[green]Resuming download from checkpoint...[/green]": "[green]Ń tún bẹ̀rẹ̀ ìgbàsílẹ̀ láti ibi ìgbéyẹ̀wò...[/green]",
        "[green]Rule added[/green]": "[green]Ìlànà ti ṣàfikún[/green]",
        "[green]Rule evaluated[/green]": "[green]Ìlànà ti ṣàyẹ̀wò[/green]",
        "[green]Rule removed[/green]": "[green]Ìlànà ti yọ kúrò[/green]",
        "[green]Saved rules[/green]": "[green]Àwọn ìlànà ti fipamọ́[/green]",
        "[green]Selected file {idx}[/green]": "[green]Fáìlì {idx} tí a yàn[/green]",
        "[green]Selected {count} file(s) for download[/green]": "[green]{count} fáìlì tí a yàn fún ìgbàsílẹ̀[/green]",
        "[green]Set priority for file {idx} to {priority}[/green]": "[green]Àkànkàn fáìlì {idx} ti ṣètò sí {priority}[/green]",
        "[green]Starting web interface on http://{host}:{port}[/green]": "[green]Ń bẹ̀rẹ̀ kiolesura wẹ́ẹ̀bù lórí http://{host}:{port}[/green]",
        "[green]Torrent added to daemon: {hash}[/green]": "[green]Torrent ti ṣàfikún sí daemon: {hash}[/green]",
        "[green]Updated runtime configuration[/green]": "[green]Ètò àkókò ṣiṣẹ́ ti ṣàtúnṣe[/green]",
        "[green]Wrote metrics to {out}[/green]": "[green]Àwọn métíríkì ti kọ sí {out}[/green]",
        "[red]Backup failed: {msgs}[/red]": "[red]Ìgbàgbẹ́ kò ṣe: {msgs}[/red]",
        "[red]Error: Could not parse magnet link[/red]": "[red]Àṣìṣe: Kò ṣeé ṣàlàyé ìjápọ̀ magnet[/red]",
        "[red]Error: {error}[/red]": "[red]Àṣìṣe: {error}[/red]",
        "[red]Failed to add magnet link: {error}[/red]": "[red]Kò ṣeé ṣàfikún ìjápọ̀ magnet: {error}[/red]",
        "[red]Failed to set config: {error}[/red]": "[red]Kò ṣeé ṣètò ètò: {error}[/red]",
        "[red]File not found: {error}[/red]": "[red]Fáìlì kò rí: {error}[/red]",
        "[red]Invalid arguments[/red]": "[red]Àwọn àtúnṣe kò tọ́[/red]",
        "[red]Invalid file index: {idx}[/red]": "[red]Fáhìrísì fáìlì kò tọ́: {idx}[/red]",
        "[red]Invalid file index[/red]": "[red]Fáhìrísì fáìlì kò tọ́[/red]",
        "[red]Invalid info hash format: {hash}[/red]": "[red]Àwọn ètò hash àlàyé kò tọ́: {hash}[/red]",
        "[red]Invalid priority. Use: do_not_download/low/normal/high/maximum[/red]": "[red]Àkànkàn kò tọ́. Lo: do_not_download/low/normal/high/maximum[/red]",
        "[red]Invalid priority: {priority}. Use: do_not_download/low/normal/high/maximum[/red]": "[red]Àkànkàn kò tọ́: {priority}. Lo: do_not_download/low/normal/high/maximum[/red]",
        "[red]Invalid torrent file: {error}[/red]": "[red]Fáìlì torrent kò tọ́: {error}[/red]",
        "[red]Key not found: {key}[/red]": "[red]Ọ̀nà kò rí: {key}[/red]",
        "[red]No checkpoint found for {hash}[/red]": "[red]Kò sí ibi ìgbéyẹ̀wò tí a rí fún {hash}[/red]",
        "[red]PyYAML not installed[/red]": "[red]PyYAML kò fi sílẹ̀[/red]",
        "[red]Reload failed: {error}[/red]": "[red]Títún ṣe kò ṣe: {error}[/red]",
        "[red]Restore failed: {msgs}[/red]": "[red]Ìpadà kò ṣe: {msgs}[/red]",
        "[red]{error}[/red]": "[red]{error}[/red]",  # Format string - error variable will be translated separately
        "[yellow]All files deselected[/yellow]": "[yellow]Àwọn fáìlì gbogbo tí a yọ kúrò[/yellow]",
        "[yellow]Debug mode not yet implemented[/yellow]": "[yellow]Àwọn àkókò ìṣọdọtun kò tíì ṣe[/yellow]",
        "[yellow]Deselected file {idx}[/yellow]": "[yellow]Fáìlì {idx} tí a yọ kúrò[/yellow]",
        "[yellow]Download interrupted by user[/yellow]": "[yellow]Ìgbàsílẹ̀ tí olùlo dákẹ́[/yellow]",
        "[yellow]Fetching metadata from peers...[/yellow]": "[yellow]Ń gbà metadata láti àwọn ẹgbẹ́...[/yellow]",
        "[yellow]Invalid priority spec '{spec}': {error}[/yellow]": "[yellow]Àkànkàn '{spec}' kò tọ́: {error}[/yellow]",
        "[yellow]Keeping session alive[/yellow]": "[yellow]Ń ṣàgbà àkókò[/yellow]",
        "[yellow]No checkpoints found[/yellow]": "[yellow]Kò sí àwọn ibi ìgbéyẹ̀wò tí a rí[/yellow]",
        "[yellow]Torrent session ended[/yellow]": "[yellow]Àkókò torrent ti parí[/yellow]",
        "[yellow]Unknown command: {cmd}[/yellow]": "[yellow]Àṣẹ àìmọ̀: {cmd}[/yellow]",
        "[yellow]Warning: Daemon is running. Starting local session may cause port conflicts.[/yellow]": "[yellow]Àkíyèsí: Daemon ń ṣiṣẹ́. Bíríbẹ̀rẹ̀ àkókò agbègbè lè fa ìjà àwọn pọ́ọ̀tì.[/yellow]",
        "[yellow]Warning: Error stopping session: {error}[/yellow]": "[yellow]Àkíyèsí: Àṣìṣe nínú dídákẹ́ àkókò: {error}[/yellow]",
        "[yellow]{warning}[/yellow]": "[yellow]{warning}[/yellow]",
        # Multi-line strings
        "\nAvailable Commands:\n  help          - Show this help message\n  status        - Show current status\n  peers         - Show connected peers\n  files         - Show file information\n  pause         - Pause download\n  resume        - Resume download\n  stop          - Stop download\n  quit          - Quit application\n  clear         - Clear screen\n        ": "\nÀwọn Àṣẹ Tí Wà:\n  help          - Fihàn ìrànlọ́wọ́ yìí\n  status        - Fihàn ìpàdé lọ́wọ́lọ́wọ́\n  peers         - Fihàn àwọn ẹgbẹ́ tí dípọ̀\n  files         - Fihàn àlàyé fáìlì\n  pause         - Dúró ìgbàsílẹ̀\n  resume        - Tún bẹ̀rẹ̀ ìgbàsílẹ̀\n  stop          - Dákẹ́ ìgbàsílẹ̀\n  quit          - Jáde kúrò nínú ohun èlò\n  clear         - Mọ́ skríìnì\n        ",
        "\n[bold cyan]File Selection[/bold cyan]": "\n[bold cyan]Ìyàn Fáìlì[/bold cyan]",
        "\n[bold]File selection[/bold]": "\n[bold]Ìyàn fáìlì[/bold]",
        "\n[yellow]Commands:[/yellow]": "\n[yellow]Àwọn Àṣẹ:[/yellow]",
        "\n[yellow]File selection cancelled, using defaults[/yellow]": "\n[yellow]Ìyàn fáìlì ti fagilé, ń lo àwọn àyípadà[/yellow]",
        "\n[yellow]Tracker Scrape Statistics:[/yellow]": "\n[yellow]Ìṣirò Tracker Scrape:[/yellow]",
        "\n[yellow]Use: files select <index>, files deselect <index>, files priority <index> <priority>[/yellow]": "\n[yellow]Lo: files select <index>, files deselect <index>, files priority <index> <priority>[/yellow]",
        "\n[yellow]Warning: No peers connected after 30 seconds[/yellow]": "\n[yellow]Àkíyèsí: Kò sí àwọn ẹgbẹ́ tí dípọ̀ lẹ́yìn ìṣẹ́jú 30[/yellow]",
        "  [cyan]deselect <index>[/cyan] - Deselect a file": "  [cyan]deselect <index>[/cyan] - Yọ fáìlì kúrò",
        "  [cyan]deselect-all[/cyan] - Deselect all files": "  [cyan]deselect-all[/cyan] - Yọ gbogbo àwọn fáìlì kúrò",
        "  [cyan]done[/cyan] - Finish selection and start download": "  [cyan]done[/cyan] - Parí ìyàn àti bẹ̀rẹ̀ ìgbàsílẹ̀",
        "  [cyan]priority <index> <priority>[/cyan] - Set priority (do_not_download/low/normal/high/maximum)": "  [cyan]priority <index> <priority>[/cyan] - Ṣètò àkànkàn (do_not_download/low/normal/high/maximum)",
        "  [cyan]select <index>[/cyan] - Select a file": "  [cyan]select <index>[/cyan] - Yàn fáìlì",
        "  [cyan]select-all[/cyan] - Select all files": "  [cyan]select-all[/cyan] - Yàn gbogbo àwọn fáìlì",
        "  • Check if torrent has active seeders": "  • Ṣàyẹ̀wò bí torrent bá ní àwọn olùgbìn tó nṣiṣẹ́",
        "  • Ensure DHT is enabled: --enable-dht": "  • Rí dájú pé DHT ti mú ṣiṣẹ́: --enable-dht",
        "  • Run 'btbt diagnose-connections' to check connection status": "  • Ṣe 'btbt diagnose-connections' láti ṣàyẹ̀wò ìpàdé ìdípọ̀",
        "  • Verify NAT/firewall settings": "  • Jẹ́rìí àwọn ètò NAT/firewall",
        " | Files: {selected}/{total} selected": " | Àwọn Fáìlì: {selected}/{total} tí a yàn",
        " | Private: {count}": " | Ìkọ̀kọ̀: {count}",
        "ccBitTorrent Interactive CLI": "ccBitTorrent CLI Ìbaraẹnisọrọ̀",
        "ccBitTorrent Status": "Ìpàdé ccBitTorrent",
        "help, status, peers, files, pause, resume, stop, config, limits, strategy, discovery, checkpoint, metrics, alerts, export, import, backup, restore, capabilities, auto_tune, template, profile, config_backup, config_diff, config_export, config_import, config_schema": "help, status, peers, files, pause, resume, stop, config, limits, strategy, discovery, checkpoint, metrics, alerts, export, import, backup, restore, capabilities, auto_tune, template, profile, config_backup, config_diff, config_export, config_import, config_schema",
        "Usage: alerts list|list-active|add|remove|clear|load|save|test ...": "Lílò: alerts list|list-active|add|remove|clear|load|save|test ...",
        "Usage: backup <info_hash> <dest>": "Lílò: backup <info_hash> <dest>",
        "Usage: checkpoint list": "Lílò: checkpoint list",
        "Usage: config [show|get|set|reload] ...": "Lílò: config [show|get|set|reload] ...",
        "Usage: config get <key.path>": "Lílò: config get <key.path>",
        "Usage: config set <key.path> <value>": "Lílò: config set <key.path> <value>",
        "Usage: config_backup list|create [desc]|restore <file>": "Lílò: config_backup list|create [desc]|restore <file>",
        "Usage: config_diff <file1> <file2>": "Lílò: config_diff <file1> <file2>",
        "Usage: config_export <toml|json|yaml> <output>": "Lílò: config_export <toml|json|yaml> <output>",
        "Usage: config_import <toml|json|yaml> <input>": "Lílò: config_import <toml|json|yaml> <input>",
        "Usage: export <path>": "Lílò: export <path>",
        "Usage: import <path>": "Lílò: import <path>",
        "Usage: limits [show|set] <info_hash> [down up]": "Lílò: limits [show|set] <info_hash> [down up]",
        "Usage: limits set <info_hash> <down_kib> <up_kib>": "Lílò: limits set <info_hash> <down_kib> <up_kib>",
        "Usage: metrics show [system|performance|all] | metrics export [json|prometheus] [output]": "Lílò: metrics show [system|performance|all] | metrics export [json|prometheus] [output]",
        "Usage: profile list | profile apply <name>": "Lílò: profile list | profile apply <name>",
        "Usage: restore <backup_file>": "Lílò: restore <backup_file>",
        "Usage: template list | template apply <name> [merge]": "Lílò: template list | template apply <name> [merge]",
    }

    # Handle Rich markup
    if msgid.startswith("[") and "]" in msgid:
        # First check if we have a direct translation for the full string
        if msgid in translations:
            return translations[msgid]

        markup_match = re.match(r"^(\[[^\]]+\])(.*?)(\[/[^\]]+\])?$", msgid)
        if markup_match:
            open_tag = markup_match.group(1)
            content = markup_match.group(2)
            close_tag = markup_match.group(3) or ""
            translated_content = translations.get(content, content)
            return f"{open_tag}{translated_content}{close_tag}"

    # First check for direct translation (including multi-line strings)
    if msgid in translations:
        return translations[msgid]

    # Handle multi-line strings - try to translate line by line if no direct match
    if "\n" in msgid:
        lines = msgid.split("\n")
        translated_lines = []
        for line in lines:
            if line.strip() in translations:
                translated_lines.append(translations[line.strip()])
            else:
                translated_lines.append(line)
        return "\n".join(translated_lines)

    return translations.get(msgid, msgid)


def translate_hausa(msgid: str) -> str:
    """Translate English string to Hausa."""
    translations = {
        "Active": "Aiki",
        "Active Alerts": "Faɗakarwa Masu Aiki",
        "Active: {count}": "Aiki: {count}",
        "Advanced Add": "Ƙara Mai Zurfi",
        "Alert Rules": "Dokoki na Faɗakarwa",
        "Alerts": "Faɗakarwa",
        "Announce: Failed": "Sanarwa: An Gaza",
        "Announce: {status}": "Sanarwa: {status}",
        "Are you sure you want to quit?": "Ka tabbata kana son fita?",
        "Automatically restart daemon if needed (without prompt)": "Sake farawa daemon ta atomatik idan an buƙata (ba tare da tambaya ba)",
        "Browse": "Bincike",
        "Capability": "Ikon",
        "Commands: ": "Umarni: ",
        "Completed": "An Kammala",
        "Completed (Scrape)": "An Kammala (Scrape)",
        "Component": "Bangare",
        "Condition": "Yanayi",
        "Config Backups": "Ajiyayyun Saituna",
        "Configuration file path": "Hanyar fayil na saituna",
        "Confirm": "Tabbatar",
        "Connected": "An Haɗa",
        "Connected Peers": "Abokan Haɗin Kai An Haɗa",
        "Count: {count}{file_info}{private_info}": "Ƙidaya: {count}{file_info}{private_info}",
        "Create backup before migration": "Ƙirƙiri ajiya kafin ƙaura",
        "DHT": "DHT",
        "Description": "Bayani",
        "Details": "Cikakkun Bayanai",
        "Disabled": "An Kashe",
        "Download": "Zazzage",
        "Download Speed": "Saurin Zazzagewa",
        "Download paused": "Zazzagewa an dakata",
        "Download resumed": "Zazzagewa an ci gaba",
        "Download stopped": "Zazzagewa an tsayar",
        "Downloaded": "An Zazzage",
        "Downloading {name}": "Ana Zazzagewa {name}",
        "ETA": "Lokacin Kammalawa",
        "Enable debug mode": "Kunna yanayin gyarawa",
        "Enable verbose output": "Kunna fitarwa mai cikakken bayani",
        "Enabled": "An Kunna",
        "Error reading scrape cache": "Kuskure a karanta cache na scrape",
        "Explore": "Bincike",
        "Failed": "An Gaza",
        "Failed to register torrent in session": "An gaza yin rajista torrent a cikin zaman",
        "File": "Fayil",
        "File Name": "Sunan Fayil",
        "File selection not available for this torrent": "Zaɓin fayil baya samuwa ga wannan torrent",
        "Files": "Fayiloli",
        "Global Config": "Saitunan Duniya",
        "Help": "Taimako",
        "History": "Tarihi",
        "ID": "ID",
        "IP": "IP",
        "IP Filter": "Tace IP",
        "IPFS": "IPFS",
        "Info Hash": "Hash na Bayani",
        "Interactive backup": "Ajiya mai hulɗa",
        "Invalid torrent file format": "Tsarin fayil na torrent bai daidaita ba",
        "Key": "Maɓalli",
        "Key not found: {key}": "Ba a sami maɓalli: {key}",
        "Last Scrape": "Scrape na Ƙarshe",
        "Leechers": "Masu Zazzagewa",
        "Leechers (Scrape)": "Masu Zazzagewa (Scrape)",
        "MIGRATED": "AN ƘAURA",
        "Menu": "Menu",
        "Metric": "Ma'auni",
        "NAT Management": "Gudanar da NAT",
        "Name": "Suna",
        "Network": "Hanyar Sadarwa",
        "No": "A'a",
        "No active alerts": "Babu faɗakarwa masu aiki",
        "No alert rules": "Babu dokoki na faɗakarwa",
        "No alert rules configured": "Babu dokoki na faɗakarwa da aka saita",
        "No backups found": "Ba a sami ajiyayyu",
        "No cached results": "Babu sakamako da aka adana",
        "No checkpoints": "Babu wuraren bincike",
        "No config file to backup": "Babu fayil na saituna don ajiya",
        "No peers connected": "Babu abokan haɗin kai da aka haɗa",
        "No profiles available": "Babu bayanan martaba da ake samu",
        "No templates available": "Babu samfura da ake samu",
        "No torrent active": "Babu torrent mai aiki",
        "Nodes: {count}": "Nodes: {count}",
        "Not available": "Ba Ake Samuwa Ba",
        "Not configured": "Ba Aka Saita Ba",
        "Not supported": "Ba Ake Taimakawa Ba",
        "OK": "Yayi",
        "Operation not supported": "Aiki ba ake taimakawa ba",
        "PEX: {status}": "PEX: {status}",  # PEX is technical acronym
        "Pause": "Dakata",
        "Peers": "Abokan Haɗin Kai",
        "Performance": "Aiki",
        "Pieces": "Guda",
        "Port": "Tashar Jiragen Ruwa",
        "Port: {port}": "Tashar Jiragen Ruwa: {port}",
        "Priority": "Fifiko",
        "Private": "Sirri",
        "Profiles": "Bayanan Martaba",
        "Progress": "Ci Gaba",
        "Property": "Dukiya",
        "Proxy Config": "Saitunan Proxy",
        "PyYAML is required for YAML output": "Ana buƙatar PyYAML don fitarwa ta YAML",
        "Quick Add": "Ƙara Maimakon",
        "Quit": "Fita",
        "Rate limits disabled": "Iyakoki na sauri an kashe",
        "Rate limits set to 1024 KiB/s": "Iyakoki na sauri an saita zuwa 1024 KiB/s",
        "Rehash: {status}": "Rehash: {status}",  # Technical term
        "Resume": "Ci Gaba",
        "Rule": "Doka",
        "Rule not found: {name}": "Ba a sami doka: {name}",
        "Rules: {rules}, IPv4: {ipv4}, IPv6: {ipv6}, Blocks: {blocks}": "Dokoki: {rules}, IPv4: {ipv4}, IPv6: {ipv6}, Tubalan: {blocks}",
        "Running": "Ana Gudana",
        "SSL Config": "Saitunan SSL",
        "Scrape Results": "Sakamakon Scrape",
        "Scrape: {status}": "Scrape: {status}",  # Technical term
        "Section not found: {section}": "Ba a sami sashe: {section}",
        "Security Scan": "Binciken Tsaro",
        "Seeders": "Masu Shuka",
        "Seeders (Scrape)": "Masu Shuka (Scrape)",
        "Select files to download": "Zaɓi fayiloli don zazzagewa",
        "Selected": "An Zaɓa",
        "Session": "Zaman",
        "Set value in global config file": "Saita ƙima a cikin fayil na saitunan duniya",
        "Set value in project local ccbt.toml": "Saita ƙima a cikin ccbt.toml na gida na aikin",
        "Severity": "Matsala",
        "Show specific key path (e.g. network.listen_port)": "Nuna hanyar maɓalli ta musamman (misali. network.listen_port)",
        "Show specific section key path (e.g. network)": "Nuna hanyar maɓalli na sashe ta musamman (misali. network)",
        "Size": "Girman",
        "Skip confirmation prompt": "Tsallake tambayar tabbatarwa",
        "Skip daemon restart even if needed": "Tsallake sake farawa daemon ko da an buƙata",
        "Snapshot failed: {error}": "Hotunan lokaci an gaza: {error}",
        "Snapshot saved to {path}": "Hotunan lokaci an adana zuwa {path}",
        "Status": "Matsayi",
        "Status: ": "Matsayi: ",
        "Supported": "Ana Taimakawa",
        "System Capabilities": "Ikon Tsarin",
        "System Capabilities Summary": "Taƙaitaccen Ikon Tsarin",
        "System Resources": "Albarkatun Tsarin",
        "Templates": "Samfura",
        "Timestamp": "Alamar Lokaci",
        "Torrent Config": "Saitunan Torrent",
        "Torrent Status": "Matsayin Torrent",
        "Torrent file not found": "Ba a sami fayil na torrent",
        "Torrent not found": "Ba a sami torrent",
        "Torrents": "Torrents",  # Technical term - commonly used as-is
        "Torrents: {count}": "Torrents: {count}",
        "Tracker Scrape": "Scrape na Tracker",
        "Type": "Nau'i",
        "Unknown": "Ba A Sani Ba",
        "Unknown subcommand": "Ƙaramin umarni ba a sani ba",
        "Unknown subcommand: {sub}": "Ƙaramin umarni ba a sani ba: {sub}",
        "Upload": "Loda",
        "Upload Speed": "Saurin Lodawa",
        "Uptime: {uptime:.1f}s": "Lokacin Aiki: {uptime:.1f}s",
        "Use --confirm to proceed with reset": "Yi amfani da --confirm don ci gaba da sake saita",
        "VALID": "DAIDAI",
        "Value": "Ƙima",
        "Welcome": "Barka da zuwa",
        "Xet": "Xet",  # Technical term/brand name
        "Yes": "Ee",
        "Yes (BEP 27)": "Ee (BEP 27)",
        "uTP Config": "Saitunan uTP",
        "{count} features": "{count} fasaloli",
        "{count} items": "{count} abubuwa",
        "{elapsed:.0f}s ago": "Sakonnin {elapsed:.0f} da suka wuce",
        # Rich markup strings
        "[cyan]Adding magnet link and fetching metadata...[/cyan]": "[cyan]Ana ƙara hanyar haɗin magnet kuma ana zazzage bayanai...[/cyan]",
        "[cyan]Downloading: {progress:.1f}% ({peers} peers)[/cyan]": "[cyan]Ana Zazzagewa: {progress:.1f}% ({peers} abokan haɗin kai)[/cyan]",
        "[cyan]Downloading: {progress:.1f}% ({rate:.2f} MB/s, {peers} peers)[/cyan]": "[cyan]Ana Zazzagewa: {progress:.1f}% ({rate:.2f} MB/s, {peers} abokan haɗin kai)[/cyan]",
        "[cyan]Initializing session components...[/cyan]": "[cyan]Ana farawa bangarorin zaman...[/cyan]",
        "[cyan]Troubleshooting:[/cyan]": "[cyan]Magance Matsaloli:[/cyan]",
        "[cyan]Waiting for session components to be ready (max 60s)...[/cyan]": "[cyan]Ana jira bangarorin zaman su shirya (matsakaici 60s)...[/cyan]",
        "[dim]Consider using daemon commands or stop the daemon first: 'btbt daemon exit'[/dim]": "[dim]Yi la'akari da amfani da umarnin daemon ko ka tsayar da daemon da farko: 'btbt daemon exit'[/dim]",
        "[green]All files selected[/green]": "[green]Duk fayiloli an zaɓa[/green]",
        "[green]Applied auto-tuned configuration[/green]": "[green]An yi amfani da saitunan da aka daidaita ta atomatik[/green]",
        "[green]Applied profile {name}[/green]": "[green]An yi amfani da bayanan martaba {name}[/green]",
        "[green]Applied template {name}[/green]": "[green]An yi amfani da samfura {name}[/green]",
        "[green]Backup created: {path}[/green]": "[green]An ƙirƙiri ajiya: {path}[/green]",
        "[green]Cleaned up {count} old checkpoints[/green]": "[green]An tsabtace wuraren bincike {count} na tsoho[/green]",
        "[green]Cleared active alerts[/green]": "[green]An share faɗakarwa masu aiki[/green]",
        "[green]Configuration reloaded[/green]": "[green]An sake loda saituna[/green]",
        "[green]Configuration restored[/green]": "[green]An maido da saituna[/green]",
        "[green]Connected to {count} peer(s)[/green]": "[green]An haɗa zuwa {count} abokin haɗin kai[/green]",
        "[green]Daemon status: {status}[/green]": "[green]Matsayin daemon: {status}[/green]",
        "[green]Download completed, stopping session...[/green]": "[green]Zazzagewa ta ƙare, ana tsayar da zaman...[/green]",
        "[green]Download completed: {name}[/green]": "[green]Zazzagewa ta ƙare: {name}[/green]",
        "[green]Exported checkpoint to {path}[/green]": "[green]An fitar da wurin bincike zuwa {path}[/green]",
        "[green]Exported configuration to {out}[/green]": "[green]An fitar da saituna zuwa {out}[/green]",
        "[green]Imported configuration[/green]": "[green]An shigo da saituna[/green]",
        "[green]Loaded {count} rules[/green]": "[green]An loda dokoki {count}[/green]",
        "[green]Magnet added successfully: {hash}...[/green]": "[green]An ƙara hanyar haɗin magnet cikin nasara: {hash}...[/green]",
        "[green]Magnet added to daemon: {hash}[/green]": "[green]An ƙara hanyar haɗin magnet zuwa daemon: {hash}[/green]",
        "[green]Metadata fetched successfully![/green]": "[green]An zazzage bayanai cikin nasara![/green]",
        "[green]Migrated checkpoint to {path}[/green]": "[green]An ƙaura wurin bincike zuwa {path}[/green]",
        "[green]Monitoring started[/green]": "[green]An fara sa ido[/green]",
        "[green]Resuming download from checkpoint...[/green]": "[green]Ana ci gaba da zazzagewa daga wurin bincike...[/green]",
        "[green]Rule added[/green]": "[green]An ƙara doka[/green]",
        "[green]Rule evaluated[/green]": "[green]An kimanta doka[/green]",
        "[green]Rule removed[/green]": "[green]An cire doka[/green]",
        "[green]Saved rules[/green]": "[green]An adana dokoki[/green]",
        "[green]Selected file {idx}[/green]": "[green]An zaɓi fayil {idx}[/green]",
        "[green]Selected {count} file(s) for download[/green]": "[green]An zaɓi fayiloli {count} don zazzagewa[/green]",
        "[green]Set priority for file {idx} to {priority}[/green]": "[green]An saita fifiko na fayil {idx} zuwa {priority}[/green]",
        "[green]Starting web interface on http://{host}:{port}[/green]": "[green]Ana farawa hanyar sadarwa ta yanar gizo akan http://{host}:{port}[/green]",
        "[green]Torrent added to daemon: {hash}[/green]": "[green]An ƙara torrent zuwa daemon: {hash}[/green]",
        "[green]Updated runtime configuration[/green]": "[green]An sabunta saitunan lokacin aiki[/green]",
        "[green]Wrote metrics to {out}[/green]": "[green]An rubuta ma'auni zuwa {out}[/green]",
        "[red]Backup failed: {msgs}[/red]": "[red]Ajiya ta gaza: {msgs}[/red]",
        "[red]Error: Could not parse magnet link[/red]": "[red]Kuskure: Ba za a iya fassara hanyar haɗin magnet ba[/red]",
        "[red]Error: {error}[/red]": "[red]Kuskure: {error}[/red]",
        "[red]Failed to add magnet link: {error}[/red]": "[red]An gaza ƙara hanyar haɗin magnet: {error}[/red]",
        "[red]Failed to set config: {error}[/red]": "[red]An gaza saita saituna: {error}[/red]",
        "[red]File not found: {error}[/red]": "[red]Ba a sami fayil: {error}[/red]",
        "[red]Invalid arguments[/red]": "[red]Hujjoji marasa inganci[/red]",
        "[red]Invalid file index: {idx}[/red]": "[red]Fihirar fayil mara inganci: {idx}[/red]",
        "[red]Invalid file index[/red]": "[red]Fihirar fayil mara inganci[/red]",
        "[red]Invalid info hash format: {hash}[/red]": "[red]Tsarin hash na bayani mara inganci: {hash}[/red]",
        "[red]Invalid priority. Use: do_not_download/low/normal/high/maximum[/red]": "[red]Fifiko mara inganci. Yi amfani da: do_not_download/low/normal/high/maximum[/red]",
        "[red]Invalid priority: {priority}. Use: do_not_download/low/normal/high/maximum[/red]": "[red]Fifiko mara inganci: {priority}. Yi amfani da: do_not_download/low/normal/high/maximum[/red]",
        "[red]Invalid torrent file: {error}[/red]": "[red]Fayil na torrent mara inganci: {error}[/red]",
        "[red]Key not found: {key}[/red]": "[red]Ba a sami maɓalli: {key}[/red]",
        "[red]No checkpoint found for {hash}[/red]": "[red]Ba a sami wurin bincike don {hash}[/red]",
        "[red]PyYAML not installed[/red]": "[red]Ba a shigar da PyYAML ba[/red]",
        "[red]Reload failed: {error}[/red]": "[red]Sake lodawa ya gaza: {error}[/red]",
        "[red]Restore failed: {msgs}[/red]": "[red]Maido ya gaza: {msgs}[/red]",
        "[red]{error}[/red]": "[red]{error}[/red]",  # Format string - error variable will be translated separately
        "[yellow]All files deselected[/yellow]": "[yellow]Duk fayiloli an cire zaɓi[/yellow]",
        "[yellow]Debug mode not yet implemented[/yellow]": "[yellow]Yanayin gyarawa bai cika ba tukuna[/yellow]",
        "[yellow]Deselected file {idx}[/yellow]": "[yellow]An cire zaɓin fayil {idx}[/yellow]",
        "[yellow]Download interrupted by user[/yellow]": "[yellow]Zazzagewa ta katse ta mai amfani[/yellow]",
        "[yellow]Fetching metadata from peers...[/yellow]": "[yellow]Ana zazzage bayanai daga abokan haɗin kai...[/yellow]",
        "[yellow]Invalid priority spec '{spec}': {error}[/yellow]": "[yellow]Fifiko '{spec}' mara inganci: {error}[/yellow]",
        "[yellow]Keeping session alive[/yellow]": "[yellow]Ana kiyaye zaman a raye[/yellow]",
        "[yellow]No checkpoints found[/yellow]": "[yellow]Ba a sami wuraren bincike[/yellow]",
        "[yellow]Torrent session ended[/yellow]": "[yellow]Zaman na torrent ya ƙare[/yellow]",
        "[yellow]Unknown command: {cmd}[/yellow]": "[yellow]Umarni da ba a sani ba: {cmd}[/yellow]",
        "[yellow]Warning: Daemon is running. Starting local session may cause port conflicts.[/yellow]": "[yellow]Gargadi: Daemon yana gudana. Farawa zaman na gida na iya haifar da rikice-rikice na tashar jiragen ruwa.[/yellow]",
        "[yellow]Warning: Error stopping session: {error}[/yellow]": "[yellow]Gargadi: Kuskure wajen tsayar da zaman: {error}[/yellow]",
        "[yellow]{warning}[/yellow]": "[yellow]{warning}[/yellow]",
        # Multi-line strings
        "\nAvailable Commands:\n  help          - Show this help message\n  status        - Show current status\n  peers         - Show connected peers\n  files         - Show file information\n  pause         - Pause download\n  resume        - Resume download\n  stop          - Stop download\n  quit          - Quit application\n  clear         - Clear screen\n        ": "\nUmarni da Ake Samu:\n  help          - Nuna wannan saƙon taimako\n  status        - Nuna matsayi na yanzu\n  peers         - Nuna abokan haɗin kai da aka haɗa\n  files         - Nuna bayanin fayil\n  pause         - Dakatar da zazzagewa\n  resume        - Ci gaba da zazzagewa\n  stop          - Tsayar da zazzagewa\n  quit          - Fita daga aikace-aikacen\n  clear         - Share allo\n        ",
        "\n[bold cyan]File Selection[/bold cyan]": "\n[bold cyan]Zaɓin Fayil[/bold cyan]",
        "\n[bold]File selection[/bold]": "\n[bold]Zaɓin fayil[/bold]",
        "\n[yellow]Commands:[/yellow]": "\n[yellow]Umarni:[/yellow]",
        "\n[yellow]File selection cancelled, using defaults[/yellow]": "\n[yellow]Zaɓin fayil an soke, ana amfani da na asali[/yellow]",
        "\n[yellow]Tracker Scrape Statistics:[/yellow]": "\n[yellow]Ƙididdigar Tracker Scrape:[/yellow]",
        "\n[yellow]Use: files select <index>, files deselect <index>, files priority <index> <priority>[/yellow]": "\n[yellow]Yi amfani da: files select <index>, files deselect <index>, files priority <index> <priority>[/yellow]",
        "\n[yellow]Warning: No peers connected after 30 seconds[/yellow]": "\n[yellow]Gargadi: Babu abokan haɗin kai da aka haɗa bayan dakika 30[/yellow]",
        "  [cyan]deselect <index>[/cyan] - Deselect a file": "  [cyan]deselect <index>[/cyan] - Cire zaɓin fayil",
        "  [cyan]deselect-all[/cyan] - Deselect all files": "  [cyan]deselect-all[/cyan] - Cire zaɓin duk fayiloli",
        "  [cyan]done[/cyan] - Finish selection and start download": "  [cyan]done[/cyan] - Kammala zaɓi kuma fara zazzagewa",
        "  [cyan]priority <index> <priority>[/cyan] - Set priority (do_not_download/low/normal/high/maximum)": "  [cyan]priority <index> <priority>[/cyan] - Saita fifiko (do_not_download/low/normal/high/maximum)",
        "  [cyan]select <index>[/cyan] - Select a file": "  [cyan]select <index>[/cyan] - Zaɓi fayil",
        "  [cyan]select-all[/cyan] - Select all files": "  [cyan]select-all[/cyan] - Zaɓi duk fayiloli",
        "  • Check if torrent has active seeders": "  • Bincika ko torrent yana da masu shuka masu aiki",
        "  • Ensure DHT is enabled: --enable-dht": "  • Tabbatar an kunna DHT: --enable-dht",
        "  • Run 'btbt diagnose-connections' to check connection status": "  • Gudanar da 'btbt diagnose-connections' don bincika matsayin haɗi",
        "  • Verify NAT/firewall settings": "  • Tabbatar da saitunan NAT/firewall",
        " | Files: {selected}/{total} selected": " | Fayiloli: {selected}/{total} an zaɓa",
        " | Private: {count}": " | Sirri: {count}",
        "ccBitTorrent Interactive CLI": "ccBitTorrent CLI na Hira",
        "ccBitTorrent Status": "Matsayin ccBitTorrent",
        "help, status, peers, files, pause, resume, stop, config, limits, strategy, discovery, checkpoint, metrics, alerts, export, import, backup, restore, capabilities, auto_tune, template, profile, config_backup, config_diff, config_export, config_import, config_schema": "help, status, peers, files, pause, resume, stop, config, limits, strategy, discovery, checkpoint, metrics, alerts, export, import, backup, restore, capabilities, auto_tune, template, profile, config_backup, config_diff, config_export, config_import, config_schema",
        "Usage: alerts list|list-active|add|remove|clear|load|save|test ...": "Amfani: alerts list|list-active|add|remove|clear|load|save|test ...",
        "Usage: backup <info_hash> <dest>": "Amfani: backup <info_hash> <dest>",
        "Usage: checkpoint list": "Amfani: checkpoint list",
        "Usage: config [show|get|set|reload] ...": "Amfani: config [show|get|set|reload] ...",
        "Usage: config get <key.path>": "Amfani: config get <key.path>",
        "Usage: config set <key.path> <value>": "Amfani: config set <key.path> <value>",
        "Usage: config_backup list|create [desc]|restore <file>": "Amfani: config_backup list|create [desc]|restore <file>",
        "Usage: config_diff <file1> <file2>": "Amfani: config_diff <file1> <file2>",
        "Usage: config_export <toml|json|yaml> <output>": "Amfani: config_export <toml|json|yaml> <output>",
        "Usage: config_import <toml|json|yaml> <input>": "Amfani: config_import <toml|json|yaml> <input>",
        "Usage: export <path>": "Amfani: export <path>",
        "Usage: import <path>": "Amfani: import <path>",
        "Usage: limits [show|set] <info_hash> [down up]": "Amfani: limits [show|set] <info_hash> [down up]",
        "Usage: limits set <info_hash> <down_kib> <up_kib>": "Amfani: limits set <info_hash> <down_kib> <up_kib>",
        "Usage: metrics show [system|performance|all] | metrics export [json|prometheus] [output]": "Amfani: metrics show [system|performance|all] | metrics export [json|prometheus] [output]",
        "Usage: profile list | profile apply <name>": "Amfani: profile list | profile apply <name>",
        "Usage: restore <backup_file>": "Amfani: restore <backup_file>",
        "Usage: template list | template apply <name> [merge]": "Amfani: template list | template apply <name> [merge]",
    }

    # Handle Rich markup
    if msgid.startswith("[") and "]" in msgid:
        # First check if we have a direct translation for the full string
        if msgid in translations:
            return translations[msgid]

        markup_match = re.match(r"^(\[[^\]]+\])(.*?)(\[/[^\]]+\])?$", msgid)
        if markup_match:
            open_tag = markup_match.group(1)
            content = markup_match.group(2)
            close_tag = markup_match.group(3) or ""
            translated_content = translations.get(content, content)
            return f"{open_tag}{translated_content}{close_tag}"

    # First check for direct translation (including multi-line strings)
    if msgid in translations:
        return translations[msgid]

    # Handle multi-line strings - try to translate line by line if no direct match
    if "\n" in msgid:
        lines = msgid.split("\n")
        translated_lines = []
        for line in lines:
            if line.strip() in translations:
                translated_lines.append(translations[line.strip()])
            else:
                translated_lines.append(line)
        return "\n".join(translated_lines)

    return translations.get(msgid, msgid)


def parse_po_file(po_path: Path) -> list[tuple[str, str, str]]:
    """Parse .po file and return list of (msgid, msgstr, raw_line) tuples."""
    with open(po_path, encoding="utf-8") as f:
        content = f.read()

    entries = []
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        if line.startswith("msgid "):
            msgid = line[6:].strip('"')
            raw_msgid = line
            i += 1
            # Handle multi-line msgid
            while i < len(lines) and lines[i].strip().startswith('"'):
                # Don't replace \\n yet - keep escaped for matching
                msgid += lines[i].strip().strip('"')
                raw_msgid += "\n" + lines[i]
                i += 1
            # Now unescape for translation matching
            msgid = msgid.replace("\\n", "\n").replace('\\"', '"')

            # Find msgstr
            if i < len(lines) and lines[i].startswith("msgstr "):
                msgstr = lines[i][7:].strip('"')
                raw_msgstr = lines[i]
                i += 1
                while i < len(lines) and lines[i].strip().startswith('"'):
                    msgstr += lines[i].strip().strip('"')
                    raw_msgstr += "\n" + lines[i]
                    i += 1
                # Now unescape
                msgstr = msgstr.replace("\\n", "\n").replace('\\"', '"')

                entries.append((msgid, msgstr, raw_msgid, raw_msgstr))
        else:
            i += 1

    return entries


def escape_po_string(s: str) -> str:
    """Escape string for .po file format."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def create_po_file(
    lang: str,
    lang_name: str,
    lang_team: str,
    plural_forms: str,
    entries: list[tuple[str, str, str, str]],
    translate_func: Callable[[str], str],
    output_path: Path,
) -> None:
    """Create complete .po file with translations."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M%z")

    header = f"""msgid ""
msgstr ""
"Project-Id-Version: ccBitTorrent 0.1.0\\n"
"Report-Msgid-Bugs-To: \\n"
"POT-Creation-Date: 2024-01-01 00:00+0000\\n"
"PO-Revision-Date: {now}\\n"
"Last-Translator: ccBitTorrent Team\\n"
"Language-Team: {lang_team}\\n"
"Language: {lang}\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"{plural_forms}\\n"

"""

    output_lines = [header]

    for msgid, english_msgstr, raw_msgid, raw_msgstr in entries:
        if not msgid:  # Skip header
            continue

        # Translate
        translation = translate_func(msgid)

        # Format msgid (preserve original formatting for multi-line)
        if "\n" in msgid or "\\n" in raw_msgid:
            # Multi-line msgid - use raw format
            msgid_lines = raw_msgid.split("\n")
            for line in msgid_lines:
                output_lines.append(line)
        else:
            output_lines.append(f'msgid "{escape_po_string(msgid)}"')

        # Format msgstr
        if "\n" in translation:
            # Multi-line msgstr - format as single quoted string with escaped newlines
            # This matches the format used in the English .po file
            escaped_translation = escape_po_string(translation)
            output_lines.append(f'msgstr "{escaped_translation}"')
        else:
            output_lines.append(f'msgstr "{escape_po_string(translation)}"')

        output_lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))


if __name__ == "__main__":
    base_dir = Path(__file__).parent / "locales"
    english_po_path = base_dir / "en" / "LC_MESSAGES" / "ccbt.po"

    entries = parse_po_file(english_po_path)
    print(f"Parsed {len(entries)} entries")

    languages = [
        (
            "sw",
            "Swahili",
            "Swahili Translation Team",
            "Plural-Forms: nplurals=3; plural=(n==1 ? 0 : n==0 || (n!=1 && n%1000000==0) ? 1 : 2);",
            translate_swahili,
        ),
        (
            "yo",
            "Yoruba",
            "Yoruba Translation Team",
            "Plural-Forms: nplurals=2; plural=(n != 1);",
            translate_yoruba,
        ),
        (
            "ha",
            "Hausa",
            "Hausa Translation Team",
            "Plural-Forms: nplurals=2; plural=(n != 1);",
            translate_hausa,
        ),
    ]

    for lang, lang_name, lang_team, plural_forms, translate_func in languages:
        output_path = base_dir / lang / "LC_MESSAGES" / "ccbt.po"
        create_po_file(
            lang,
            lang_name,
            lang_team,
            plural_forms,
            entries,
            translate_func,
            output_path,
        )
        print(f"Created {output_path}")
