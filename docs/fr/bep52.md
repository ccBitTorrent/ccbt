# BEP 52 : Protocole BitTorrent v2

## Vue d'ensemble

Le Protocole BitTorrent v2 (BEP 52) est une mise à jour majeure du protocole BitTorrent qui introduit le hachage SHA-256, une structure de métadonnées améliorée et un meilleur support pour les fichiers volumineux. ccBitTorrent fournit un support complet pour les torrents v2 uniquement, v1 uniquement et les torrents hybrides qui fonctionnent avec les deux protocoles.

### Caractéristiques Clés

- **Hachage SHA-256** : Plus sécurisé que SHA-1 utilisé dans v1
- **Structure Merkle Tree** : Validation efficace des pièces et téléchargements partiels
- **Format File Tree** : Organisation hiérarchique des fichiers
- **Piece Layers** : Validation des pièces par fichier
- **Torrents Hybrides** : Compatibilité descendante avec les clients v1

## Architecture

### Composants Principaux

#### 1. Métadonnées du Torrent (`ccbt/core/torrent_v2.py`)

L'analyseur de torrent v2 gère toutes les opérations de métadonnées :

```python
from ccbt.core.torrent_v2 import TorrentV2Parser, TorrentV2Info

# Analyser le torrent v2
parser = TorrentV2Parser()
with open("torrent_file.torrent", "rb") as f:
    torrent_data = decode(f.read())
    
v2_info = parser.parse_v2(torrent_data[b"info"], torrent_data)

# Accéder aux données spécifiques à v2
print(f"Info Hash v2: {v2_info.info_hash_v2.hex()}")
print(f"File Tree: {v2_info.file_tree}")
print(f"Piece Layers: {len(v2_info.piece_layers)}")
```

#### 2. Communication du Protocole (`ccbt/protocols/bittorrent_v2.py`)

Gère les handshakes et messages v2 :

```python
from ccbt.protocols.bittorrent_v2 import (
    create_v2_handshake,
    send_v2_handshake,
    handle_v2_handshake,
    PieceLayerRequest,
    PieceLayerResponse,
)

# Créer le handshake v2
info_hash_v2 = v2_info.info_hash_v2
peer_id = b"-CC0101-" + b"x" * 12
handshake = create_v2_handshake(info_hash_v2, peer_id)

# Envoyer le handshake
await send_v2_handshake(writer, info_hash_v2, peer_id)

# Recevoir le handshake
version, peer_id, parsed = await handle_v2_handshake(reader, writer)
```

#### 3. Hachage SHA-256 (`ccbt/piece/hash_v2.py`)

Implémente les fonctions de hachage v2 :

```python
from ccbt.piece.hash_v2 import (
    hash_piece_v2,
    hash_piece_layer,
    hash_file_tree,
    verify_piece_v2,
)

# Hacher une pièce
piece_data = b"..." * 16384
piece_hash = hash_piece_v2(piece_data)

# Vérifier la pièce
is_valid = verify_piece_v2(piece_data, expected_hash)

# Construire l'arbre Merkle
piece_hashes = [hash_piece_v2(p) for p in pieces]
merkle_root = hash_piece_layer(piece_hashes)
```

## Configuration

### Activer le Protocole v2

Configurez le support du protocole v2 dans `ccbt.toml` :

```toml
[network.protocol_v2]
enable_protocol_v2 = true      # Activer le support v2
prefer_protocol_v2 = false     # Préférer v2 à v1 lorsque les deux sont disponibles
support_hybrid = true          # Support pour les torrents hybrides
v2_handshake_timeout = 30.0    # Délai d'attente du handshake en secondes
```

### Variables d'Environnement

```bash
export CCBT_PROTOCOL_V2_ENABLE=true
export CCBT_PROTOCOL_V2_PREFER=true
export CCBT_PROTOCOL_V2_SUPPORT_HYBRID=true
export CCBT_PROTOCOL_V2_HANDSHAKE_TIMEOUT=30.0
```

### Options CLI

```bash
# Activer le protocole v2
ccbt download file.torrent --protocol-v2

# Préférer v2 lorsqu'il est disponible
ccbt download file.torrent --protocol-v2-prefer

# Désactiver le protocole v2
ccbt download file.torrent --no-protocol-v2
```

## Créer des Torrents

### Torrents V2 Uniquement

Créez des torrents qui ne fonctionnent qu'avec les clients v2 :

