# Vue d'ensemble de l'Architecture

Ce document fournit une vue d'ensemble technique de l'architecture, des composants et du flux de données de ccBitTorrent.

## Points d'Entrée

ccBitTorrent fournit plusieurs points d'entrée pour différents cas d'utilisation :

1. **CLI de Base (`ccbt`)** : Interface en ligne de commande simple pour les téléchargements de torrents individuels
   - Point d'entrée : `ccbt/__main__.py:main`
   - Utilisation : `python -m ccbt torrent.torrent` ou `python -m ccbt "magnet:..."`

2. **CLI Async (`ccbt async`)** : Interface asynchrone haute performance avec gestion complète des sessions
   - Point d'entrée : `ccbt/session/async_main.py:main`
   - Prend en charge le mode daemon, plusieurs torrents et des fonctionnalités avancées

3. **CLI Amélioré (`btbt`)** : Interface en ligne de commande riche avec des fonctionnalités complètes
   - Point d'entrée : `ccbt/cli/main.py:main`
   - Fournit des commandes interactives, le monitoring et la configuration avancée

4. **Tableau de Bord Terminal (`bitonic`)** : Tableau de bord terminal interactif en direct (TUI)
   - Point d'entrée : `ccbt/interface/terminal_dashboard.py:main`
   - Visualisation en temps réel des torrents, pairs et métriques système

## Architecture du Système

