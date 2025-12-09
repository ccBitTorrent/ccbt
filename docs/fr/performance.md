# Guide d'Optimisation des Performances

Ce guide couvre les techniques d'optimisation des performances pour ccBitTorrent afin d'atteindre des vitesses de téléchargement maximales et une utilisation efficace des ressources.

## Optimisation Réseau

### Paramètres de Connexion

#### Profondeur du Pipeline

Contrôle le nombre de requêtes en attente par pair.

Configuration : [ccbt.toml:12](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L12)

**Recommandations :**
- **Connexions à haute latence** : 32-64 (satellite, mobile)
- **Connexions à faible latence** : 16-32 (fibre, câble)
- **Réseaux locaux** : 8-16 (transferts LAN)

Implémentation : [ccbt/peer/async_peer_connection.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/async_peer_connection.py) - Pipeline de requêtes

#### Taille de Bloc

Taille des blocs de données demandés aux pairs.

Configuration : [ccbt.toml:13](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L13)

**Recommandations :**
- **Haut débit** : 32-64 KiB (fibre, câble)
- **Débit moyen** : 16-32 KiB (DSL, mobile)
- **Faible débit** : 4-16 KiB (dial-up, mobile lent)

Tailles min/max de bloc : [ccbt.toml:14-15](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L14-L15)

#### Tampons de Socket

Augmenter pour les scénarios à haut débit.

Configuration : [ccbt.toml:17-18](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L17-L18)

Valeurs par défaut : [ccbt.toml:17-18](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L17-L18) (256 KiB chacun)

Paramètre TCP_NODELAY : [ccbt.toml:19](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L19)

### Limites de Connexion

#### Limites Globales de Pairs

Configuration : [ccbt.toml:6-7](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L6-L7)

**Lignes Directrices d'Ajustement :**
- **Haut débit** : Augmenter les pairs globaux (200-500)
- **Faible débit** : Réduire les pairs globaux (50-100)
- **Beaucoup de torrents** : Réduire la limite par torrent (10-25)
- **Peu de torrents** : Augmenter la limite par torrent (50-100)

Implémentation : [ccbt/peer/connection_pool.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/connection_pool.py) - Gestion du pool de connexions

Connexions max par pair : [ccbt.toml:8](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L8)

#### Délais d'Attente de Connexion

Configuration : [ccbt.toml:22-25](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L22-L25)

- Délai d'attente de connexion : [ccbt.toml:22](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L22)
- Délai d'attente de handshake : [ccbt.toml:23](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L23)
- Intervalle keep alive : [ccbt.toml:24](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L24)
- Délai d'attente de pair : [ccbt.toml:25](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L25)

## Optimisation E/S Disque

### Stratégie de Préallocation

Configuration : [ccbt.toml:59](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L59)

**Recommandations :**
- **SSD** : Utiliser "full" pour de meilleures performances
- **HDD** : Utiliser "sparse" pour économiser l'espace
- **Stockage réseau** : Utiliser "none" pour éviter les retards

Option fichiers sparse : [ccbt.toml:60](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L60)