```python
from pathlib import Path
from ccbt.core.torrent_v2 import TorrentV2Parser

parser = TorrentV2Parser()

# Créer à partir d'un seul fichier
torrent_bytes = parser.generate_v2_torrent(
    source=Path("video.mp4"),
    output=Path("video.torrent"),
    trackers=["http://tracker.example.com/announce"],
    piece_length=262144,  # 256 KiB
    comment="My video file",
    private=False,
)

# Créer à partir d'un répertoire
torrent_bytes = parser.generate_v2_torrent(
    source=Path("my_files/"),
    output=Path("my_files.torrent"),
    trackers=[
        "http://tracker1.example.com/announce",
        "http://tracker2.example.com/announce",
    ],
    piece_length=None,  # Auto-calculer
)
```

### Torrents Hybrides

Créez des torrents compatibles avec les clients v1 et v2 :

```python
# Créer un torrent hybride
torrent_bytes = parser.generate_hybrid_torrent(
    source=Path("archive.zip"),
    output=Path("archive.torrent"),
    trackers=["http://tracker.example.com/announce"],
    piece_length=1048576,  # 1 MiB
    comment="Backwards compatible torrent",
    private=False,
)
```

### Création de Torrent CLI

```bash
# Créer un torrent v2
ccbt create-torrent file.mp4 --v2 \
    --output file.torrent \
    --tracker http://tracker.example.com/announce \
    --piece-length 262144 \
    --comment "My file"

# Créer un torrent hybride
ccbt create-torrent directory/ --hybrid \
    --output directory.torrent \
    --tracker http://tracker.example.com/announce \
    --private
```

## Détails du Protocole

### Format de Handshake

#### Handshake V2 (80 octets)
```
- 1 octet :  Longueur de la chaîne de protocole (19)
- 19 octets : "BitTorrent protocol"
- 8 octets :  Octets réservés (bit 0 = 1 pour le support v2)
- 32 octets : SHA-256 info_hash_v2
- 20 octets : Peer ID
```

#### Handshake Hybride (100 octets)
```
- 1 octet :  Longueur de la chaîne de protocole (19)
- 19 octets : "BitTorrent protocol"
- 8 octets :  Octets réservés (bit 0 = 1)
- 20 octets : SHA-1 info_hash_v1
- 32 octets : SHA-256 info_hash_v2
- 20 octets : Peer ID
```

### Négociation de Version du Protocole

ccBitTorrent négocie automatiquement la meilleure version du protocole :

```python
from ccbt.protocols.bittorrent_v2 import (
    ProtocolVersion,
    negotiate_protocol_version,
)

# Handshake du pair
peer_handshake = b"..."

# Nos versions supportées (par ordre de priorité)
supported = [
    ProtocolVersion.HYBRID,
    ProtocolVersion.V2,
    ProtocolVersion.V1,
]

# Négocier
negotiated = negotiate_protocol_version(peer_handshake, supported)

if negotiated == ProtocolVersion.V2:
    # Utiliser le protocole v2
    pass
elif negotiated == ProtocolVersion.HYBRID:
    # Utiliser le mode hybride
    pass
elif negotiated == ProtocolVersion.V1:
    # Revenir à v1
    pass
else:
    # Incompatible
    pass
```

### Messages Spécifiques à V2

#### Demande de Piece Layer (ID de Message 20)

Demander les hachages de pièces pour un fichier :

```python
from ccbt.protocols.bittorrent_v2 import PieceLayerRequest

pieces_root = b"..." # Hachage racine SHA-256 de 32 octets
request = PieceLayerRequest(pieces_root)
message_bytes = request.serialize()
```

#### Réponse de Piece Layer (ID de Message 21)

Envoyer les hachages de pièces :

```python
from ccbt.protocols.bittorrent_v2 import PieceLayerResponse

piece_hashes = [b"..." * 32 for _ in range(10)]  # Liste de hachages SHA-256
response = PieceLayerResponse(pieces_root, piece_hashes)
message_bytes = response.serialize()
```

#### Demande de File Tree (ID de Message 22)

Demander l'arbre de fichiers complet :

```python
from ccbt.protocols.bittorrent_v2 import FileTreeRequest

request = FileTreeRequest()
message_bytes = request.serialize()
```

#### Réponse de File Tree (ID de Message 23)

Envoyer la structure de l'arbre de fichiers :

```python
from ccbt.protocols.bittorrent_v2 import FileTreeResponse

file_tree_bencoded = encode(file_tree_dict)
response = FileTreeResponse(file_tree_bencoded)
message_bytes = response.serialize()
```

## Structure du File Tree

Les torrents v2 utilisent un arbre de fichiers hiérarchique :

