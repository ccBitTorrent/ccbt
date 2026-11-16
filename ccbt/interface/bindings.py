"""Single binding registry: footer, help, navigation and palette derive from this."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class BindingSpec:
    key: str; action: str; label: str; category: str = "General"; scope: str = "app"

# key, action, label, category
_SPECS = [
    ("p","pause_torrent","Pause","Torrent Control"),("r","resume_torrent","Resume","Torrent Control"),
    ("delete","remove_torrent","Remove","Torrent Control"),("ctrl+a","force_announce_torrent","Announce","Torrent Control"),
    ("i","quick_add_torrent","Quick Add","Add Torrents"),("o","advanced_add_torrent","Advanced Add","Add Torrents"),
    ("b","browse_add_torrent","Browse","Add Torrents"),
    ("g","global_config","Global Config","Configuration"),("t","torrent_config","Torrent Config","Configuration"),
    ("s","system_resources","System Resources","Monitoring"),("m","performance_metrics","Performance","Monitoring"),
    ("n","network_quality","Network","Monitoring"),("h","historical_trends","History","Monitoring"),
    ("a","alerts_dashboard","Alerts","Monitoring"),("e","metrics_explorer","Explore","Monitoring"),
    ("x","security_scan","Security Scan","Monitoring"),
    ("ctrl+t","toggle_dark","Toggle Dark/Light","General"),("q","quit","Quit","General"),
    ("l","language_selection","Language","Settings"),("ctrl+shift+t","theme_selection","Theme","Settings"),
    ("?","help","Help","Navigation"),("ctrl+m","navigation_menu","Menu","Navigation"),
    ("ctrl+x","xet_management","Xet","Protocols"),("ctrl+f","xet_folder_sync","XET Folders","Protocols"),
    ("ctrl+i","ipfs_management","IPFS","Protocols"),("ctrl+s","ssl_config","SSL Config","Protocols"),
    ("ctrl+p","proxy_config","Proxy Config","Protocols"),("ctrl+r","scrape_results","Scrape Results","Protocols"),
    ("ctrl+n","nat_management","NAT Management","Protocols"),("ctrl+u","utp_config","uTP Config","Protocols"),
    ("ctrl+shift+d","peer_diagnostics","Peer Diagnostics","Monitoring"),
    ("ctrl+q","queue_management","Queue","Management"),("ctrl+e","security_management","Security / IP Filter","Management"),
    ("ctrl+k","checkpoints_management","Checkpoints","Management"),("ctrl+d","session_management","Session / Daemon","Management"),
    ("ctrl+shift+x","cas_hub_management","CAS / Hub","Management"),("ctrl+shift+a","torrent_advanced","Torrent Advanced","Management"),("ctrl+shift+s","xet_share","XET Share / Tonic","Protocols"),
]
BINDING_SPECS: tuple[BindingSpec, ...] = tuple(BindingSpec(k,a,l,c) for k,a,l,c in _SPECS)

def footer_bindings() -> list[tuple[str,str,str]]:
    return [(s.key, s.action, s.label) for s in BINDING_SPECS]

def bindings_by_category() -> dict[str, list[BindingSpec]]:
    out: dict[str, list[BindingSpec]] = {}
    for s in BINDING_SPECS: out.setdefault(s.category, []).append(s)
    return out

def action_names() -> set[str]:
    return {s.action for s in BINDING_SPECS}
