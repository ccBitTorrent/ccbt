# ccBitTorrent - Client BitTorrent Haute Performance

Un client BitTorrent moderne et haute performance construit avec Python asyncio, avec des algorithmes avancés de sélection de pièces, échange parallèle de métadonnées et E/S disque optimisées.

## Caractéristiques

### Optimisations de Performance
- **E/S Asynchrone**: Implémentation complète d'asyncio pour une concurrence supérieure. Voir [ccbt/session/async_main.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/async_main.py)
- **Sélection Rarest-First**: Sélection intelligente de pièces pour une santé optimale de l'essaim. Voir [ccbt/piece/async_piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py)
- **Mode Endgame**: Requêtes dupliquées pour une finalisation plus rapide
- **Pipeline de Requêtes**: Files de requêtes profondes (16-64 requêtes en attente par pair). Voir [ccbt/peer/async_peer_connection.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/async_peer_connection.py)
- **Choking Tit-for-Tat**: Allocation équitable de bande passante avec optimistic unchoke
- **Métadonnées Parallèles**: Récupération concurrente d'ut_metadata depuis plusieurs pairs. Voir [ccbt/piece/async_metadata_exchange.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_metadata_exchange.py)
- **Optimisation E/S Disque**: Préallocation de fichiers, écriture par lots, mise en mémoire tampon en anneau, E/S mappée en mémoire, io_uring/E/S directe (configurable). Voir [ccbt/storage/disk_io.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/disk_io.py)
- **Pool de Vérification de Hash**: Vérification SHA-1 parallèle sur threads de travail

### Configuration Avancée
- **Configuration TOML**: Système de configuration complet avec rechargement à chaud. Voir [ccbt/config/config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)
- **Paramètres par Torrent**: Remplacements de configuration individuels par torrent
- **Limitation de Débit**: Limites globales et par torrent de téléchargement/upload. Voir [ccbt.toml:38-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L38-L42)
- **Sélection de Stratégie**: Sélection de pièces round-robin, rarest-first ou séquentielle. Voir [ccbt.toml:100-114](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L100-L114)
- **Mode Streaming**: Sélection de pièces basée sur la priorité pour fichiers multimédias

### Fonctionnalités Réseau
- **Support Tracker UDP**: Communication tracker UDP conforme BEP 15. Voir [ccbt/discovery/tracker_udp_client.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/tracker_udp_client.py)
- **DHT Amélioré**: Table de routage Kademlia complète avec recherches itératives. Voir [ccbt/discovery/dht.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/dht.py)
- **Échange de Pairs (PEX)**: Découverte de pairs conforme BEP 11. Voir [ccbt/discovery/pex.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/pex.py)
- **Gestion de Connexions**: Sélection adaptative de pairs et limites de connexion. Voir [ccbt/peer/connection_pool.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/connection_pool.py)
- **Optimisations de Protocole**: Gestion efficace des messages en mémoire avec chemins zéro copie

## Extension de Protocole Xet (BEP XET)

L'Extension de Protocole Xet est un différenciateur clé qui transforme BitTorrent en un système de fichiers peer-to-peer rapide et actualisable optimisé pour la collaboration. BEP XET permet :

- **Découpage Défini par Contenu**: Segmentation intelligente de fichiers basée sur Gearhash (morceaux de 8KB-128KB) pour mises à jour efficaces. Voir [ccbt/storage/xet_chunking.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py)
- **Déduplication Inter-Torrents**: Déduplication au niveau des morceaux entre plusieurs torrents. Voir [ccbt/storage/xet_deduplication.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py)
- **CAS Peer-to-Peer**: Stockage Adressable par Contenu Décentralisé utilisant DHT et trackers. Voir [ccbt/discovery/xet_cas.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/xet_cas.py)
- **Mises à Jour Ultra-Rapides**: Seuls les morceaux modifiés nécessitent redistribution, permettant partage rapide de fichiers collaboratifs
- **Système de Fichiers P2P**: Transforme BitTorrent en système de fichiers peer-to-peer actualisable optimisé pour collaboration
- **Vérification Arbre Merkle**: Hachage BLAKE3-256 avec repli SHA-256 pour intégrité. Voir [ccbt/storage/xet_hashing.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py)