```python
from ccbt.core.torrent_v2 import FileTreeNode

# Fichier unique
file_node = FileTreeNode(
    name="video.mp4",
    length=1000000,
    pieces_root=b"..." * 32,
    children=None,
)

# Structure de répertoire
dir_node = FileTreeNode(
    name="my_files",
    length=0,
    pieces_root=None,
    children={
        "file1.txt": FileTreeNode(...),
        "file2.txt": FileTreeNode(...),
        "subdir": FileTreeNode(...),
    },
)

# Vérifier le type de nœud
if file_node.is_file():
    print(f"Fichier : {file_node.length} octets")
if dir_node.is_directory():
    print(f"Répertoire avec {len(dir_node.children)} éléments")
```

## Piece Layers

Chaque fichier a sa propre couche de pièces avec des hachages SHA-256 :

```python
from ccbt.core.torrent_v2 import PieceLayer

# Créer une couche de pièces
layer = PieceLayer(
    piece_length=262144,  # 256 KiB
    pieces=[
        b"..." * 32,  # Hachage de pièce 0
        b"..." * 32,  # Hachage de pièce 1
        b"..." * 32,  # Hachage de pièce 2
    ],
)

# Obtenir le hachage de pièce
piece_0_hash = layer.get_piece_hash(0)

# Nombre de pièces
num_pieces = layer.num_pieces()
```

## Meilleures Pratiques

### Quand Utiliser V2

- **Torrents nouveaux** : Toujours préférer v2 pour le nouveau contenu
- **Fichiers volumineux** : V2 est plus efficace pour les fichiers > 1 GB
- **Sécurité** : SHA-256 offre une meilleure résistance aux collisions
- **Préparation à l'avenir** : V2 est l'avenir de BitTorrent

### Quand Utiliser Hybride

- **Compatibilité maximale** : Atteindre les clients v1 et v2
- **Période de transition** : Pendant la migration de l'écosystème
- **Torrents publics** : Distribution plus large

### Quand Utiliser V1 Uniquement

- **Systèmes hérités** : Seulement lorsque le support v2 n'est pas disponible
- **Petits fichiers** : La surcharge de V1 est acceptable pour < 100 MB

### Sélection de la Longueur de Pièce

L'auto-calcul est recommandé, mais valeurs manuelles :

- **Petits fichiers (< 16 MiB)** : 16 KiB
- **Fichiers moyens (16 MiB - 512 MiB)** : 256 KiB
- **Fichiers volumineux (> 512 MiB)** : 1 MiB
- **Très gros fichiers (> 10 GiB)** : 2-4 MiB

La longueur de pièce doit être une puissance de 2.

## Référence API

### TorrentV2Parser

Classe principale pour les opérations de torrent v2 :

```python
class TorrentV2Parser:
    def parse_v2(self, info_dict: dict, torrent_data: dict) -> TorrentV2Info:
        """Analyser le dictionnaire d'information de torrent v2."""
        
    def parse_hybrid(self, info_dict: dict, torrent_data: dict) -> tuple[TorrentInfo, TorrentV2Info]:
        """Analyser le torrent hybride (retourne les informations v1 et v2)."""
        
    def generate_v2_torrent(
        self,
        source: Path,
        output: Path | None = None,
        trackers: list[str] | None = None,
        web_seeds: list[str] | None = None,
        comment: str | None = None,
        created_by: str = "ccBitTorrent",
        piece_length: int | None = None,
        private: bool = False,
    ) -> bytes:
        """Générer le fichier torrent v2 uniquement."""
        
    def generate_hybrid_torrent(
        self,
        source: Path,
        output: Path | None = None,
        trackers: list[str] | None = None,
        web_seeds: list[str] | None = None,
        comment: str | None = None,
        created_by: str = "ccBitTorrent",
        piece_length: int | None = None,
        private: bool = False,
    ) -> bytes:
        """Générer le fichier torrent hybride."""
```

### TorrentV2Info

Modèle de données pour les informations de torrent v2 :

```python
@dataclass
class TorrentV2Info:
    name: str
    info_hash_v2: bytes  # SHA-256 de 32 octets
    info_hash_v1: bytes | None  # SHA-1 de 20 octets (hybride uniquement)
    announce: str
    announce_list: list[list[str]] | None
    comment: str | None
    created_by: str | None
    creation_date: int | None
    encoding: str | None
    is_private: bool
    file_tree: dict[str, FileTreeNode]
    piece_layers: dict[bytes, PieceLayer]
    piece_length: int
    files: list[FileInfo]
    total_length: int
    num_pieces: int
    
    def get_file_paths(self) -> list[str]:
        """Obtenir la liste de tous les chemins de fichiers."""
        
    def get_piece_layer(self, pieces_root: bytes) -> PieceLayer | None:
        """Obtenir la couche de pièces pour un fichier."""
```

### Fonctions du Protocole