Implémentation : [ccbt/storage/disk_io.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Opérations E/S disque

### Optimisation d'Écriture

Configuration : [ccbt.toml:63-64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L63-L64)

**Lignes Directrices d'Ajustement :**
- **Stockage rapide** : Augmenter la taille de lot (128-256 KiB)
- **Stockage lent** : Diminuer la taille de lot (32-64 KiB)
- **Données critiques** : Activer sync_writes
- **Performances** : Désactiver sync_writes

Taille de lot d'écriture : [ccbt.toml:63](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L63)

Taille du tampon d'écriture : [ccbt.toml:64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L64)

Paramètre écritures synchronisées : [ccbt.toml:82](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L82)

Assembleur de fichiers : [ccbt/storage/file_assembler.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/file_assembler.py)

### Mappage Mémoire

Configuration : [ccbt.toml:65-66](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L65-L66)

**Avantages :**
- Lectures plus rapides pour les pièces complétées
- Utilisation réduite de la mémoire
- Meilleur cache du système d'exploitation

**Considérations :**
- Nécessite suffisamment de RAM
- Peut causer une pression mémoire
- Idéal pour les charges de travail intensives en lecture

Utiliser MMAP : [ccbt.toml:65](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L65)

Taille du cache MMAP : [ccbt.toml:66](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L66)

Intervalle de nettoyage du cache MMAP : [ccbt.toml:67](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L67)

### Fonctionnalités E/S Avancées

#### io_uring (Linux)

Configuration : [ccbt.toml:84](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L84)

**Exigences :**
- Noyau Linux 5.1+
- Dispositifs de stockage modernes
- Ressources système suffisantes

#### E/S Directe

Configuration : [ccbt.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L81)

**Cas d'Utilisation :**
- Stockage haute performance
- Contourner le cache de pages du système d'exploitation
- Performances constantes

Taille de lecture anticipée : [ccbt.toml:83](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L83)

## Sélection de Stratégie

### Algorithmes de Sélection de Pièces

Configuration : [ccbt.toml:101](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L101)

#### Rarest-First (Recommandé)

**Avantages :**
- Santé optimale de l'essaim
- Temps de complétion plus rapides
- Meilleure coopération entre pairs

Implémentation : [ccbt/piece/async_piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py) - Logique de sélection de pièces

Seuil rarest first : [ccbt.toml:107](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L107)

#### Séquentiel

**Cas d'Utilisation :**
- Fichiers multimédias en streaming
- Modèles d'accès séquentiel
- Téléchargements basés sur la priorité

Fenêtre séquentielle : [ccbt.toml:108](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L108)

Mode streaming : [ccbt.toml:104](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L104)

#### Round-Robin

**Cas d'Utilisation :**
- Scénarios simples
- Débogage
- Compatibilité héritée

Implémentation : [ccbt/piece/piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/piece_manager.py)

### Optimisation de Fin de Partie

Configuration : [ccbt.toml:102-103](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L102-L103)

**Ajustement :**
- **Connexions rapides** : Seuil plus bas (0.85-0.9)
- **Connexions lentes** : Seuil plus haut (0.95-0.98)
- **Beaucoup de pairs** : Augmenter les doublons (3-5)
- **Peu de pairs** : Diminuer les doublons (1-2)

Seuil de fin de partie : [ccbt.toml:103](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L103)

Doublons de fin de partie : [ccbt.toml:102](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L102)

Capacité du pipeline : [ccbt.toml:109](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L109)

### Priorités de Pièces

Configuration : [ccbt.toml:112-113](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L112-L113)

Priorité de la première pièce : [ccbt.toml:112](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L112)

Priorité de la dernière pièce : [ccbt.toml:113](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L113)

## Limitation de Débit

### Limites Globales

Configuration : [ccbt.toml:140-141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L140-L141)

Limite globale de téléchargement : [ccbt.toml:140](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L140) (0 = illimité)

Limite globale de téléversement : [ccbt.toml:141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L141) (0 = illimité)

Limites au niveau réseau : [ccbt.toml:39-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L39-L42)

Implémentation : [ccbt/security/rate_limiter.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/rate_limiter.py) - Logique de limitation de débit

### Limites par Torrent

Définir les limites via CLI en utilisant [ccbt/cli/main.py:download](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L369) avec les options `--download-limit` et `--upload-limit`.

Configuration par torrent : [ccbt.toml:144-145](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L144-L145)

Limites par pair : [ccbt.toml:148](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L148)

### Paramètres du Planificateur

Tranche de temps du planificateur : [ccbt.toml:151](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L151)

## Vérification de Hash

### Threads de Travail

Configuration : [ccbt.toml:70](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L70)

**Lignes Directrices d'Ajustement :**
- **Cœurs CPU** : Correspondre ou dépasser le nombre de cœurs
- **Stockage SSD** : Peut gérer plus de workers
- **Stockage HDD** : Limiter les workers (2-4)

Taille de fragment de hash : [ccbt.toml:71](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L71)

Taille de lot de hash : [ccbt.toml:72](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L72)

Taille de la file d'attente de hash : [ccbt.toml:73](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L73)

Implémentation : [ccbt/storage/disk_io.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/disk_io.py) - Workers de vérification de hash

## Gestion de la Mémoire

### Tailles de Tampon

Tampon d'écriture : [ccbt.toml:64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L64)

Lecture anticipée : [ccbt.toml:83](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L83)

### Paramètres de Cache

Taille du cache : [ccbt.toml:78](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L78)

Cache MMAP : [ccbt.toml:66](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L66)

Taille de la file d'attente disque : [ccbt.toml:77](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L77)

Workers disque : [ccbt.toml:76](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L76)

## Optimisation au Niveau Système

### Ajustement du Système de Fichiers

Pour les optimisations au niveau système, consultez la documentation de votre système d'exploitation. Ce sont des recommandations générales qui s'appliquent en dehors de la configuration de ccBitTorrent.

### Ajustement de la Pile Réseau

Pour les optimisations de la pile réseau, consultez la documentation de votre système d'exploitation. Ce sont des paramètres au niveau système qui affectent les performances réseau globales.

## Surveillance des Performances

### Métriques Clés

Surveiller ces métriques clés via Prometheus :

- **Vitesse de Téléchargement** : `ccbt_download_rate_bytes_per_second` - Voir [ccbt/utils/metrics.py:142](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/metrics.py#L142)
- **Vitesse de Téléversement** : `ccbt_upload_rate_bytes_per_second` - Voir [ccbt/utils/metrics.py:148](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/metrics.py#L148)
- **Pairs Connectés** : Disponible via MetricsCollector
- **Profondeur de la File d'Attente Disque** : Disponible via MetricsCollector - Voir [ccbt/monitoring/metrics_collector.py]
- **Profondeur de la File d'Attente Hash** : Disponible via MetricsCollector

Point de terminaison des métriques Prometheus : [ccbt/utils/metrics.py:179](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/utils/metrics.py#L179)

### Profilage des Performances

Activer les métriques : [ccbt.toml:164](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L164)

Port des métriques : [ccbt.toml:165](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L165)

Accéder aux métriques à `http://localhost:9090/metrics` lorsqu'il est activé.

Voir les métriques via CLI : [ccbt/cli/monitoring_commands.py:metrics](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L229)

## Dépannage des Problèmes de Performances

### Vitesses de Téléchargement Faibles

1. **Vérifier les connexions de pairs** :
   Lancer le tableau de bord Bitonic : [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L20)

2. **Vérifier la sélection de pièces** :
   Configurer dans [ccbt.toml:101](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L101)
   
   Implémentation : [ccbt/piece/async_piece_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/piece/async_piece_manager.py)

3. **Augmenter la profondeur du pipeline** :
   Configurer dans [ccbt.toml:12](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L12)
   
   Implémentation : [ccbt/peer/async_peer_connection.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/peer/async_peer_connection.py)

4. **Vérifier les limites de débit** :
   Configuration : [ccbt.toml:140-141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L140-L141)
   
   Commande de statut CLI : [ccbt/cli/main.py:status](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/main.py#L789)

### Utilisation CPU Élevée

1. **Réduire les workers de hash** :
   Configurer dans [ccbt.toml:70](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L70)

2. **Désactiver le mappage mémoire** :
   Configurer dans [ccbt.toml:65](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L65)

3. **Augmenter les intervalles de rafraîchissement** :
   Intervalle de rafraîchissement Bitonic : [ccbt/interface/terminal_dashboard.py:303](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L303)
   
   Configuration du tableau de bord : [ccbt.toml:189](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L189)

### Goulots d'Étranglement E/S Disque

1. **Activer l'écriture par lots** :
   Configurer la taille de lot d'écriture : [ccbt.toml:63](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L63)
   
   Implémentation : [ccbt/storage/disk_io.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/storage/disk_io.py)

2. **Utiliser un stockage plus rapide** :
   - Déplacer les téléchargements vers SSD
   - Utiliser RAID 0 pour les performances

3. **Optimiser le système de fichiers** :
   - Utiliser un système de fichiers approprié
   - Ajuster les options de montage

## Benchmarking

### Scripts de Benchmark

Les scripts de benchmark de performance se trouvent dans `tests/performance/` :

- Vérification de hash : `tests/performance/bench_hash_verify.py`
- E/S disque : `tests/performance/bench_disk_io.py`
- Assemblage de pièces : `tests/performance/bench_piece_assembly.py`
- Débit loopback : `tests/performance/bench_loopback_throughput.py`
- Chiffrement : `tests/performance/bench_encryption.py`

Exécuter tous les benchmarks : [tests/scripts/bench_all.py](https://github.com/ccBittorrent/ccbt/blob/main/tests/scripts/bench_all.py)

Exemple de configuration de benchmark : [example-config-performance.toml](examples/example-config-performance.toml)

### Enregistrement de Benchmark

Les benchmarks peuvent être enregistrés avec différents modes pour suivre les performances dans le temps :

#### Modes d'Enregistrement

- **`pre-commit`** : Enregistre pendant les exécutions de hook pre-commit (tests rapides de fumée)
- **`commit`** : Enregistre pendant les commits réels (benchmarks complets, enregistrés à la fois par exécution et en séries temporelles)
- **`both`** : Enregistre dans les contextes pre-commit et commit
- **`auto`** : Détecte automatiquement le contexte (utilise la variable d'environnement `PRE_COMMIT`)
- **`none`** : Aucun enregistrement (le benchmark s'exécute mais ne sauvegarde pas les résultats)

#### Exécution de Benchmarks avec Enregistrement

```bash
# Mode pre-commit (test rapide de fumée)
uv run python tests/performance/bench_hash_verify.py --quick --record-mode=pre-commit

# Mode commit (benchmark complet)
uv run python tests/performance/bench_hash_verify.py --record-mode=commit

# Les deux modes
uv run python tests/performance/bench_hash_verify.py --record-mode=both

# Mode auto-détection (par défaut)
uv run python tests/performance/bench_hash_verify.py --record-mode=auto
```

#### Stockage des Données de Benchmark

Les résultats de benchmark sont stockés en deux formats :

1. **Fichiers par exécution** (`docs/reports/benchmarks/runs/`) :
   - Fichiers JSON individuels pour chaque exécution de benchmark
   - Format de nom de fichier : `{benchmark_name}-{timestamp}-{commit_hash_short}.json`
   - Contient des métadonnées complètes : hash de commit git, branche, auteur, informations de plateforme, résultats

2. **Fichiers de séries temporelles** (`docs/reports/benchmarks/timeseries/`) :
   - Données historiques agrégées au format JSON
   - Format de nom de fichier : `{benchmark_name}_timeseries.json`
   - Permet une interrogation facile des tendances de performance dans le temps

Pour des informations détaillées sur l'interrogation des données historiques et les rapports de benchmark, voir [Rapports de Benchmark](reports/benchmarks/index.md).

### Artefacts de Test et de Couverture

Lors de l'exécution de la suite de tests complète (pre-push/CI), les artefacts sont émis vers :

- `tests/.reports/junit.xml` (rapport JUnit)
- `tests/.reports/pytest.log` (journaux de test)
- `coverage.xml` et `htmlcov/` (rapports de couverture)

Ceux-ci s'intègrent avec Codecov ; les drapeaux dans `dev/.codecov.yml` sont alignés sur les sous-paquets `ccbt/` pour attribuer la couverture avec précision (ex. `peer`, `piece`, `protocols`, `extensions`). Le rapport HTML de couverture est automatiquement intégré dans la documentation via le plugin `mkdocs-coverage`, qui lit depuis `site/reports/htmlcov/` et le rend dans [reports/coverage.md](reports/coverage.md).

#### Artefacts de Benchmark Hérités

Les artefacts de benchmark hérités sont toujours écrits dans `site/reports/benchmarks/artifacts/` pour la compatibilité ascendante lors de l'utilisation de l'argument `--output-dir`. Cependant, le nouveau système d'enregistrement est recommandé pour suivre les performances dans le temps.

## Meilleures Pratiques

1. **Commencer avec les valeurs par défaut** : Commencer avec les paramètres par défaut de [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
2. **Mesurer la ligne de base** : Établir la ligne de base de performance en utilisant [ccbt/cli/monitoring_commands.py:metrics](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L229)
3. **Changer un paramètre** : Modifier un paramètre à la fois dans [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)
4. **Tester minutieusement** : Vérifier les améliorations
5. **Surveiller les ressources** : Surveiller l'utilisation CPU, mémoire, disque via [Bitonic](bitonic.md)
6. **Documenter les changements** : Garder une trace des paramètres efficaces

## Modèles de Configuration

### Configuration Haute Performance

Référence du modèle de configuration haute performance : [ccbt/config/config_templates.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_templates.py)

Paramètres clés :
- Réseau : [ccbt.toml:11-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L11-L42)
- Disque : [ccbt.toml:57-85](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L57-L85)
- Stratégie : [ccbt.toml:99-114](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L99-L114)

Exemple : [example-config-performance.toml](examples/example-config-performance.toml)

### Configuration à Faibles Ressources

Référence du modèle de configuration à faibles ressources : [ccbt/config/config_templates.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_templates.py)

Paramètres clés :
- Réseau : [ccbt.toml:6-7](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L6-L7) - Réduire les limites de pairs
- Disque : [ccbt.toml:59-65](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L59-L65) - Utiliser la préallocation sparse, désactiver MMAP
- Stratégie : [ccbt.toml:101](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L101) - Rarest-first reste optimal

Pour des options de configuration plus détaillées, voir la documentation de [Configuration](configuration.md).