[En savoir plus sur BEP XET →](bep_xet.md)

### Observabilité
- **Export de Métriques**: Métriques compatibles Prometheus pour monitoring. Voir [ccbt/monitoring/metrics_collector.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/monitoring/metrics_collector.py)
- **Journalisation Structurée**: Journalisation configurable avec traçage par pair. Voir [ccbt/utils/logging_config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/logging_config.py)
- **Statistiques de Performance**: Suivi en temps réel du débit, latence et profondeur de file
- **Surveillance de Santé**: Qualité de connexion et score de fiabilité des pairs
- **Tableau de Bord Terminal**: Tableau de bord en direct basé sur Textual (Bitonic). Voir [ccbt/interface/terminal_dashboard.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py)
- **Gestionnaire d'Alertes**: Alertes basées sur règles avec persistance et tests via CLI. Voir [ccbt/monitoring/alert_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/monitoring/alert_manager.py)

## Démarrage Rapide

### Installation avec UV

Installez UV depuis [astral.sh/uv](https://astral.sh/uv), puis installez ccBitTorrent.

Référence: [pyproject.toml:79-81](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L79-L81) pour les points d'entrée

### Points d'Entrée Principaux

**Bitonic** - L'interface principale du tableau de bord terminal (recommandé):
- Point d'entrée: [ccbt/interface/terminal_dashboard.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- Défini dans: [pyproject.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L81)
- Lancer: `uv run bitonic` ou `uv run ccbt dashboard`

**btbt CLI** - Interface en ligne de commande améliorée:
- Point d'entrée: [ccbt/cli/main.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1463)
- Défini dans: [pyproject.toml:80](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L80)
- Lancer: `uv run btbt`

**ccbt** - Interface CLI de base:
- Point d'entrée: [ccbt/__main__.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/__main__.py#L18)
- Défini dans: [pyproject.toml:79](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L79)
- Lancer: `uv run ccbt`

Pour utilisation détaillée, voir:
- [Guide de Démarrage](getting-started.md) - Tutoriel étape par étape
- [Bitonic](bitonic.md) - Guide du tableau de bord terminal
- [btbt CLI](btbt-cli.md) - Référence complète des commandes

## Documentation

- [BEP XET](bep_xet.md) - Extension de Protocole Xet pour découpage défini par contenu et déduplication
- [Démarrage](getting-started.md) - Installation et premiers pas
- [Bitonic](bitonic.md) - Tableau de bord terminal (interface principale)
- [btbt CLI](btbt-cli.md) - Référence d'interface en ligne de commande
- [Configuration](configuration.md) - Options de configuration et configuration
- [Réglage de Performance](performance.md) - Guide d'optimisation
- [Référence API ccBT](API.md) - Documentation API Python
- [Contribuer](contributing.md) - Comment contribuer
- [Financement](funding.md) - Soutenir le projet

## Licence

Ce projet est sous licence **GNU General Public License v2 (GPL-2.0)** - voir [license.md](license.md) pour détails.

De plus, ce projet est soumis à des restrictions d'utilisation supplémentaires sous la **Licence ccBT RAIL-AMS** - voir [ccBT-RAIL.md](ccBT-RAIL.md) pour les termes complets et restrictions d'utilisation.

**Important**: Les deux licences s'appliquent à ce logiciel. Vous devez respecter tous les termes et restrictions à la fois dans la licence GPL-2.0 et la licence RAIL.

## Rapports

Voir les rapports du projet dans la documentation:
- [Rapports de Couverture](reports/coverage.md) - Analyse de couverture de code
- [Rapport de Sécurité Bandit](reports/bandit/index.md) - Résultats de scan de sécurité
- [Benchmarks](reports/benchmarks/index.md) - Résultats de benchmarks de performance

## Remerciements

- Spécification du protocole BitTorrent (BEP 5, 10, 11, 15, 52)
- Protocole Xet pour inspiration de découpage défini par contenu
- Python asyncio pour E/S haute performance
- La communauté BitTorrent pour le développement du protocole