```
┌─────────────────────────────────────────────────────────────────┐
│                    ccBitTorrent Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│  CLI Interface                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │   Basic     │ │ Interactive │ │  Dashboard   │              │
│  │   Commands  │ │     CLI     │ │   (TUI)     │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Session Management                                             │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              AsyncSessionManager                           │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │ │
│  │  │   Config    │ │   Events    │ │  Checkpoint │          │ │
│  │  │  Manager    │ │   System    │ │   Manager   │          │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘          │ │
│  └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  Core Components                                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │    Peer     │ │    Piece    │ │    Disk     │              │
│  │  Connection │ │   Manager   │ │     I/O     │              │
│  │  Manager    │ │             │ │   Manager   │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │   Tracker   │ │     DHT     │ │  Metadata   │              │
│  │   Client    │ │   Manager   │ │  Exchange   │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Network Layer                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │    TCP      │ │     UDP     │ │   WebRTC    │              │
│  │ Connections │ │  Trackers   │ │ (WebTorrent)│              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Monitoring & Observability                                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │   Metrics   │ │   Alerts    │ │   Tracing   │              │
│  │  Collector  │ │   Manager   │ │   Manager   │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## Composants Principaux

### Architecture Orientée Services

ccBitTorrent utilise une architecture orientée services avec plusieurs services principaux :

- **PeerService** : Gère les connexions et la communication entre pairs
  - Implémentation : `ccbt/services/peer_service.py`
  - Suit les connexions de pairs, la bande passante et les statistiques de pièces
  
- **StorageService** : Gère les opérations du système de fichiers avec des écritures fragmentées haute performance
  - Implémentation : `ccbt/services/storage_service.py`
  - Gère la création de fichiers, les opérations de lecture/écriture de données
  
- **TrackerService** : Gère la communication avec les trackers et le monitoring de santé
  - Implémentation : `ccbt/services/tracker_service.py`
  - Prend en charge les trackers HTTP et UDP avec support de scrape (BEP 48)

Tous les services héritent de la classe de base `Service` qui fournit la gestion du cycle de vie, les vérifications de santé et le suivi d'état.

**Implémentation :** `ccbt/services/base.py`

### AsyncSessionManager

L'orchestrateur central qui gère toute la session BitTorrent. Il existe deux implémentations :

1. **AsyncSessionManager dans `ccbt/session/async_main.py`** : Utilisé par le point d'entrée CLI asynchrone, gère plusieurs torrents avec support de protocole.

La classe `AsyncSessionManager` est définie dans `ccbt/session/async_main.py` à partir de la ligne 319. Les attributs d'initialisation clés incluent :

- `config` : Instance de configuration (utilise la configuration globale si non fournie)
- `torrents` : Dictionnaire mappant les IDs de torrents aux instances de `AsyncDownloadManager`
- `metrics` : Instance de `MetricsCollector` (initialisée dans `start()` si activée)
- `disk_io_manager` : Gestionnaire d'I/O disque (initialisé dans `start()`)
- `security_manager` : Gestionnaire de sécurité (initialisé dans `start()`)
- `protocol_manager` : `ProtocolManager` pour gérer plusieurs protocoles
- `protocols` : Liste des instances de protocole actives

Voir l'implémentation complète :

```python
--8<-- "ccbt/session/async_main.py:319:374"
```

2. **AsyncSessionManager dans `ccbt/session/session.py`** : Implémentation plus complète avec DHT, gestion de file d'attente, traversée NAT et support de scrape.

Le `AsyncSessionManager` plus complet dans `ccbt/session/session.py` (à partir de la ligne 1317) inclut des composants supplémentaires :

- `dht_client` : Client DHT pour la découverte de pairs
- `peer_service` : Instance de `PeerService` pour gérer les connexions de pairs
- `queue_manager` : Gestionnaire de file d'attente de torrents pour la priorisation
- `nat_manager` : Gestionnaire de traversée NAT pour le mappage de ports
- `private_torrents` : Ensemble suivant les torrents privés (BEP 27)
- `scrape_cache` : Cache pour les résultats de scrape de trackers (BEP 48)
- Tâches en arrière-plan pour le nettoyage, la collecte de métriques et le scraping périodique

Voir l'implémentation complète :

```python
--8<-- "ccbt/session/session.py:1317:1367"
```

**Responsabilités :**
- Gestion du cycle de vie des torrents
- Coordination des connexions de pairs via `PeerService`
- Gestion des protocoles (`BitTorrentProtocol`, `IPFSProtocol`)
- Allocation et limites de ressources
- Distribution d'événements via `EventBus`
- Gestion des points de contrôle
- Gestion du client DHT
- Gestion de file d'attente pour la priorisation des torrents
- Traversée NAT via `NATManager`
- Scraping de trackers (BEP 48)

#### Contrôleurs de Session (refactorisation)

Pour améliorer la maintenabilité, la logique de session est progressivement extraite dans des contrôleurs ciblés sous `ccbt/session/` :

- `models.py` : Enum `TorrentStatus` et `SessionContext`
- `types.py` : Protocoles (`DHTClientProtocol`, `TrackerClientProtocol`, `PeerManagerProtocol`, `PieceManagerProtocol`)
- `tasks.py` : `TaskSupervisor` pour la gestion des tâches en arrière-plan
- `checkpointing.py` : `CheckpointController` pour sauvegarder/charger et traitement par lots
- `discovery.py` : `DiscoveryController` pour la découverte DHT/tracker et déduplication
- `peer_events.py` : `PeerEventsBinder` pour le câblage des callbacks
- `lifecycle.py` : `LifecycleController` pour le séquencement de démarrage/pause/reprise/arrêt
- `metrics_status.py` : Aides à l'agrégation des métriques et de l'état
- `adapters.py` : `DHTAdapter` et `TrackerAdapter` pour unifier les clients concrets derrière les protocoles

### Gestionnaire de Connexions de Pairs

Gère toutes les connexions de pairs avec pipeline avancé. Le `AsyncPeerConnectionManager` gère les connexions de pairs individuelles pour une session de torrent.

**Implémentation :** `ccbt/peer/async_peer_connection.py`

**Fonctionnalités :**
- Connexions TCP asynchrones
- Pipeline de requêtes (16-64 requêtes en attente)
- Taille de bloc adaptative
- Pool de connexions
- Algorithmes de choking/unchoking
- Poignée de main du protocole BitTorrent
- Support du protocole d'extensions (Fast, PEX, DHT, WebSeed, SSL, XET)

### Gestionnaire de Pièces

Implémente des algorithmes avancés de sélection de pièces. Le `AsyncPieceManager` coordonne le téléchargement de pièces, la vérification et le suivi de complétion.

**Implémentation :** `ccbt/piece/async_piece_manager.py`

**Algorithmes :**
- **Rarest-First** : Santé optimale de l'essaim
- **Séquentiel** : Pour les médias en streaming
- **Round-Robin** : Fallback simple
- **Mode Endgame** : Requêtes dupliquées pour la complétion
- Support de sélection de fichiers pour téléchargements partiels

### Gestionnaire d'I/O Disque

Opérations disque optimisées avec plusieurs stratégies. Le système d'I/O disque est initialisé via `init_disk_io()` et géré via le gestionnaire de session.

**Implémentation :** `ccbt/storage/disk_io.py`

**Optimisations :**
- Préallocation de fichiers (sparse/full)
- Traitement par lots et mise en tampon d'écriture
- I/O mappé en mémoire
- Support io_uring (Linux)
- I/O direct pour stockage haute performance
- Vérification de hash parallèle
- Gestion des points de contrôle pour capacité de reprise

## Flux de Données

### Processus de Téléchargement

```
1. Chargement du Torrent
   ┌─────────────┐
   │ Torrent File│ ──┐
   │ or Magnet   │   │
   └─────────────┘   │
                     │