```python
# Handshake
def create_v2_handshake(info_hash_v2: bytes, peer_id: bytes) -> bytes
def create_hybrid_handshake(info_hash_v1: bytes, info_hash_v2: bytes, peer_id: bytes) -> bytes
def detect_protocol_version(handshake: bytes) -> ProtocolVersion
def parse_v2_handshake(data: bytes) -> dict
def negotiate_protocol_version(handshake: bytes, supported: list[ProtocolVersion]) -> ProtocolVersion | None

# I/O Asynchrone
async def send_v2_handshake(writer: StreamWriter, info_hash_v2: bytes, peer_id: bytes) -> None
async def send_hybrid_handshake(writer: StreamWriter, info_hash_v1: bytes, info_hash_v2: bytes, peer_id: bytes) -> None
async def handle_v2_handshake(reader: StreamReader, writer: StreamWriter, our_info_hash_v2: bytes | None = None, our_info_hash_v1: bytes | None = None, timeout: float = 30.0) -> tuple[ProtocolVersion, bytes, dict]
async def upgrade_to_v2(connection: Any, info_hash_v2: bytes) -> bool
```

### Fonctions de Hachage

```python
# Hachage de pièces
def hash_piece_v2(data: bytes) -> bytes
def hash_piece_v2_streaming(data_source: bytes | IO) -> bytes
def verify_piece_v2(data: bytes, expected_hash: bytes) -> bool

# Merkle trees
def hash_piece_layer(piece_hashes: list[bytes]) -> bytes
def verify_piece_layer(piece_hashes: list[bytes], expected_root: bytes) -> bool

# File trees
def hash_file_tree(file_tree: dict[str, FileTreeNode]) -> bytes
```

## Exemples

Consultez [docs/examples/bep52/](examples/bep52/) pour des exemples complets fonctionnels :

- `create_v2_torrent.py` : Créer un torrent v2 à partir d'un fichier
- `create_hybrid_torrent.py` : Créer un torrent hybride
- `parse_v2_torrent.py` : Analyser et afficher les informations du torrent v2
- `protocol_v2_session.py` : Démarrer une session avec support v2

## Dépannage

### Problèmes Courants

**Problème** : Le handshake v2 échoue avec "Info hash v2 mismatch"
- **Solution** : Vérifier que info_hash_v2 est correctement calculé (SHA-256 du dictionnaire info bencoded)

**Problème** : La validation de la couche de pièces échoue
- **Solution** : S'assurer que piece_length correspond entre le torrent et la validation

**Problème** : Erreurs d'analyse de l'arbre de fichiers
- **Solution** : Vérifier que la structure de l'arbre de fichiers suit le format BEP 52 (imbrication appropriée, longueur de pieces_root)

**Problème** : La négociation de version du protocole retourne None
- **Solution** : Le pair peut ne pas supporter v2. Vérifier les octets réservés dans le handshake.

### Journalisation de Débogage

Activer la journalisation de débogage pour le protocole v2 :

```python
import logging
logging.getLogger("ccbt.core.torrent_v2").setLevel(logging.DEBUG)
logging.getLogger("ccbt.protocols.bittorrent_v2").setLevel(logging.DEBUG)
logging.getLogger("ccbt.piece.hash_v2").setLevel(logging.DEBUG)
```

## Considérations de Performance

### Utilisation de la Mémoire

- Les torrents V2 utilisent plus de mémoire pour les couches de pièces (32 octets vs 20 octets par pièce)
- La structure de l'arbre de fichiers ajoute une surcharge pour les torrents multi-fichiers
- Les torrents hybrides stockent les métadonnées v1 et v2

### Utilisation du CPU

- SHA-256 est ~2x plus lent que SHA-1 pour le hachage
- La construction de l'arbre Merkle ajoute une surcharge computationnelle
- Utiliser une longueur de pièce >= 256 KiB pour les fichiers volumineux pour réduire l'utilisation du CPU

### Réseau

- Les handshakes V2 sont 12 octets plus grands (80 vs 68 octets)
- Les handshakes hybrides sont 32 octets plus grands (100 vs 68 octets)
- L'échange de couches de pièces ajoute une surcharge initiale mais permet une reprise efficace

## Conformité aux Normes

L'implémentation BEP 52 de ccBitTorrent suit la spécification officielle :

- **BEP 52** : [BitTorrent Protocol v2](https://www.bittorrent.org/beps/bep_0052.html)
- **Suite de Tests** : Plus de 2500 lignes de tests complets
- **Compatibilité** : Interopérable avec libtorrent, qBittorrent, Transmission

## Voir Aussi

- [Documentation API](API.md)
- [Guide de Configuration](configuration.md)
- [Vue d'ensemble de l'Architecture](architecture.md)
- [Index BEP](https://www.bittorrent.org/beps/bep_0000.html)

