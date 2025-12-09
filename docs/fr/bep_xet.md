# BEP XET : Extension du Protocole Xet pour Chunking Défini par Contenu et Déduplication

## Vue d'ensemble

L'Extension du Protocole Xet (BEP XET) est une extension du protocole BitTorrent qui permet le chunking défini par contenu (CDC) et la déduplication entre torrents via un système de stockage adressable par contenu (CAS) peer-to-peer. Cette extension transforme BitTorrent en un système de fichiers peer-to-peer super rapide et actualisable optimisé pour la collaboration et le partage efficace de données.

## Justification

L'extension du protocole Xet résout les limitations clés de BitTorrent traditionnel :

1. **Tailles de Pièce Fixes** : BitTorrent traditionnel utilise des tailles de pièce fixes, conduisant à une redistribution inefficace lorsque les fichiers sont modifiés. CDC s'adapte aux limites de contenu.

2. **Pas de Déduplication Entre Torrents** : Chaque torrent est indépendant, même s'il partage un contenu identique. Xet permet la déduplication au niveau des chunks entre torrents.

3. **Stockage Centralisé** : Les systèmes CAS traditionnels nécessitent des services externes. Xet construit CAS directement dans le réseau BitTorrent en utilisant DHT et les trackers.

4. **Mises à Jour Inefficaces** : Mettre à jour un fichier partagé nécessite de redistribuer tout le fichier. Xet ne redistribue que les chunks modifiés.

En combinant CDC, déduplication et CAS P2P, Xet transforme BitTorrent en un système de fichiers peer-to-peer super rapide et actualisable optimisé pour la collaboration.

### Caractéristiques Clés

- **Chunking Défini par Contenu (CDC)** : Segmentation intelligente de fichiers basée sur Gearhash (chunks de 8KB-128KB)
- **Déduplication Entre Torrents** : Déduplication au niveau des chunks entre plusieurs torrents
- **CAS Peer-to-Peer** : Stockage Adressable par Contenu décentralisé utilisant DHT et les trackers
- **Vérification Merkle Tree** : Hachage BLAKE3-256 avec fallback SHA-256 pour l'intégrité
- **Format Xorb** : Format de stockage efficace pour regrouper plusieurs chunks
- **Format Shard** : Stockage de métadonnées pour les informations de fichiers et les données CAS
- **Compression LZ4** : Compression optionnelle pour les données Xorb

## Cas d'Utilisation

### 1. Partage Collaboratif de Fichiers

Xet permet une collaboration efficace en :
- **Déduplication** : Les fichiers partagés entre plusieurs torrents partagent les mêmes chunks
- **Mises à Jour Rapides** : Seuls les chunks modifiés doivent être redistribués
- **Contrôle de Version** : Suivre les versions de fichiers via les racines de Merkle tree

### 2. Distribution de Fichiers Volumineux

Pour les fichiers volumineux ou les ensembles de données :
- **Chunking Défini par Contenu** : Les limites intelligentes réduisent la redistribution des chunks lors des modifications
- **Téléchargements Parallèles** : Télécharger des chunks depuis plusieurs pairs simultanément
- **Capacité de Reprise** : Suivre les chunks individuels pour une reprise fiable

### 3. Système de Fichiers Peer-to-Peer

Transformer BitTorrent en système de fichiers P2P :
- **Intégration CAS** : Chunks stockés dans DHT pour disponibilité globale
- **Stockage de Métadonnées** : Les shards fournissent les métadonnées du système de fichiers
- **Recherches Rapides** : Accès direct aux chunks via hash élimine le besoin de télécharger le torrent complet

## État d'Implémentation

L'extension du protocole Xet est entièrement implémentée dans ccBitTorrent :

- ✅ Chunking Défini par Contenu (Gearhash CDC)
- ✅ Hachage BLAKE3-256 avec fallback SHA-256
- ✅ Cache de déduplication SQLite
- ✅ Intégration DHT (BEP 44)
- ✅ Intégration des trackers
- ✅ Formats Xorb et Shard
- ✅ Calcul de Merkle tree
- ✅ Extension du protocole BitTorrent (BEP 10)
- ✅ Intégration CLI
- ✅ Gestion de configuration

## Configuration

### Commandes CLI