2. Annonce Tracker   │
   ┌─────────────┐   │
   │   Tracker  │ ◄──┘
   │   Client   │
   └─────────────┘
           │
           ▼
3. Découverte de Pairs
   ┌─────────────┐
   │    DHT     │
   │   Manager  │
   └─────────────┘
           │
           ▼
4. Connexions de Pairs
   ┌─────────────┐
   │    Peer    │
   │ Connection │
   │   Manager  │
   └─────────────┘
           │
           ▼
5. Sélection de Pièces
   ┌─────────────┐
   │    Piece    │
   │   Manager   │
   └─────────────┘
           │
           ▼
6. Transfert de Données
   ┌─────────────┐
   │    Disk     │
   │     I/O     │
   │   Manager   │
   └─────────────┘
```

### Système d'Événements

Le système utilise une architecture basée sur les événements pour un couplage lâche. Les événements sont émis via le `EventBus` global et peuvent être souscrits par n'importe quel composant.

**Implémentation :** `ccbt/utils/events.py`

Le système d'événements inclut des types d'événements complets :

L'enum `EventType` définit tous les événements système incluant les événements de pairs, pièces, torrents, trackers, DHT, protocole, extensions et sécurité. L'enum complet avec tous les types d'événements :

```python
--8<-- "ccbt/utils/events.py:34:152"
```

Les événements sont émis en utilisant le bus d'événements global via la fonction `emit_event()` :

```python
--8<-- "ccbt/utils/events.py:658:661"
```

## Système de Configuration

### Configuration Hiérarchique

La configuration est gérée par `ConfigManager` qui charge les paramètres depuis plusieurs sources par ordre de priorité.

**Implémentation :** `ccbt/config/config.py`

La classe `ConfigManager` gère le chargement, la validation et le rechargement à chaud de la configuration. Elle recherche les fichiers de configuration dans des emplacements standard et prend en charge les mots de passe de proxy chiffrés. Voir l'initialisation :

```python
--8<-- "ccbt/config/config.py:46:60"
```

**Sources de Configuration (par ordre) :**
1. Valeurs par défaut (depuis les modèles Pydantic)
2. Fichier de configuration (`ccbt.toml` dans le répertoire actuel, `~/.config/ccbt/ccbt.toml`, ou `~/.ccbt.toml`)
3. Variables d'environnement (`CCBT_*`)
4. Arguments CLI
5. Surcharges par torrent

### Rechargement à Chaud

Le `ConfigManager` prend en charge le rechargement à chaud des fichiers de configuration sans redémarrer l'application. Le rechargement à chaud est automatiquement démarré lorsqu'un fichier de configuration est détecté.

## Monitoring et Observabilité

### Collecte de Métriques

La collecte de métriques est initialisée via `init_metrics()` et fournit des métriques compatibles Prometheus.

**Implémentation :** `ccbt/monitoring/metrics_collector.py`

Les métriques sont initialisées dans la méthode `start()` du gestionnaire de session et peuvent être accédées via `session.metrics` si activées dans la configuration.

### Système d'Alertes

Le système d'alertes fournit des alertes basées sur des règles pour diverses conditions système.

**Implémentation :** `ccbt/monitoring/alert_manager.py`

### Traçage

Support de traçage distribué pour l'analyse de performance et le débogage.

**Implémentation :** `ccbt/monitoring/tracing.py`

## Fonctionnalités de Sécurité

### Gestionnaire de Sécurité

Le `SecurityManager` fournit des fonctionnalités de sécurité complètes incluant le filtrage IP, la validation de pairs, la limitation de débit et la détection d'anomalies.

**Implémentation :** `ccbt/security/security_manager.py`

Le gestionnaire de sécurité est initialisé dans la méthode `start()` du gestionnaire de session et peut charger les filtres IP depuis la configuration.

### Validation de Pairs

La validation de pairs est gérée par le `PeerValidator` qui vérifie les IPs bloquées et les modèles de comportement suspects.

**Implémentation :** `ccbt/security/peer_validator.py`

### Limitation de Débit

La limitation de débit adaptative pour la gestion de bande passante est fournie par le `RateLimiter` et `AdaptiveLimiter` (basé sur ML).

**Implémentation :** `ccbt/security/rate_limiter.py`, `ccbt/ml/adaptive_limiter.py`

## Extensibilité

### Système de Plugins

Le système de plugins permet aux plugins et extensions optionnels d'être enregistrés et gérés.

**Implémentation :** `ccbt/plugins/base.py`

Les plugins peuvent être enregistrés avec le `PluginManager` et fournissent des hooks pour divers événements système.

### Extensions de Protocole

Les extensions du protocole BitTorrent sont gérées par le `ExtensionManager` qui gère les extensions Fast Extension, PEX, DHT, WebSeed, SSL et XET.

**Implémentation :** `ccbt/extensions/manager.py`

Le `ExtensionManager` initialise toutes les extensions BitTorrent prises en charge incluant les extensions Protocol, SSL, Fast, PEX et DHT. Chaque extension est enregistrée avec ses capacités et son état. Voir la logique d'initialisation :

```python
--8<-- "ccbt/extensions/manager.py:51:110"
```

### Gestionnaire de Protocoles

Le `ProtocolManager` gère plusieurs protocoles (BitTorrent, IPFS, WebTorrent, XET, Hybrid) avec support de circuit breaker et suivi de performance.

**Implémentation :** `ccbt/protocols/base.py`

Le `ProtocolManager` gère plusieurs protocoles avec support de circuit breaker, suivi de performance et émission automatique d'événements. Les protocoles sont enregistrés avec leur type et les statistiques sont suivies par protocole. Voir l'initialisation et l'enregistrement :

```python
--8<-- "ccbt/protocols/base.py:286:324"
```

## Optimisations de Performance

### Async/Await Partout

Toutes les opérations d'I/O sont asynchrones :
- Opérations réseau
- I/O disque
- Vérification de hash
- Chargement de configuration

### Gestion de la Mémoire

- Gestion de messages zéro-copie où possible
- Tampons en anneau pour scénarios à haut débit
- I/O de fichiers mappé en mémoire
- Structures de données efficaces

### Pool de Connexions

Le pool de connexions est implémenté dans la couche de connexion de pairs pour réutiliser efficacement les connexions TCP et gérer les limites de connexion.

**Implémentation :** `ccbt/peer/connection_pool.py`

## Architecture de Tests

### Catégories de Tests

- **Tests Unitaires** : Tests de composants individuels
- **Tests d'Intégration** : Tests d'interaction de composants
- **Tests de Performance** : Benchmarking et profilage
- **Tests de Chaos** : Injection de fautes et tests de résilience

### Utilitaires de Tests

Les utilitaires de tests et mocks sont disponibles dans le répertoire `tests/` pour les tests unitaires, d'intégration, de propriétés et de performance.

## Considérations Futures d'Architecture

### Scalabilité

- Mise à l'échelle horizontale avec plusieurs gestionnaires de session
- Découverte de pairs distribuée
- Équilibrage de charge entre instances

### Intégration Cloud

- Backends de stockage cloud
- Options de déploiement serverless
- Orchestration de conteneurs

### Fonctionnalités Avancées

- Apprentissage automatique pour la sélection de pairs
- Découverte de pairs basée sur blockchain
- **Intégration IPFS** (Implémentée)
- Compatibilité WebTorrent

## Intégration du Protocole IPFS

### Vue d'ensemble de l'Architecture

L'intégration du protocole IPFS fournit l'adressage de contenu décentralisé et les capacités de réseau peer-to-peer via un daemon IPFS.

**Implémentation :** `ccbt/protocols/ipfs.py`

### Points d'Intégration

```
┌─────────────────────────────────────────────────────────────┐
│                    IPFS Protocol Integration                  │
├─────────────────────────────────────────────────────────────┤
│  Session Manager                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         AsyncSessionManager                           │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │         ProtocolManager                         │ │  │
│  │  │  ┌──────────────┐  ┌──────────────┐           │ │  │
│  │  │  │ BitTorrent   │  │    IPFS      │           │ │  │
│  │  │  │  Protocol    │  │  Protocol    │           │ │  │
│  │  │  └──────────────┘  └──────────────┘           │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  IPFS Protocol                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   HTTP API   │  │   Pubsub     │  │     DHT      │     │
│  │  Client      │  │  Messaging   │  │  Discovery   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Content    │  │   Gateway    │  │   Pinning    │     │
│  │  Operations  │  │   Fallback   │  │   Manager    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
├─────────────────────────────────────────────────────────────┤
│  IPFS Daemon (External)                                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  IPFS Node (libp2p, Bitswap, DHT, Gateway)          │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Cycle de Vie du Protocole

