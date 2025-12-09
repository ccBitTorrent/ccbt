# btbt CLI - Référence des Commandes

**btbt** est l'interface en ligne de commande améliorée pour ccBitTorrent, offrant un contrôle complet sur les opérations de torrent, le monitoring, la configuration et les fonctionnalités avancées.

- Point d'entrée : [ccbt/cli/main.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1463)
- Défini dans : [pyproject.toml:80](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L80)
- Groupe CLI principal : [ccbt/cli/main.py:cli](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L243)

## Commandes de Base

### download

Télécharger un fichier torrent.

Implémentation : [ccbt/cli/main.py:download](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L369)

Utilisation :
```bash
uv run btbt download <torrent_file> [options]
```

Options :
- `--output <dir>` : Répertoire de sortie
- `--interactive` : Mode interactif
- `--monitor` : Mode monitoring
- `--resume` : Reprendre depuis un point de contrôle
- `--no-checkpoint` : Désactiver les points de contrôle
- `--checkpoint-dir <dir>` : Répertoire des points de contrôle
- `--files <indices...>` : Sélectionner des fichiers spécifiques à télécharger (peut être spécifié plusieurs fois, ex. `--files 0 --files 1`)
- `--file-priority <spec>` : Définir la priorité du fichier comme `file_index=priority` (ex. `0=high,1=low`). Peut être spécifié plusieurs fois.

Options réseau (voir [ccbt/cli/main.py:_apply_network_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L67)) :
- `--listen-port <int>` : Port d'écoute
- `--max-peers <int>` : Nombre maximum de pairs globaux
- `--max-peers-per-torrent <int>` : Nombre maximum de pairs par torrent
- `--pipeline-depth <int>` : Profondeur du pipeline de requêtes
- `--block-size-kib <int>` : Taille de bloc en KiB
- `--connection-timeout <float>` : Délai d'attente de connexion
- `--global-down-kib <int>` : Limite globale de téléchargement (KiB/s)
- `--global-up-kib <int>` : Limite globale de téléversement (KiB/s)

Options disque (voir [ccbt/cli/main.py:_apply_disk_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L179)) :
- `--hash-workers <int>` : Nombre de workers de vérification de hash
- `--disk-workers <int>` : Nombre de workers d'E/S disque
- `--use-mmap` : Activer le mappage mémoire
- `--no-mmap` : Désactiver le mappage mémoire
- `--write-batch-kib <int>` : Taille de lot d'écriture en KiB
- `--write-buffer-kib <int>` : Taille du tampon d'écriture en KiB
- `--preallocate <str>` : Stratégie de préallocation (none|sparse|full)

Options de stratégie (voir [ccbt/cli/main.py:_apply_strategy_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L151)) :
- `--piece-selection <str>` : Stratégie de sélection de pièces (round_robin|rarest_first|sequential)
- `--endgame-duplicates <int>` : Demandes dupliquées en fin de partie
- `--endgame-threshold <float>` : Seuil de fin de partie
- `--streaming` : Activer le mode streaming

Options de découverte (voir [ccbt/cli/main.py:_apply_discovery_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L123)) :
- `--enable-dht` : Activer DHT
- `--disable-dht` : Désactiver DHT
- `--enable-pex` : Activer PEX
- `--disable-pex` : Désactiver PEX
- `--enable-http-trackers` : Activer les trackers HTTP
- `--disable-http-trackers` : Désactiver les trackers HTTP
- `--enable-udp-trackers` : Activer les trackers UDP
- `--disable-udp-trackers` : Désactiver les trackers UDP

Options d'observabilité (voir [ccbt/cli/main.py:_apply_observability_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L217)) :
- `--log-level <str>` : Niveau de journalisation (DEBUG|INFO|WARNING|ERROR|CRITICAL)
- `--log-file <path>` : Chemin du fichier de journalisation
- `--enable-metrics` : Activer la collecte de métriques
- `--disable-metrics` : Désactiver la collecte de métriques
- `--metrics-port <int>` : Port des métriques

### magnet

Télécharger depuis un lien magnet.

Implémentation : [ccbt/cli/main.py:magnet](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L608)

Utilisation :
```bash
uv run btbt magnet <magnet_link> [options]
```

Options : Identiques à la commande `download`.

### interactive

Démarrer le mode CLI interactif.

Implémentation : [ccbt/cli/main.py:interactive](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L767)

Utilisation :
```bash
uv run btbt interactive
```