```bash
# Activer le protocole Xet
ccbt xet enable

# Afficher l'état de Xet
ccbt xet status

# Afficher les statistiques de déduplication
ccbt xet stats

# Nettoyer les chunks non utilisés
ccbt xet cleanup --max-age-days 30
```

### Activer le Protocole Xet

Configurez le support Xet dans `ccbt.toml` :

```toml
[disk]
# Configuration du Protocole Xet
xet_enabled = false                        # Activer le protocole Xet
xet_chunk_min_size = 8192                  # Taille minimale de chunk (octets)
xet_chunk_max_size = 131072                # Taille maximale de chunk (octets)
xet_chunk_target_size = 16384              # Taille cible de chunk (octets)
xet_deduplication_enabled = true           # Activer la déduplication au niveau des chunks
xet_cache_db_path = "data/xet_cache.db"    # Chemin de la base de données de cache SQLite
xet_chunk_store_path = "data/xet_chunks"   # Répertoire de stockage des chunks
xet_use_p2p_cas = true                     # Utiliser le Stockage Adressable par Contenu P2P
xet_compression_enabled = true             # Activer la compression LZ4 pour les données Xorb
```


## Spécification du Protocole

### Négociation d'Extension

L'extension XET suit BEP 10 (Extension Protocol) pour la négociation. Pendant le handshake étendu, les pairs échangent les capacités d'extension :