1. **Initialisation** : Protocole créé et enregistré dans `ProtocolManager`
2. **Connexion** : `start()` se connecte au daemon IPFS via HTTP API
3. **Vérification** : ID de nœud interrogé pour vérifier la connexion
4. **Opération** : Opérations de contenu, connexions de pairs, messagerie
5. **Nettoyage** : `stop()` déconnecte et nettoie les ressources

### Intégration du Gestionnaire de Session

Le protocole IPFS est automatiquement enregistré lors du démarrage du gestionnaire de session s'il est activé dans la configuration. Le protocole est enregistré avec le gestionnaire de protocoles et démarré, avec gestion d'erreurs gracieuse qui n'empêche pas le démarrage de session si IPFS n'est pas disponible. Voir l'initialisation :

```python
--8<-- "ccbt/session/async_main.py:441:462"
```

### Adressage de Contenu

IPFS utilise des Identifiants de Contenu (CIDs) pour l'adressage de contenu immuable :

- **CIDv0** : Encodé en Base58, format legacy (ex. `Qm...`)
- **CIDv1** : Encodé en Multibase, format moderne (ex. `bafybei...`)
- Le contenu est adressé par son hash cryptographique
- Le même contenu produit toujours le même CID

### Conversion Torrent vers IPFS

Les torrents peuvent être convertis en contenu IPFS :

