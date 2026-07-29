# Exemples

Cette section fournit des exemples pratiques et des échantillons de code pour utiliser ccBitTorrent.

## Exemples de Configuration

### Configuration de Base

Un fichier de configuration minimal pour démarrer :

```toml
[disk]
download_dir = "./downloads"
checkpoint_dir = "./checkpoints"
```

Consultez [example-config-basic.toml](examples/example-config-basic.toml) pour une configuration de base complète.

### Configuration Avancée

Pour les utilisateurs avancés qui ont besoin d'un contrôle précis :

Consultez [example-config-advanced.toml](examples/example-config-advanced.toml) pour les options de configuration avancées.

### Configuration de Performance

Paramètres optimisés pour des performances maximales :

Consultez [example-config-performance.toml](examples/example-config-performance.toml) pour le réglage des performances.

### Configuration de Sécurité

Configuration axée sur la sécurité avec chiffrement et validation :

Consultez [example-config-security.toml](examples/example-config-security.toml) pour les paramètres de sécurité.

## Exemples BEP 52

### Créer un Torrent v2

Créer un fichier torrent BitTorrent v2 :

```python
from ccbt.core.torrent_v2 import create_v2_torrent

# Créer un torrent v2
create_v2_torrent(
    source_dir="./my_files",
    output_file="./my_torrent.torrent",
    piece_length=16384  # Pièces de 16KB
)
```

Consultez [create_v2_torrent.py](examples/bep52/create_v2_torrent.py) pour un exemple complet.

### Créer un Torrent Hybride

Créer un torrent hybride qui fonctionne avec les clients v1 et v2 :

Consultez [create_hybrid_torrent.py](examples/bep52/create_hybrid_torrent.py) pour un exemple complet.

### Analyser un Torrent v2

Analyser et inspecter un fichier torrent BitTorrent v2 :

Consultez [parse_v2_torrent.py](examples/bep52/parse_v2_torrent.py) pour un exemple complet.

### Session de Protocole v2

Utiliser le protocole BitTorrent v2 dans une session :

Consultez [protocol_v2_session.py](examples/bep52/protocol_v2_session.py) pour un exemple complet.

## Démarrage

Pour plus d'informations sur le démarrage avec ccBitTorrent, consultez le [Guide de Démarrage](getting-started.md).