- **Nom d'Extension** : `ut_xet`
- **ID d'Extension** : Assigné dynamiquement pendant le handshake (1-255)
- **Capacités Requises** : Aucune (l'extension est optionnelle)

Les pairs supportant XET incluent `ut_xet` dans leur handshake d'extension. L'ID d'extension est stocké par session de pair pour le routage des messages.

### Types de Message

L'extension XET définit les types de message suivants :

#### Messages de Chunk

1. **CHUNK_REQUEST (0x01)** : Demander un chunk spécifique par hash
2. **CHUNK_RESPONSE (0x02)** : Réponse contenant les données du chunk
3. **CHUNK_NOT_FOUND (0x03)** : Le pair n'a pas le chunk demandé
4. **CHUNK_ERROR (0x04)** : Erreur survenue lors de la récupération du chunk

#### Messages de Synchronisation de Dossiers

5. **FOLDER_VERSION_REQUEST (0x10)** : Demander la version du dossier (référence de commit git)
6. **FOLDER_VERSION_RESPONSE (0x11)** : Réponse avec la version du dossier
7. **FOLDER_UPDATE_NOTIFY (0x12)** : Notifier le pair d'une mise à jour de dossier
8. **FOLDER_SYNC_MODE_REQUEST (0x13)** : Demander le mode de synchronisation
9. **FOLDER_SYNC_MODE_RESPONSE (0x14)** : Réponse avec le mode de synchronisation

#### Messages d'Échange de Métadonnées

10. **FOLDER_METADATA_REQUEST (0x20)** : Demander les métadonnées du dossier (fichier .tonic)
11. **FOLDER_METADATA_RESPONSE (0x21)** : Réponse avec la pièce de métadonnées du dossier
12. **FOLDER_METADATA_NOT_FOUND (0x22)** : Métadonnées non disponibles

#### Messages de Filtre Bloom

13. **BLOOM_FILTER_REQUEST (0x30)** : Demander le filtre bloom du pair pour la disponibilité des chunks
14. **BLOOM_FILTER_RESPONSE (0x31)** : Réponse avec les données du filtre bloom

### Format de Message

#### CHUNK_REQUEST

```
Offset  Taille  Description
0       32      Hash du chunk (BLAKE3-256 ou SHA-256)
```

#### CHUNK_RESPONSE

```
Offset  Taille  Description
0       32      Hash du chunk
32      4       Longueur des données du chunk (big-endian)
36      N       Données du chunk
```

#### CHUNK_NOT_FOUND

```
Offset  Taille  Description
0       32      Hash du chunk
```

#### CHUNK_ERROR

```
Offset  Taille  Description
0       32      Hash du chunk
32      4       Code d'erreur (big-endian)
36      N       Message d'erreur (UTF-8)
```

#### FOLDER_VERSION_REQUEST

```
Offset  Taille  Description
0       N       Identifiant de dossier (UTF-8, terminé par null)
```

#### FOLDER_VERSION_RESPONSE

```
Offset  Taille  Description
0       N       Identifiant de dossier (UTF-8, terminé par null)
N       40      Référence de commit git (SHA-1, 20 octets) ou (SHA-256, 32 octets)
```

#### FOLDER_UPDATE_NOTIFY

```
Offset  Taille  Description
0       N       Identifiant de dossier (UTF-8, terminé par null)
N       40      Nouvelle référence de commit git
N+40    8       Timestamp (big-endian, époque Unix)
```

#### FOLDER_SYNC_MODE_REQUEST

```
Offset  Taille  Description
0       N       Identifiant de dossier (UTF-8, terminé par null)
```

#### FOLDER_SYNC_MODE_RESPONSE

```
Offset  Taille  Description
0       N       Identifiant de dossier (UTF-8, terminé par null)
N       1       Mode de synchronisation (0=DESIGNATED, 1=BEST_EFFORT, 2=BROADCAST, 3=CONSENSUS)
```

#### FOLDER_METADATA_REQUEST

```
Offset  Taille  Description
0       N       Identifiant de dossier (UTF-8, terminé par null)
N       4       Index de pièce (big-endian, basé sur 0)
```

#### FOLDER_METADATA_RESPONSE

```
Offset  Taille  Description
0       N       Identifiant de dossier (UTF-8, terminé par null)
N       4       Index de pièce (big-endian)
N+4     4       Total de pièces (big-endian)
N+8     4       Taille de pièce (big-endian)
N+12    M       Données de pièce (fragment de fichier .tonic bencoded)
```

#### BLOOM_FILTER_REQUEST

```
Offset  Taille  Description
0       4       Taille du filtre en octets (big-endian)
```

#### BLOOM_FILTER_RESPONSE

```
Offset  Taille  Description
0       4       Taille du filtre en octets (big-endian)
4       4       Nombre de hash (big-endian)
8       N       Données du filtre bloom (tableau de bits)
```

### Découverte de Chunks

Les chunks sont découverts via plusieurs mécanismes :

1. **DHT (BEP 44)** : Stocker et récupérer les métadonnées de chunks en utilisant DHT. Le hash du chunk (32 octets) est utilisé comme clé DHT. Format de métadonnées : `{"type": "xet_chunk", "available": True, "ed25519_public_key": "...", "ed25519_signature": "..."}`

2. **Trackers** : Annoncer la disponibilité des chunks aux trackers. Les 20 premiers octets du hash du chunk utilisés comme info_hash pour les annonces de tracker.

3. **Peer Exchange (PEX)** : PEX étendu (BEP 11) avec messages de disponibilité de chunks. Les types de message `CHUNKS_ADDED` et `CHUNKS_DROPPED` échangent des listes de hashes de chunks.

4. **Filtres Bloom** : Pré-filtrer les requêtes de disponibilité de chunks. Les pairs échangent des filtres bloom contenant leurs chunks disponibles pour réduire la surcharge réseau.

5. **Catalogue de Chunks** : Index en mémoire ou persistant mappant les hashes de chunks aux informations de pairs. Permet des requêtes en masse rapides pour plusieurs chunks.

6. **Découverte Locale de Pairs (BEP 14)** : Multicast UDP pour la découverte de pairs sur le réseau local. Adresse et port multicast spécifiques à XET configurables.

7. **Diffusion Multicast** : Multicast UDP pour les annonces de chunks sur le réseau local.

8. **Protocole Gossip** : Protocole de style épidémique pour la propagation décentralisée de mises à jour avec fanout et intervalle configurables.

9. **Inondation Contrôlée** : Mécanisme d'inondation basé sur TTL pour les mises à jour urgentes avec seuil de priorité.

10. **Métadonnées de Torrent** : Extraire les hashes de chunks des métadonnées XET du torrent ou des couches de pièces BitTorrent v2.

### Synchronisation de Dossiers

XET supporte la synchronisation de dossiers avec plusieurs modes de synchronisation :

#### Modes de Synchronisation

- **DESIGNATED (0)** : Source unique de vérité. Un pair désigné comme source, les autres se synchronisent depuis lui. Élection automatique du pair source basée sur le temps de fonctionnement et la disponibilité des chunks.

- **BEST_EFFORT (1)** : Tous les nœuds contribuent aux mises à jour, meilleur effort. Résolution de conflits via last-write-wins, version-vector, 3-way-merge ou stratégies de timestamp.

- **BROADCAST (2)** : Nœuds spécifiques diffusent les mises à jour avec file d'attente. Utilise le protocole gossip ou l'inondation contrôlée pour la propagation.

- **CONSENSUS (3)** : Les mises à jour nécessitent l'accord de la majorité des nœuds. Supporte la majorité simple, le consensus Raft ou la Tolérance aux Pannes Byzantines (BFT).

#### Résolution de Conflits

Lorsque des conflits sont détectés en mode BEST_EFFORT, les stratégies suivantes sont disponibles :

- **last-write-wins** : Le timestamp de modification le plus récent gagne
- **version-vector** : Détection et résolution de conflits basées sur horloge vectorielle
- **3-way-merge** : Algorithme de fusion à trois voies pour résolution automatique de conflits
- **timestamp** : Résolution basée sur timestamp avec fenêtres de temps configurables

#### Intégration Git

Versions de dossiers suivies via références de commit git (SHA-1 ou SHA-256). Changements détectés via `git diff`. Auto-commit activé si `git_auto_commit=True`. Le dépôt git doit être initialisé à la racine du dossier.

#### Liste d'Autorisation

Liste d'autorisation chiffrée utilisant Ed25519 pour la signature et AES-256-GCM pour le stockage. Vérifiée pendant le handshake de pairs. Alias supportés pour les noms de pairs lisibles par l'homme. Hash de la liste d'autorisation échangé pendant le handshake d'extension.

### Format de Fichier .tonic

Le format de fichier `.tonic` (similaire à `.torrent`) contient des métadonnées spécifiques à XET :

```
dictionary {
    "xet": dictionary {
        "version": integer,           # Version du format (1)
        "sync_mode": integer,        # 0=DESIGNATED, 1=BEST_EFFORT, 2=BROADCAST, 3=CONSENSUS
        "git_ref": string,           # Référence de commit git (SHA-1 ou SHA-256)
        "allowlist_hash": string,    # Hash SHA-256 de la liste d'autorisation
        "file_tree": dictionary {    # Structure de répertoire imbriquée
            "path": dictionary {
                "": dictionary {     # Clé vide = métadonnées de fichier
                    "hash": string,   # Hash du fichier
                    "size": integer   # Taille du fichier
                }
            }
        },
        "files": list [              # Liste plate de fichiers
            dictionary {
                "path": string,
                "hash": string,
                "size": integer
            }
        ],
        "chunk_hashes": list [       # Liste de hashes de chunks (32 octets chacun)
            string
        ]
    }
}
```

### Mappage de Ports NAT

XET nécessite le mappage de ports UDP pour une traversée NAT appropriée :

- **Port du Protocole XET** : Configurable via `xet_port` (par défaut `listen_port_udp`). Mappé via UPnP/NAT-PMP si `map_xet_port=True`.

- **Port Multicast XET** : Configurable via `xet_multicast_port`. Mappé si `map_xet_multicast_port=True` (généralement pas nécessaire pour multicast).

Les informations du port externe propagées aux trackers pour une découverte appropriée des pairs. `NATManager.get_external_port()` supporte le protocole UDP pour les requêtes de port XET.


## Architecture

### Composants Principaux

#### 1. Extension de Protocole (`ccbt/extensions/xet.py`)

L'extension Xet implémente les messages BEP 10 (Extension Protocol) pour les requêtes et réponses de chunks.

::: ccbt.extensions.xet.XetExtension
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Types de Message :**

```23:29:ccbt/extensions/xet.py
class XetMessageType(IntEnum):
    """Xet Extension message types."""

    CHUNK_REQUEST = 0x01  # Request chunk by hash
    CHUNK_RESPONSE = 0x02  # Response with chunk data
    CHUNK_NOT_FOUND = 0x03  # Chunk not available
    CHUNK_ERROR = 0x04  # Error retrieving chunk
```

**Méthodes Clés :**
- `encode_chunk_request()`: [ccbt/extensions/xet.py:89](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/extensions/xet.py#L89) - Encoder le message de requête de chunk avec ID de requête
- `decode_chunk_request()`: [ccbt/extensions/xet.py:108](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/extensions/xet.py#L108) - Décoder le message de requête de chunk
- `encode_chunk_response()`: [ccbt/extensions/xet.py:136](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/extensions/xet.py#L136) - Encoder la réponse de chunk avec données
- `handle_chunk_request()`: [ccbt/extensions/xet.py:210](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/extensions/xet.py#L210) - Gérer la requête de chunk entrante du pair
- `handle_chunk_response()`: [ccbt/extensions/xet.py:284](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/extensions/xet.py#L284) - Gérer la réponse de chunk du pair

**Handshake d'Extension :**
- `encode_handshake()`: [ccbt/extensions/xet.py:61](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/extensions/xet.py#L61) - Encoder les capacités de l'extension Xet
- `decode_handshake()`: [ccbt/extensions/xet.py:75](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/extensions/xet.py#L75) - Décoder les capacités de l'extension Xet du pair

#### 2. Chunking Défini par Contenu (`ccbt/storage/xet_chunking.py`)

Algorithme Gearhash CDC pour segmentation intelligente de fichiers avec chunks de taille variable basés sur les motifs de contenu.

::: ccbt.storage.xet_chunking.GearhashChunker
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Constantes :**
- `MIN_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:21](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py#L21) - Taille minimale de chunk de 8 KB
- `MAX_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:22](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py#L22) - Taille maximale de chunk de 128 KB
- `TARGET_CHUNK_SIZE`: [ccbt/storage/xet_chunking.py:23](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py#L23) - Taille cible de chunk par défaut de 16 KB
- `WINDOW_SIZE`: [ccbt/storage/xet_chunking.py:24](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py#L24) - Fenêtre de hash glissant de 48 octets

**Méthodes Clés :**
- `chunk_buffer()`: [ccbt/storage/xet_chunking.py:210](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py#L210) - Fragmenter les données en utilisant l'algorithme Gearhash CDC
- `_find_chunk_boundary()`: [ccbt/storage/xet_chunking.py:242](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py#L242) - Trouver la limite de chunk définie par contenu en utilisant le hash glissant
- `_init_gear_table()`: [ccbt/storage/xet_chunking.py:54](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_chunking.py#L54) - Initialiser la table de gear précalculée pour le hash glissant

**Algorithme :**
L'algorithme Gearhash utilise un hash glissant avec une table de gear précalculée de 256 éléments pour trouver les limites définies par contenu. Cela garantit que le contenu similaire dans différents fichiers produit les mêmes limites de chunk, permettant la déduplication entre fichiers.

#### 3. Cache de Déduplication (`ccbt/storage/xet_deduplication.py`)

Cache de déduplication local basé sur SQLite avec intégration DHT pour déduplication au niveau des chunks.

::: ccbt.storage.xet_deduplication.XetDeduplication
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Schéma de Base de Données :**
- Table `chunks`: [ccbt/storage/xet_deduplication.py:65](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py#L65) - Stocke le hash de chunk, la taille, le chemin de stockage, le compteur de références, les timestamps
- Index : [ccbt/storage/xet_deduplication.py:75](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py#L75) - Sur size et last_accessed pour requêtes efficaces

**Méthodes Clés :**
- `check_chunk_exists()`: [ccbt/storage/xet_deduplication.py:85](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py#L85) - Vérifier si le chunk existe localement et mettre à jour le temps d'accès
- `store_chunk()`: [ccbt/storage/xet_deduplication.py:112](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py#L112) - Stocker le chunk avec déduplication (incrémente ref_count si existe)
- `get_chunk_path()`: [ccbt/storage/xet_deduplication.py:165](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py#L165) - Obtenir le chemin de stockage local pour le chunk
- `cleanup_unused_chunks()`: [ccbt/storage/xet_deduplication.py:201](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_deduplication.py#L201) - Supprimer les chunks non accédés dans max_age_days

**Fonctionnalités :**
- Comptage de références : Suit combien de torrents/fichiers référencent chaque chunk
- Nettoyage automatique : Supprime les chunks non utilisés basés sur le temps d'accès
- Stockage physique : Chunks stockés dans le répertoire `xet_chunks/` avec hash comme nom de fichier

#### 4. CAS Peer-to-Peer (`ccbt/discovery/xet_cas.py`)

Découverte et échange de chunks basés sur DHT et trackers pour Stockage Adressable par Contenu décentralisé.

::: ccbt.discovery.xet_cas.P2PCASClient
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 4
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Méthodes Clés :**
- `announce_chunk()`: [ccbt/discovery/xet_cas.py:50](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/xet_cas.py#L50) - Annoncer la disponibilité du chunk à DHT (BEP 44) et aux trackers
- `find_chunk_peers()`: [ccbt/discovery/xet_cas.py:112](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/xet_cas.py#L112) - Trouver les pairs qui ont un chunk spécifique via requêtes DHT et tracker
- `request_chunk_from_peer()`: [ccbt/discovery/xet_cas.py:200](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/xet_cas.py#L200) - Demander le chunk depuis un pair spécifique en utilisant le protocole d'extension Xet

**Intégration DHT :**
- Utilise BEP 44 (Distributed Hash Table for Mutable Items) pour stocker les métadonnées de chunks
- Format de métadonnées de chunk : [ccbt/discovery/xet_cas.py:68](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/discovery/xet_cas.py#L68) - `{"type": "xet_chunk", "available": True}`
- Supporte plusieurs méthodes DHT : `store()`, `store_chunk_hash()`, `get_chunk_peers()`, `get_peers()`, `find_value()`

**Intégration des Trackers :**
- Annonce les chunks aux trackers en utilisant les 20 premiers octets du hash du chunk comme info_hash
- Permet la découverte de pairs basée sur les trackers pour les chunks

## Formats de Stockage

### Format Xorb

Les Xorbs regroupent plusieurs chunks pour un stockage et une récupération efficaces.

::: ccbt.storage.xet_xorb.Xorb
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Spécification de Format :**
- En-tête : [ccbt/storage/xet_xorb.py:123](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L123) - 16 octets (magic `0x24687531`, version, flags, réservé)
- Nombre de chunks : [ccbt/storage/xet_xorb.py:149](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L149) - 4 octets (uint32, little-endian)
- Entrées de chunk : [ccbt/storage/xet_xorb.py:140](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L140) - Variable (hash, tailles, données pour chaque chunk)
- Métadonnées : [ccbt/storage/xet_xorb.py:119](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L119) - 8 octets (taille totale non compressée comme uint64)

**Constantes :**
- `MAX_XORB_SIZE`: [ccbt/storage/xet_xorb.py:35](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L35) - Taille maximale de xorb de 64 MiB
- `XORB_MAGIC_INT`: [ccbt/storage/xet_xorb.py:36](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L36) - Nombre magique `0x24687531`
- `FLAG_COMPRESSED`: [ccbt/storage/xet_xorb.py:42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L42) - Flag de compression LZ4

**Méthodes Clés :**
- `add_chunk()`: [ccbt/storage/xet_xorb.py:62](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L62) - Ajouter un chunk au xorb (échoue si dépasse MAX_XORB_SIZE)
- `serialize()`: [ccbt/storage/xet_xorb.py:84](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L84) - Sérialiser le xorb au format binaire avec compression LZ4 optionnelle
- `deserialize()`: [ccbt/storage/xet_xorb.py:200](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L200) - Désérialiser le xorb depuis le format binaire avec décompression automatique

**Compression :**
- Compression LZ4 optionnelle : [ccbt/storage/xet_xorb.py:132](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L132) - Compresse les données de chunk si `compress=True` et LZ4 disponible
- Détection automatique : [ccbt/storage/xet_xorb.py:22](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_xorb.py#L22) - Rechute gracieusement si LZ4 n'est pas installé

### Format Shard

Les Shards stockent les métadonnées de fichiers et les informations CAS pour des opérations efficaces du système de fichiers.

::: ccbt.storage.xet_shard.XetShard
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Spécification de Format :**
- En-tête : [ccbt/storage/xet_shard.py:142](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L142) - 24 octets (magic `"SHAR"`, version, flags, comptes de fichier/xorb/chunk)
- Section d'Informations de Fichier : [ccbt/storage/xet_shard.py:145](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L145) - Variable (chemin, hash, taille, références xorb pour chaque fichier)
- Section d'Informations CAS : [ccbt/storage/xet_shard.py:148](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L148) - Variable (hashes xorb, hashes de chunks)
- Pied de page HMAC : [ccbt/storage/xet_shard.py:150](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L150) - 32 octets (HMAC-SHA256 si clé fournie)

**Constantes :**
- `SHARD_MAGIC`: [ccbt/storage/xet_shard.py:19](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L19) - Octets magiques `b"SHAR"`
- `SHARD_VERSION`: [ccbt/storage/xet_shard.py:20](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L20) - Version de format 1
- `HMAC_SIZE`: [ccbt/storage/xet_shard.py:22](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L22) - 32 octets pour HMAC-SHA256

**Méthodes Clés :**
- `add_file_info()`: [ccbt/storage/xet_shard.py:47](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L47) - Ajouter les métadonnées de fichier avec références xorb
- `add_chunk_hash()`: [ccbt/storage/xet_shard.py:80](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L80) - Ajouter le hash de chunk au shard
- `add_xorb_hash()`: [ccbt/storage/xet_shard.py:93](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L93) - Ajouter le hash xorb au shard
- `serialize()`: [ccbt/storage/xet_shard.py:106](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L106) - Sérialiser le shard au format binaire avec HMAC optionnel
- `deserialize()`: [ccbt/storage/xet_shard.py:201](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L201) - Désérialiser le shard depuis le format binaire avec vérification HMAC

**Intégrité :**
- Vérification HMAC : [ccbt/storage/xet_shard.py:170](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_shard.py#L170) - HMAC-SHA256 optionnel pour l'intégrité du shard

## Calcul de Merkle Tree

Les fichiers sont vérifiés en utilisant des Merkle trees construits à partir de hashes de chunks pour une vérification efficace de l'intégrité.

::: ccbt.storage.xet_hashing.XetHasher
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3
      members_order: alphabetical
      filters:
        - "!^_"
      show_submodules: false

**Fonctions de Hachage :**
- `compute_chunk_hash()`: [ccbt/storage/xet_hashing.py:43](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L43) - Calculer le hash BLAKE3-256 pour le chunk (rechute vers SHA-256)
- `compute_xorb_hash()`: [ccbt/storage/xet_hashing.py:63](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L63) - Calculer le hash pour les données xorb
- `verify_chunk_hash()`: [ccbt/storage/xet_hashing.py:158](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L158) - Vérifier les données de chunk contre le hash attendu

**Construction de Merkle Tree :**
- `build_merkle_tree()`: [ccbt/storage/xet_hashing.py:78](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L78) - Construire le Merkle tree à partir des données de chunk (hashe les chunks d'abord)
- `build_merkle_tree_from_hashes()`: [ccbt/storage/xet_hashing.py:115](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L115) - Construire le Merkle tree à partir de hashes de chunks pré-calculés

**Algorithme :**
Le Merkle tree est construit de bas en haut en appariant les hashes à chaque niveau :
1. Commencer avec les hashes de chunk (nœuds feuille)
2. Apparier les hashes adjacents et hasher la combinaison
3. Répéter jusqu'à ce qu'un seul hash racine reste
4. Nombres impairs : dupliquer le dernier hash pour l'appariement

**Hachage Incrémental :**
- `hash_file_incremental()`: [ccbt/storage/xet_hashing.py:175](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L175) - Calculer le hash de fichier de manière incrémentale pour l'efficacité mémoire

**Taille de Hash :**
- `HASH_SIZE`: [ccbt/storage/xet_hashing.py:40](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L40) - 32 octets pour BLAKE3-256 ou SHA-256

**Support BLAKE3 :**
- Détection automatique : [ccbt/storage/xet_hashing.py:21](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/xet_hashing.py#L21) - Utilise BLAKE3 si disponible, rechute vers SHA-256
- Performance : BLAKE3 fournit de meilleures performances pour les fichiers volumineux

## Références

- [BEP 10: Extension Protocol](https://www.bittorrent.org/beps/bep_0010.html)
- [BEP 44: Distributed Hash Table for Mutable Items](https://www.bittorrent.org/beps/bep_0044.html)
- [BEP 52: BitTorrent Protocol v2](https://www.bittorrent.org/beps/bep_0052.html)
- [Gearhash Algorithm](https://github.com/xetdata/xet-core)

