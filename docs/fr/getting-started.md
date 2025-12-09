# Démarrage

Bienvenue dans ccBitTorrent ! Ce guide vous aidera à démarrer rapidement avec notre client BitTorrent haute performance.

!!! tip "Fonctionnalité Clé : Extension du Protocole BEP XET"
    ccBitTorrent inclut l'**Extension du Protocole Xet (BEP XET)**, qui permet le découpage défini par contenu et la déduplication entre torrents. Cela transforme BitTorrent en un système de fichiers peer-to-peer ultra-rapide et actualisable optimisé pour la collaboration. [En savoir plus sur BEP XET →](bep_xet.md)

## Installation

### Prérequis

- Python 3.8 ou supérieur
- Gestionnaire de paquets [UV](https://astral.sh/uv) (recommandé)

### Installer UV

Installez UV depuis le script d'installation officiel :
- macOS/Linux : `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows : `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

### Installer ccBitTorrent

Installer depuis PyPI :
```bash
uv pip install ccbittorrent
```

Ou installer depuis les sources :
```bash
git clone https://github.com/ccBittorrent/ccbt.git
cd ccbt
uv pip install -e .
```

Les points d'entrée sont définis dans [pyproject.toml:79-81](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L79-L81).

## Points d'Entrée Principaux

ccBitTorrent fournit trois points d'entrée principaux :

### 1. Bitonic (Recommandé)

**Bitonic** est l'interface principale du tableau de bord terminal. Il fournit une vue interactive en direct de tous les torrents, pairs et métriques système.

- Point d'entrée : [ccbt/interface/terminal_dashboard.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L1123)
- Défini dans : [pyproject.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L81)
- Lancer : `uv run bitonic` ou `uv run ccbt dashboard`

Consultez le [Guide Bitonic](bitonic.md) pour une utilisation détaillée.

### 2. btbt CLI

**btbt** est l'interface en ligne de commande améliorée avec des fonctionnalités avancées.

- Point d'entrée : [ccbt/cli/main.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L1463)
- Défini dans : [pyproject.toml:80](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L80)
- Lancer : `uv run btbt`

Consultez la [Référence btbt CLI](btbt-cli.md) pour toutes les commandes disponibles.

### 3. ccbt (CLI de Base)

**ccbt** est l'interface en ligne de commande de base.

- Point d'entrée : [ccbt/__main__.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/__main__.py#L18)
- Défini dans : [pyproject.toml:79](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L79)
- Lancer : `uv run ccbt`

## Démarrage Rapide

### Démarrer le Démon {#start-daemon}

ccBitTorrent peut fonctionner en mode démon pour une opération en arrière-plan, ou localement pour des téléchargements en session unique.

**Démarrer le démon (recommandé pour plusieurs torrents) :**
```bash
# Démarrer le démon en arrière-plan
uv run btbt daemon start

# Démarrer le démon au premier plan (pour le débogage)
uv run btbt daemon start --foreground

# Vérifier le statut du démon
uv run btbt daemon status
```

Le démon s'exécute en arrière-plan et gère toutes les sessions torrent. Les commandes CLI se connectent automatiquement au démon lorsqu'il est en cours d'exécution.

**Exécuter localement (sans démon) :**
```bash
# Les commandes s'exécuteront en mode local si le démon n'est pas en cours d'exécution
uv run btbt download movie.torrent
```

### Lancer Bitonic (Recommandé)

Démarrer le tableau de bord terminal :
```bash
uv run bitonic
```

Ou via la CLI :
```bash
uv run ccbt dashboard
```

Avec un taux de rafraîchissement personnalisé :
```bash
uv run ccbt dashboard --refresh 2.0
```

### Télécharger un Torrent {#download-torrent}

En utilisant la CLI :
```bash
# Télécharger depuis un fichier torrent
uv run btbt download movie.torrent

# Télécharger depuis un lien magnet
uv run btbt magnet "magnet:?xt=urn:btih:..."

# Avec limites de débit
uv run btbt download movie.torrent --download-limit 1024 --upload-limit 512

# Reprendre depuis un point de contrôle
uv run btbt download movie.torrent --resume
```

Consultez la [Référence btbt CLI](btbt-cli.md) pour toutes les options de téléchargement.

### Configurer ccBitTorrent {#configure}

Créez un fichier `ccbt.toml` dans votre répertoire de travail. Référencez la configuration d'exemple :
- Configuration par défaut : [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
- Variables d'environnement : [env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
- Système de configuration : [ccbt/config/config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)

!!! warning "Résolution de Chemins Windows"
    Sur Windows, les chemins liés au démon (fichiers PID, répertoires d'état) utilisent l'aide `_get_daemon_home_dir()` de `ccbt/daemon/daemon_manager.py` pour une résolution de chemin cohérente, notamment avec des espaces dans les noms d'utilisateur. Voir [Guide de Configuration - Résolution de Chemins Windows](configuration.md#daemon-home-dir) pour plus de détails.

Consultez le [Guide de Configuration](configuration.md) pour les options de configuration détaillées.

## Rapports du Projet

Voir les métriques de qualité du projet et les rapports :

- **Couverture de Code** : [reports/coverage.md](reports/coverage.md) - Analyse complète de la couverture de code
- **Rapport de Sécurité** : [reports/bandit/index.md](reports/bandit/index.md) - Résultats du scan de sécurité de Bandit
- **Benchmarks** : [reports/benchmarks/index.md](reports/benchmarks/index.md) - Résultats des benchmarks de performance

Ces rapports sont générés et mis à jour automatiquement dans le cadre de notre processus d'intégration continue.

## Prochaines Étapes

- [Bitonic](bitonic.md) - Découvrez l'interface du tableau de bord terminal
- [btbt CLI](btbt-cli.md) - Référence complète de l'interface en ligne de commande
- [Configuration](configuration.md) - Options de configuration détaillées
- [Réglage des Performances](performance.md) - Guide d'optimisation
- [Référence API](API.md) - Documentation de l'API Python incluant les fonctionnalités de surveillance

## Obtenir de l'Aide

- Utilisez `uv run bitonic --help` ou `uv run btbt --help` pour l'aide des commandes
- Consultez la [Référence btbt CLI](btbt-cli.md) pour les options détaillées
- Visitez notre [dépôt GitHub](https://github.com/ccBittorrent/ccbt) pour les problèmes et discussions