CLI interactif : [ccbt/cli/interactive.py:InteractiveCLI](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/interactive.py#L41)

### status

Afficher le statut de la session actuelle.

Implémentation : [ccbt/cli/main.py:status](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L789)

Utilisation :
```bash
uv run btbt status
```

## Commandes de Point de Contrôle

Groupe de gestion des points de contrôle : [ccbt/cli/main.py:checkpoints](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L849)

### checkpoints list

Lister tous les points de contrôle disponibles.

Implémentation : [ccbt/cli/main.py:list_checkpoints](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L863)

Utilisation :
```bash
uv run btbt checkpoints list [--format json|table]
```

### checkpoints clean

Nettoyer les anciens points de contrôle.

Implémentation : [ccbt/cli/main.py:clean_checkpoints](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L930)

Utilisation :
```bash
uv run btbt checkpoints clean [--days <n>] [--dry-run]
```

### checkpoints delete

Supprimer un point de contrôle spécifique.

Implémentation : [ccbt/cli/main.py:delete_checkpoint](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L978)

Utilisation :
```bash
uv run btbt checkpoints delete <info_hash>
```

### checkpoints verify

Vérifier un point de contrôle.

Implémentation : [ccbt/cli/main.py:verify_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1016)

Utilisation :
```bash
uv run btbt checkpoints verify <info_hash>
```

### checkpoints export

Exporter un point de contrôle vers un fichier.

Implémentation : [ccbt/cli/main.py:export_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1058)

Utilisation :
```bash
uv run btbt checkpoints export <info_hash> [--format json|binary] [--output <path>]
```

### checkpoints backup

Sauvegarder un point de contrôle vers un emplacement.

Implémentation : [ccbt/cli/main.py:backup_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1099)

Utilisation :
```bash
uv run btbt checkpoints backup <info_hash> <destination> [--compress] [--encrypt]
```

### checkpoints restore

Restaurer un point de contrôle depuis une sauvegarde.

Implémentation : [ccbt/cli/main.py:restore_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1138)

Utilisation :
```bash
uv run btbt checkpoints restore <backup_file> [--info-hash <hash>]
```

### checkpoints migrate

Migrer un point de contrôle entre formats.

Implémentation : [ccbt/cli/main.py:migrate_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1173)

Utilisation :
```bash
uv run btbt checkpoints migrate <info_hash> --from <format> --to <format>
```

### resume

Reprendre le téléchargement depuis un point de contrôle.

Implémentation : [ccbt/cli/main.py:resume](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1204)

Utilisation :
```bash
uv run btbt resume <info_hash> [--output <dir>] [--interactive]
```

## Commandes de Monitoring

Groupe de commandes de monitoring : [ccbt/cli/monitoring_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py)

### dashboard

Démarrer le tableau de bord de monitoring terminal (Bitonic).

Implémentation : [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L20)

Utilisation :
```bash
uv run btbt dashboard [--refresh <seconds>] [--rules <path>]
```

Voir le [Guide Bitonic](bitonic.md) pour une utilisation détaillée.

### alerts

Gérer les règles d'alerte et les alertes actives.

Implémentation : [ccbt/cli/monitoring_commands.py:alerts](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L48)

Utilisation :
```bash
# Lister les règles d'alerte
uv run btbt alerts --list

# Lister les alertes actives
uv run btbt alerts --list-active

# Ajouter une règle d'alerte
uv run btbt alerts --add --name <name> --metric <metric> --condition "<condition>" --severity <severity>

# Supprimer une règle d'alerte
uv run btbt alerts --remove --name <name>

# Effacer toutes les alertes actives
uv run btbt alerts --clear-active

# Tester une règle d'alerte
uv run btbt alerts --test --name <name> --value <value>

# Charger les règles depuis un fichier
uv run btbt alerts --load <path>

# Sauvegarder les règles vers un fichier
uv run btbt alerts --save <path>
```

Voir la [Référence API](API.md#monitoring) pour plus d'informations.

### metrics

Collecter et exporter les métriques.

Implémentation : [ccbt/cli/monitoring_commands.py:metrics](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L229)

Utilisation :
```bash
uv run btbt metrics [--format json|prometheus] [--output <path>] [--duration <seconds>] [--interval <seconds>] [--include-system] [--include-performance]
```

Exemples :
```bash
# Exporter les métriques JSON
uv run btbt metrics --format json --include-system --include-performance

# Exporter au format Prometheus
uv run btbt metrics --format prometheus > metrics.txt
```

Voir la [Référence API](API.md#monitoring) pour plus d'informations.

## Commandes de Sélection de Fichiers

Groupe de commandes de sélection de fichiers : [ccbt/cli/file_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py)

Gérer la sélection de fichiers et les priorités pour les torrents multi-fichiers.

### files list

Lister tous les fichiers d'un torrent avec leur statut de sélection, leurs priorités et leur progression de téléchargement.

Implémentation : [ccbt/cli/file_commands.py:files_list](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L28)

Utilisation :
```bash
uv run btbt files list <info_hash>
```

La sortie inclut :
- Index et nom du fichier
- Taille du fichier
- Statut de sélection (sélectionné/désélectionné)
- Niveau de priorité
- Progression du téléchargement

### files select

Sélectionner un ou plusieurs fichiers pour le téléchargement.

Implémentation : [ccbt/cli/file_commands.py:files_select](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L72)

Utilisation :
```bash
uv run btbt files select <info_hash> <file_index> [<file_index> ...]
```

Exemples :
```bash
# Sélectionner les fichiers 0, 2 et 5
uv run btbt files select abc123... 0 2 5

# Sélectionner un seul fichier
uv run btbt files select abc123... 0
```

### files deselect

Désélectionner un ou plusieurs fichiers du téléchargement.

Implémentation : [ccbt/cli/file_commands.py:files_deselect](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L108)

Utilisation :
```bash
uv run btbt files deselect <info_hash> <file_index> [<file_index> ...]
```

### files select-all

Sélectionner tous les fichiers du torrent.

Implémentation : [ccbt/cli/file_commands.py:files_select_all](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L144)

Utilisation :
```bash
uv run btbt files select-all <info_hash>
```

### files deselect-all

Désélectionner tous les fichiers du torrent.

Implémentation : [ccbt/cli/file_commands.py:files_deselect_all](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L161)

Utilisation :
```bash
uv run btbt files deselect-all <info_hash>
```

### files priority

Définir la priorité d'un fichier spécifique.

Implémentation : [ccbt/cli/file_commands.py:files_priority](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L178)

Utilisation :
```bash
uv run btbt files priority <info_hash> <file_index> <priority>
```

Niveaux de priorité :
- `do_not_download` : Ne pas télécharger (équivalent à désélectionné)
- `low` : Priorité faible
- `normal` : Priorité normale (par défaut)
- `high` : Priorité élevée
- `maximum` : Priorité maximale

Exemples :
```bash
# Définir le fichier 0 à priorité élevée
uv run btbt files priority abc123... 0 high

# Définir le fichier 2 à priorité maximale
uv run btbt files priority abc123... 2 maximum
```

## Commandes de Configuration

Groupe de commandes de configuration : [ccbt/cli/config_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/config_commands.py)

### config

Gérer la configuration.

Implémentation : [ccbt/cli/main.py:config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L810)

Utilisation :
```bash
uv run btbt config [subcommand]
```

Commandes de configuration étendues : [ccbt/cli/config_commands_extended.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/config_commands_extended.py)

Voir le [Guide de Configuration](configuration.md) pour les options de configuration détaillées.

## Commandes Avancées

Groupe de commandes avancées : [ccbt/cli/advanced_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py)

### performance

Analyse de performance et benchmarking.

Implémentation : [ccbt/cli/advanced_commands.py:performance](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L73)

Utilisation :
```bash
uv run btbt performance [--analyze] [--benchmark]
```

### security

Analyse et validation de sécurité.

Implémentation : [ccbt/cli/advanced_commands.py:security](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L170)

Utilisation :
```bash
uv run btbt security [options]
```

### recover

Opérations de récupération.

Implémentation : [ccbt/cli/advanced_commands.py:recover](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L209)

Utilisation :
```bash
uv run btbt recover [options]
```

### test

Exécuter des tests et diagnostics.

Implémentation : [ccbt/cli/advanced_commands.py:test](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L248)

Utilisation :
```bash
uv run btbt test [options]
```

## Options de Ligne de Commande

### Options Globales

Options globales définies dans : [ccbt/cli/main.py:cli](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L243)

- `--config <path>` : Chemin du fichier de configuration
- `--verbose` : Sortie verbeuse
- `--debug` : Mode debug

### Surcharges CLI

Toutes les options CLI surchargent la configuration dans cet ordre :
1. Valeurs par défaut de [ccbt/config/config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)
2. Fichier de configuration ([ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml))
3. Variables d'environnement ([env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example))
4. Arguments CLI

Implémentation de la surcharge : [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L55)

## Exemples

### Téléchargement de Base
```bash
uv run btbt download movie.torrent
```

### Téléchargement avec Options
```bash
uv run btbt download movie.torrent \
  --listen-port 7001 \
  --enable-dht \
  --use-mmap \
  --download-limit 1024 \
  --upload-limit 512
```

### Téléchargement Sélectif de Fichiers
```bash
# Télécharger uniquement des fichiers spécifiques
uv run btbt download torrent.torrent --files 0 --files 2 --files 5

# Télécharger avec priorités de fichiers
uv run btbt download torrent.torrent \
  --file-priority 0=high \
  --file-priority 1=maximum \
  --file-priority 2=low

# Combiné : sélectionner des fichiers et définir des priorités
uv run btbt download torrent.torrent \
  --files 0 1 2 \
  --file-priority 0=maximum \
  --file-priority 1=high
```

### Téléchargement depuis Magnet
```bash
uv run btbt magnet "magnet:?xt=urn:btih:..." \
  --download-limit 1024 \
  --upload-limit 256
```

### Gestion de Sélection de Fichiers
```bash
# Lister les fichiers d'un torrent
uv run btbt files list abc123def456789...

# Sélectionner des fichiers spécifiques après le début du téléchargement
uv run btbt files select abc123... 3 4

# Définir les priorités de fichiers
uv run btbt files priority abc123... 0 high
uv run btbt files priority abc123... 2 maximum

# Sélectionner/désélectionner tous les fichiers
uv run btbt files select-all abc123...
uv run btbt files deselect-all abc123...
```

### Gestion des Points de Contrôle
```bash
# Lister les points de contrôle
uv run btbt checkpoints list --format json

# Exporter un point de contrôle
uv run btbt checkpoints export <infohash> --format json --output checkpoint.json

# Nettoyer les anciens points de contrôle
uv run btbt checkpoints clean --days 7
```

### Configuration par Torrent

Gérer les options de configuration et les limites de débit par torrent. Ces paramètres sont persistés dans les points de contrôle et l'état du daemon.

Implémentation : [ccbt/cli/torrent_config_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/torrent_config_commands.py)

#### Définir une Option par Torrent

Définir une option de configuration pour un torrent spécifique :

```bash
uv run btbt torrent config set <info_hash> <key> <value> [--save-checkpoint]
```

Exemples :
```bash
# Définir la stratégie de sélection de pièces
uv run btbt torrent config set abc123... piece_selection sequential

# Activer le mode streaming
uv run btbt torrent config set abc123... streaming_mode true

# Définir le nombre maximum de pairs par torrent
uv run btbt torrent config set abc123... max_peers_per_torrent 50

# Définir une option et sauvegarder le point de contrôle immédiatement
uv run btbt torrent config set abc123... piece_selection rarest_first --save-checkpoint
```

#### Obtenir une Option par Torrent

Obtenir la valeur d'une option de configuration pour un torrent spécifique :

```bash
uv run btbt torrent config get <info_hash> <key>
```

Exemple :
```bash
uv run btbt torrent config get abc123... piece_selection
```

#### Lister Toute la Configuration par Torrent

Lister toutes les options de configuration et limites de débit pour un torrent :

```bash
uv run btbt torrent config list <info_hash>
```

Exemple :
```bash
uv run btbt torrent config list abc123...
```

La sortie affiche :
- Toutes les options par torrent (piece_selection, streaming_mode, etc.)
- Limites de débit (téléchargement/téléversement en KiB/s)

#### Réinitialiser la Configuration par Torrent

Réinitialiser les options de configuration pour un torrent :

```bash
uv run btbt torrent config reset <info_hash> [--key <key>]
```

Exemples :
```bash
# Réinitialiser toutes les options par torrent
uv run btbt torrent config reset abc123...

# Réinitialiser une option spécifique
uv run btbt torrent config reset abc123... --key piece_selection
```

**Note** : Les options de configuration par torrent sont automatiquement sauvegardées dans les points de contrôle lors de leur création. Utilisez `--save-checkpoint` avec `set` pour persister immédiatement les modifications. Ces paramètres sont également persistés dans l'état du daemon lors de l'exécution en mode daemon.

### Monitoring
```bash
# Démarrer le tableau de bord
uv run btbt dashboard --refresh 2.0

# Ajouter une règle d'alerte
uv run btbt alerts --add --name cpu_high --metric system.cpu --condition "value > 80" --severity warning

# Exporter les métriques
uv run btbt metrics --format json --include-system --include-performance
```

## Obtenir de l'Aide

Obtenir de l'aide pour n'importe quelle commande :
```bash
uv run btbt --help
uv run btbt <command> --help
```

Pour plus d'informations :
- [Guide Bitonic](bitonic.md) - Tableau de bord terminal
- [Guide de Configuration](configuration.md) - Options de configuration
- [Référence API](API.md#monitoring) - Monitoring et métriques
- [Optimisation des Performances](performance.md) - Guide d'optimisation




**btbt** est l'interface en ligne de commande améliorée pour ccBitTorrent, offrant un contrôle complet sur les opérations de torrent, le monitoring, la configuration et les fonctionnalités avancées.

- Point d'entrée : [ccbt/cli/main.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1463)
- Défini dans : [pyproject.toml:80](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L80)
- Groupe CLI principal : [ccbt/cli/main.py:cli](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L243)

## Commandes de Base

### download

Télécharger un fichier torrent.

Implémentation : [ccbt/cli/main.py:download](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L369)

Utilisation :
```bash
uv run btbt download <torrent_file> [options]
```

Options :
- `--output <dir>` : Répertoire de sortie
- `--interactive` : Mode interactif
- `--monitor` : Mode monitoring
- `--resume` : Reprendre depuis un point de contrôle
- `--no-checkpoint` : Désactiver les points de contrôle
- `--checkpoint-dir <dir>` : Répertoire des points de contrôle
- `--files <indices...>` : Sélectionner des fichiers spécifiques à télécharger (peut être spécifié plusieurs fois, ex. `--files 0 --files 1`)
- `--file-priority <spec>` : Définir la priorité du fichier comme `file_index=priority` (ex. `0=high,1=low`). Peut être spécifié plusieurs fois.

Options réseau (voir [ccbt/cli/main.py:_apply_network_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L67)) :
- `--listen-port <int>` : Port d'écoute
- `--max-peers <int>` : Nombre maximum de pairs globaux
- `--max-peers-per-torrent <int>` : Nombre maximum de pairs par torrent
- `--pipeline-depth <int>` : Profondeur du pipeline de requêtes
- `--block-size-kib <int>` : Taille de bloc en KiB
- `--connection-timeout <float>` : Délai d'attente de connexion
- `--global-down-kib <int>` : Limite globale de téléchargement (KiB/s)
- `--global-up-kib <int>` : Limite globale de téléversement (KiB/s)

Options disque (voir [ccbt/cli/main.py:_apply_disk_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L179)) :
- `--hash-workers <int>` : Nombre de workers de vérification de hash
- `--disk-workers <int>` : Nombre de workers d'E/S disque
- `--use-mmap` : Activer le mappage mémoire
- `--no-mmap` : Désactiver le mappage mémoire
- `--write-batch-kib <int>` : Taille de lot d'écriture en KiB
- `--write-buffer-kib <int>` : Taille du tampon d'écriture en KiB
- `--preallocate <str>` : Stratégie de préallocation (none|sparse|full)

Options de stratégie (voir [ccbt/cli/main.py:_apply_strategy_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L151)) :
- `--piece-selection <str>` : Stratégie de sélection de pièces (round_robin|rarest_first|sequential)
- `--endgame-duplicates <int>` : Demandes dupliquées en fin de partie
- `--endgame-threshold <float>` : Seuil de fin de partie
- `--streaming` : Activer le mode streaming

Options de découverte (voir [ccbt/cli/main.py:_apply_discovery_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L123)) :
- `--enable-dht` : Activer DHT
- `--disable-dht` : Désactiver DHT
- `--enable-pex` : Activer PEX
- `--disable-pex` : Désactiver PEX
- `--enable-http-trackers` : Activer les trackers HTTP
- `--disable-http-trackers` : Désactiver les trackers HTTP
- `--enable-udp-trackers` : Activer les trackers UDP
- `--disable-udp-trackers` : Désactiver les trackers UDP

Options d'observabilité (voir [ccbt/cli/main.py:_apply_observability_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L217)) :
- `--log-level <str>` : Niveau de journalisation (DEBUG|INFO|WARNING|ERROR|CRITICAL)
- `--log-file <path>` : Chemin du fichier de journalisation
- `--enable-metrics` : Activer la collecte de métriques
- `--disable-metrics` : Désactiver la collecte de métriques
- `--metrics-port <int>` : Port des métriques

### magnet

Télécharger depuis un lien magnet.

Implémentation : [ccbt/cli/main.py:magnet](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L608)

Utilisation :
```bash
uv run btbt magnet <magnet_link> [options]
```

Options : Identiques à la commande `download`.

### interactive

Démarrer le mode CLI interactif.

Implémentation : [ccbt/cli/main.py:interactive](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L767)

Utilisation :
```bash
uv run btbt interactive
```

CLI interactif : [ccbt/cli/interactive.py:InteractiveCLI](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/interactive.py#L41)

### status

Afficher le statut de la session actuelle.

Implémentation : [ccbt/cli/main.py:status](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L789)

Utilisation :
```bash
uv run btbt status
```

## Commandes de Point de Contrôle

Groupe de gestion des points de contrôle : [ccbt/cli/main.py:checkpoints](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L849)

### checkpoints list

Lister tous les points de contrôle disponibles.

Implémentation : [ccbt/cli/main.py:list_checkpoints](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L863)

Utilisation :
```bash
uv run btbt checkpoints list [--format json|table]
```

### checkpoints clean

Nettoyer les anciens points de contrôle.

Implémentation : [ccbt/cli/main.py:clean_checkpoints](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L930)

Utilisation :
```bash
uv run btbt checkpoints clean [--days <n>] [--dry-run]
```

### checkpoints delete

Supprimer un point de contrôle spécifique.

Implémentation : [ccbt/cli/main.py:delete_checkpoint](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L978)

Utilisation :
```bash
uv run btbt checkpoints delete <info_hash>
```

### checkpoints verify

Vérifier un point de contrôle.

Implémentation : [ccbt/cli/main.py:verify_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1016)

Utilisation :
```bash
uv run btbt checkpoints verify <info_hash>
```

### checkpoints export

Exporter un point de contrôle vers un fichier.

Implémentation : [ccbt/cli/main.py:export_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1058)

Utilisation :
```bash
uv run btbt checkpoints export <info_hash> [--format json|binary] [--output <path>]
```

### checkpoints backup

Sauvegarder un point de contrôle vers un emplacement.

Implémentation : [ccbt/cli/main.py:backup_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1099)

Utilisation :
```bash
uv run btbt checkpoints backup <info_hash> <destination> [--compress] [--encrypt]
```

### checkpoints restore

Restaurer un point de contrôle depuis une sauvegarde.

Implémentation : [ccbt/cli/main.py:restore_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1138)

Utilisation :
```bash
uv run btbt checkpoints restore <backup_file> [--info-hash <hash>]
```

### checkpoints migrate

Migrer un point de contrôle entre formats.

Implémentation : [ccbt/cli/main.py:migrate_checkpoint_cmd](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1173)

Utilisation :
```bash
uv run btbt checkpoints migrate <info_hash> --from <format> --to <format>
```

### resume

Reprendre le téléchargement depuis un point de contrôle.

Implémentation : [ccbt/cli/main.py:resume](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1204)

Utilisation :
```bash
uv run btbt resume <info_hash> [--output <dir>] [--interactive]
```

## Commandes de Monitoring

Groupe de commandes de monitoring : [ccbt/cli/monitoring_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py)

### dashboard

Démarrer le tableau de bord de monitoring terminal (Bitonic).

Implémentation : [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L20)

Utilisation :
```bash
uv run btbt dashboard [--refresh <seconds>] [--rules <path>]
```

Voir le [Guide Bitonic](bitonic.md) pour une utilisation détaillée.

### alerts

Gérer les règles d'alerte et les alertes actives.

Implémentation : [ccbt/cli/monitoring_commands.py:alerts](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L48)

Utilisation :
```bash
# Lister les règles d'alerte
uv run btbt alerts --list

# Lister les alertes actives
uv run btbt alerts --list-active

# Ajouter une règle d'alerte
uv run btbt alerts --add --name <name> --metric <metric> --condition "<condition>" --severity <severity>

# Supprimer une règle d'alerte
uv run btbt alerts --remove --name <name>

# Effacer toutes les alertes actives
uv run btbt alerts --clear-active

# Tester une règle d'alerte
uv run btbt alerts --test --name <name> --value <value>

# Charger les règles depuis un fichier
uv run btbt alerts --load <path>

# Sauvegarder les règles vers un fichier
uv run btbt alerts --save <path>
```

Voir la [Référence API](API.md#monitoring) pour plus d'informations.

### metrics

Collecter et exporter les métriques.

Implémentation : [ccbt/cli/monitoring_commands.py:metrics](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L229)

Utilisation :
```bash
uv run btbt metrics [--format json|prometheus] [--output <path>] [--duration <seconds>] [--interval <seconds>] [--include-system] [--include-performance]
```

Exemples :
```bash
# Exporter les métriques JSON
uv run btbt metrics --format json --include-system --include-performance

# Exporter au format Prometheus
uv run btbt metrics --format prometheus > metrics.txt
```

Voir la [Référence API](API.md#monitoring) pour plus d'informations.

## Commandes de Sélection de Fichiers

Groupe de commandes de sélection de fichiers : [ccbt/cli/file_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py)

Gérer la sélection de fichiers et les priorités pour les torrents multi-fichiers.

### files list

Lister tous les fichiers d'un torrent avec leur statut de sélection, leurs priorités et leur progression de téléchargement.

Implémentation : [ccbt/cli/file_commands.py:files_list](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L28)

Utilisation :
```bash
uv run btbt files list <info_hash>
```

La sortie inclut :
- Index et nom du fichier
- Taille du fichier
- Statut de sélection (sélectionné/désélectionné)
- Niveau de priorité
- Progression du téléchargement

### files select

Sélectionner un ou plusieurs fichiers pour le téléchargement.

Implémentation : [ccbt/cli/file_commands.py:files_select](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L72)

Utilisation :
```bash
uv run btbt files select <info_hash> <file_index> [<file_index> ...]
```

Exemples :
```bash
# Sélectionner les fichiers 0, 2 et 5
uv run btbt files select abc123... 0 2 5

# Sélectionner un seul fichier
uv run btbt files select abc123... 0
```

### files deselect

Désélectionner un ou plusieurs fichiers du téléchargement.

Implémentation : [ccbt/cli/file_commands.py:files_deselect](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L108)

Utilisation :
```bash
uv run btbt files deselect <info_hash> <file_index> [<file_index> ...]
```

### files select-all

Sélectionner tous les fichiers du torrent.

Implémentation : [ccbt/cli/file_commands.py:files_select_all](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L144)

Utilisation :
```bash
uv run btbt files select-all <info_hash>
```

### files deselect-all

Désélectionner tous les fichiers du torrent.

Implémentation : [ccbt/cli/file_commands.py:files_deselect_all](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L161)

Utilisation :
```bash
uv run btbt files deselect-all <info_hash>
```

### files priority

Définir la priorité d'un fichier spécifique.

Implémentation : [ccbt/cli/file_commands.py:files_priority](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/file_commands.py#L178)

Utilisation :
```bash
uv run btbt files priority <info_hash> <file_index> <priority>
```

Niveaux de priorité :
- `do_not_download` : Ne pas télécharger (équivalent à désélectionné)
- `low` : Priorité faible
- `normal` : Priorité normale (par défaut)
- `high` : Priorité élevée
- `maximum` : Priorité maximale

Exemples :
```bash
# Définir le fichier 0 à priorité élevée
uv run btbt files priority abc123... 0 high

# Définir le fichier 2 à priorité maximale
uv run btbt files priority abc123... 2 maximum
```

## Commandes de Configuration

Groupe de commandes de configuration : [ccbt/cli/config_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/config_commands.py)

### config

Gérer la configuration.

Implémentation : [ccbt/cli/main.py:config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L810)

Utilisation :
```bash
uv run btbt config [subcommand]
```

Commandes de configuration étendues : [ccbt/cli/config_commands_extended.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/config_commands_extended.py)

Voir le [Guide de Configuration](configuration.md) pour les options de configuration détaillées.

## Commandes Avancées

Groupe de commandes avancées : [ccbt/cli/advanced_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py)

### performance

Analyse de performance et benchmarking.

Implémentation : [ccbt/cli/advanced_commands.py:performance](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L73)

Utilisation :
```bash
uv run btbt performance [--analyze] [--benchmark]
```

### security

Analyse et validation de sécurité.

Implémentation : [ccbt/cli/advanced_commands.py:security](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L170)

Utilisation :
```bash
uv run btbt security [options]
```

### recover

Opérations de récupération.

Implémentation : [ccbt/cli/advanced_commands.py:recover](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L209)

Utilisation :
```bash
uv run btbt recover [options]
```

### test

Exécuter des tests et diagnostics.

Implémentation : [ccbt/cli/advanced_commands.py:test](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/advanced_commands.py#L248)

Utilisation :
```bash
uv run btbt test [options]
```

## Options de Ligne de Commande

### Options Globales

Options globales définies dans : [ccbt/cli/main.py:cli](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L243)

- `--config <path>` : Chemin du fichier de configuration
- `--verbose` : Sortie verbeuse
- `--debug` : Mode debug

### Surcharges CLI

Toutes les options CLI surchargent la configuration dans cet ordre :
1. Valeurs par défaut de [ccbt/config/config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)
2. Fichier de configuration ([ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml))
3. Variables d'environnement ([env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example))
4. Arguments CLI

Implémentation de la surcharge : [ccbt/cli/main.py:_apply_cli_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L55)

## Exemples

### Téléchargement de Base
```bash
uv run btbt download movie.torrent
```

### Téléchargement avec Options
```bash
uv run btbt download movie.torrent \
  --listen-port 7001 \
  --enable-dht \
  --use-mmap \
  --download-limit 1024 \
  --upload-limit 512
```

### Téléchargement Sélectif de Fichiers
```bash
# Télécharger uniquement des fichiers spécifiques
uv run btbt download torrent.torrent --files 0 --files 2 --files 5

# Télécharger avec priorités de fichiers
uv run btbt download torrent.torrent \
  --file-priority 0=high \
  --file-priority 1=maximum \
  --file-priority 2=low

# Combiné : sélectionner des fichiers et définir des priorités
uv run btbt download torrent.torrent \
  --files 0 1 2 \
  --file-priority 0=maximum \
  --file-priority 1=high
```

### Téléchargement depuis Magnet
```bash
uv run btbt magnet "magnet:?xt=urn:btih:..." \
  --download-limit 1024 \
  --upload-limit 256
```

### Gestion de Sélection de Fichiers
```bash
# Lister les fichiers d'un torrent
uv run btbt files list abc123def456789...

# Sélectionner des fichiers spécifiques après le début du téléchargement
uv run btbt files select abc123... 3 4

# Définir les priorités de fichiers
uv run btbt files priority abc123... 0 high
uv run btbt files priority abc123... 2 maximum

# Sélectionner/désélectionner tous les fichiers
uv run btbt files select-all abc123...
uv run btbt files deselect-all abc123...
```

### Gestion des Points de Contrôle
```bash
# Lister les points de contrôle
uv run btbt checkpoints list --format json

# Exporter un point de contrôle
uv run btbt checkpoints export <infohash> --format json --output checkpoint.json

# Nettoyer les anciens points de contrôle
uv run btbt checkpoints clean --days 7
```

### Configuration par Torrent

Gérer les options de configuration et les limites de débit par torrent. Ces paramètres sont persistés dans les points de contrôle et l'état du daemon.

Implémentation : [ccbt/cli/torrent_config_commands.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/torrent_config_commands.py)

#### Définir une Option par Torrent

Définir une option de configuration pour un torrent spécifique :

```bash
uv run btbt torrent config set <info_hash> <key> <value> [--save-checkpoint]
```

Exemples :
```bash
# Définir la stratégie de sélection de pièces
uv run btbt torrent config set abc123... piece_selection sequential

# Activer le mode streaming
uv run btbt torrent config set abc123... streaming_mode true

# Définir le nombre maximum de pairs par torrent
uv run btbt torrent config set abc123... max_peers_per_torrent 50

# Définir une option et sauvegarder le point de contrôle immédiatement
uv run btbt torrent config set abc123... piece_selection rarest_first --save-checkpoint
```

#### Obtenir une Option par Torrent

Obtenir la valeur d'une option de configuration pour un torrent spécifique :

```bash
uv run btbt torrent config get <info_hash> <key>
```

Exemple :
```bash
uv run btbt torrent config get abc123... piece_selection
```

#### Lister Toute la Configuration par Torrent

Lister toutes les options de configuration et limites de débit pour un torrent :

```bash
uv run btbt torrent config list <info_hash>
```

Exemple :
```bash
uv run btbt torrent config list abc123...
```

La sortie affiche :
- Toutes les options par torrent (piece_selection, streaming_mode, etc.)
- Limites de débit (téléchargement/téléversement en KiB/s)

#### Réinitialiser la Configuration par Torrent

Réinitialiser les options de configuration pour un torrent :

```bash
uv run btbt torrent config reset <info_hash> [--key <key>]
```

Exemples :
```bash
# Réinitialiser toutes les options par torrent
uv run btbt torrent config reset abc123...

# Réinitialiser une option spécifique
uv run btbt torrent config reset abc123... --key piece_selection
```

**Note** : Les options de configuration par torrent sont automatiquement sauvegardées dans les points de contrôle lors de leur création. Utilisez `--save-checkpoint` avec `set` pour persister immédiatement les modifications. Ces paramètres sont également persistés dans l'état du daemon lors de l'exécution en mode daemon.

### Monitoring
```bash
# Démarrer le tableau de bord
uv run btbt dashboard --refresh 2.0

# Ajouter une règle d'alerte
uv run btbt alerts --add --name cpu_high --metric system.cpu --condition "value > 80" --severity warning

# Exporter les métriques
uv run btbt metrics --format json --include-system --include-performance
```

## Obtenir de l'Aide

Obtenir de l'aide pour n'importe quelle commande :
```bash
uv run btbt --help
uv run btbt <command> --help
```

Pour plus d'informations :
- [Guide Bitonic](bitonic.md) - Tableau de bord terminal
- [Guide de Configuration](configuration.md) - Options de configuration
- [Référence API](API.md#monitoring) - Monitoring et métriques
- [Optimisation des Performances](performance.md) - Guide d'optimisation


























































































































































































