"""Add Rich markup translations to the translation dictionaries.

This script extracts all Rich markup strings and adds their translations
to the generate_african_translations.py file.
"""

from __future__ import annotations

# Rich markup translations for Swahili
SWAHILI_RICH_MARKUP = {
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
    "[red]{error}[/red]": "[red]{error}[/red]",
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
}

# Due to the large size, I'll need to add these to the main script
# Let me update the generate_african_translations.py file directly

if __name__ == "__main__":
    print("This script contains Rich markup translations.")
    print("These need to be added to generate_african_translations.py")