1. Métadonnées du torrent sérialisées en JSON
2. Métadonnées ajoutées à IPFS, générant un CID
3. Hashes de pièces référencés comme blocs
4. Contenu automatiquement épinglé si configuré

### Communication entre Pairs

- **Pubsub** : Messagerie basée sur des topics (`/ccbt/peer/{peer_id}`)
- **Multiaddr** : Format standard pour les adresses de pairs
- **DHT** : Table de hachage distribuée pour la découverte de pairs
- **Files d'Attente de Messages** : Files d'attente par pair pour livraison fiable

### Opérations de Contenu

- **Add** : Contenu ajouté à IPFS, retourne un CID
- **Get** : Contenu récupéré par CID
- **Pin** : Contenu épinglé pour empêcher la collecte de déchets
- **Unpin** : Contenu désépinglé, peut être collecté comme déchet
- **Stats** : Statistiques de contenu (taille, blocs, liens)

### Configuration

La configuration IPFS fait partie du modèle `Config` principal. Voir la documentation de configuration pour les détails sur les paramètres IPFS.

### Gestion des Erreurs

- Échecs de connexion : Nouvelle tentative automatique avec backoff exponentiel
- Timeouts : Timeouts configurables par opération
- Daemon indisponible : Dégradation gracieuse, protocole reste enregistré
- Contenu non trouvé : Retourne `None`, enregistre un avertissement

### Considérations de Performance

- **Opérations Asynchrones** : Tous les appels API IPFS utilisent `asyncio.to_thread` pour éviter le blocage
- **Cache** : Résultats de découverte et statistiques de contenu mis en cache avec TTL
- **Fallback de Gateway** : Gateways publics utilisés si le daemon n'est pas disponible
- **Pool de Connexions** : Réutilise les connexions HTTP au daemon IPFS

### Diagramme de Séquence

```
Session Manager          IPFS Protocol          IPFS Daemon
     │                         │                      │
     │  start()                │                      │
     ├────────────────────────>│                      │
     │                         │  connect()           │
     │                         ├─────────────────────>│
     │                         │  id()                │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │                         │                      │
     │  add_content()           │                      │
     ├────────────────────────>│  add_bytes()         │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │  <CID>                  │                      │
     │<────────────────────────┤                      │
     │                         │                      │
     │  get_content(CID)       │                      │
     ├────────────────────────>│  cat(CID)            │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │  <content>               │                      │
     │<────────────────────────┤                      │
     │                         │                      │
     │  stop()                  │                      │
     ├────────────────────────>│  close()             │
     │                         ├─────────────────────>│
     │                         │<─────────────────────┤
     │                         │                      │
```

Pour des informations plus détaillées sur des composants spécifiques, voir les fichiers de documentation individuels et le code source.

