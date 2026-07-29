# Guide de Configuration

ccBitTorrent utilise un système de configuration complet avec support TOML, validation, rechargement à chaud et chargement hiérarchique depuis plusieurs sources.

Système de configuration : [ccbt/config/config.py:ConfigManager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L40)

## Sources de Configuration et Priorité

La configuration est chargée dans cet ordre (les sources ultérieures remplacent les précédentes) :

1. **Valeurs par Défaut** : Valeurs par défaut intégrées sensées de [ccbt/models.py:Config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)
2. **Fichier de Configuration** : `ccbt.toml` dans le répertoire actuel ou `~/.config/ccbt/ccbt.toml`. Voir [ccbt/config/config.py:_find_config_file](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L55)
3. **Variables d'Environnement** : Variables préfixées `CCBT_*`. Voir [env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example)
4. **Arguments CLI** : Remplacements en ligne de commande. Voir [ccbt/cli/overrides.py:apply_cli_overrides](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/overrides.py#L1) {#cli-overrides}
5. **Par Torrent - Valeurs par Défaut** : Valeurs par défaut globales pour les options par torrent. Voir la section [Configuration par Torrent](#per-torrent-configuration)
6. **Par Torrent - Remplacements** : Paramètres individuels de torrent (définis via CLI, TUI ou programmatiquement)

Chargement de la configuration : [ccbt/config/config.py:_load_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L76)

### Résolution de Chemins Windows {#daemon-home-dir}

**CRITIQUE** : Utilisez l'aide `_get_daemon_home_dir()` de `ccbt/daemon/daemon_manager.py` pour tous les chemins liés au démon.

**Pourquoi** : Windows peut résoudre `Path.home()` ou `os.path.expanduser("~")` différemment dans différents processus, notamment avec des espaces dans les noms d'utilisateur.

**Modèle** : L'aide essaie plusieurs méthodes (`expanduser`, `USERPROFILE`, `HOME`, `Path.home()`) et utilise `Path.resolve()` pour le chemin canonique.

**Utilisation** : Utilisez toujours l'aide au lieu de `Path.home()` ou `os.path.expanduser("~")` directement pour les fichiers PID du démon, les répertoires d'état, les fichiers de configuration.

**Fichiers affectés** : `DaemonManager`, `StateManager`, `IPCClient`, tout code qui lit/écrit le fichier PID du démon ou l'état.

**Résultat** : Garantit que le démon et la CLI utilisent le même chemin canonique, évitant les échecs de détection.

Implémentation : [ccbt/daemon/daemon_manager.py:_get_daemon_home_dir](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/daemon_manager.py#L25)

## Fichier de Configuration

### Configuration par Défaut

Référencez le fichier de configuration par défaut : [ccbt.toml](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml)

La configuration est organisée en sections :

### Configuration Réseau

Paramètres réseau : [ccbt.toml:4-43](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L4-L43)

- Limites de connexion : [ccbt.toml:6-8](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L6-L8)
- Pipeline de requêtes : [ccbt.toml:11-14](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L11-L14)
- Réglage de socket : [ccbt.toml:17-19](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L17-L19)
- Timeouts : [ccbt.toml:22-26](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L22-L26)
- Paramètres d'écoute : [ccbt.toml:29-31](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L29-L31)
- Protocoles de transport : [ccbt.toml:34-36](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L34-L36)
- Limites de débit : [ccbt.toml:39-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L39-L42)
- Stratégie de choking : [ccbt.toml:45-47](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L45-L47)
- Paramètres de tracker : [ccbt.toml:50-54](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L50-L54)

Modèle de configuration réseau : [ccbt/models.py:NetworkConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuration Disque

Paramètres disque : [ccbt.toml:57-96](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L57-L96)

- Préallocation : [ccbt.toml:59-60](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L59-L60)
- Optimisation d'écriture : [ccbt.toml:63-67](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L63-L67)
- Vérification de hash : [ccbt.toml:70-73](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L70-L73)
- Threading I/O : [ccbt.toml:76-78](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L76-L78)
- Paramètres avancés : [ccbt.toml:81-85](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L81-L85)
- Paramètres du service de stockage : [ccbt.toml:87-89](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L87-L89)
  - `max_file_size_mb` : Limite de taille de fichier maximale en MB pour le service de stockage (0 ou None = illimité, max 1048576 = 1TB). Empêche les écritures disque illimitées pendant les tests et peut être configuré pour une utilisation en production.
- Paramètres de checkpoint : [ccbt.toml:91-96](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L91-L96)

Modèle de configuration disque : [ccbt/models.py:DiskConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuration de Stratégie

Paramètres de stratégie : [ccbt.toml:99-114](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L99-L114)

- Sélection de pièces : [ccbt.toml:101-104](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L101-L104)
- Stratégie avancée : [ccbt.toml:107-109](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L107-L109)
- Priorités de pièces : [ccbt.toml:112-113](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L112-L113)

Modèle de configuration de stratégie : [ccbt/models.py:StrategyConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuration de Découverte

Paramètres de découverte : [ccbt.toml:116-136](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L116-L136)

- Paramètres DHT : [ccbt.toml:118-125](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L118-L125)
- Paramètres PEX : [ccbt.toml:128-129](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L128-L129)
- Paramètres de tracker : [ccbt.toml:132-135](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L132-L135)
  - `tracker_announce_interval` : Intervalle d'annonce du tracker en secondes (par défaut : 1800.0, plage : 60.0-86400.0)
  - `tracker_scrape_interval` : Intervalle de scrape du tracker en secondes pour le scraping périodique (par défaut : 3600.0, plage : 60.0-86400.0)
  - `tracker_auto_scrape` : Scraper automatiquement les trackers lorsque des torrents sont ajoutés (BEP 48) (par défaut : false)
  - Variables d'environnement : `CCBT_TRACKER_ANNOUNCE_INTERVAL`, `CCBT_TRACKER_SCRAPE_INTERVAL`, `CCBT_TRACKER_AUTO_SCRAPE`

Modèle de configuration de découverte : [ccbt/models.py:DiscoveryConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuration des Limites

Limites de débit : [ccbt.toml:138-152](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L138-L152)

- Limites globales : [ccbt.toml:140-141](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L140-L141)
- Limites par torrent : [ccbt.toml:144-145](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L144-L145)
- Limites par pair : [ccbt.toml:148](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L148)
- Paramètres du planificateur : [ccbt.toml:151](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L151)

Modèle de configuration des limites : [ccbt/models.py:LimitsConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuration d'Observabilité

Paramètres d'observabilité : [ccbt.toml:154-171](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L154-L171)

- Journalisation : [ccbt.toml:156-160](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L156-L160)
- Métriques : [ccbt.toml:163-165](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L163-L165)
- Traçage et alertes : [ccbt.toml:168-170](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L168-L170)

Modèle de configuration d'observabilité : [ccbt/models.py:ObservabilityConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuration d'Optimisation {#optimization-profile}

Les profils d'optimisation fournissent des paramètres préconfigurés pour différents cas d'utilisation.

::: ccbt.models.OptimizationProfile
    options:
      show_source: true
      show_signature: true
      show_root_heading: false
      heading_level: 3

**Profils Disponibles :**
- `BALANCED` : Performance et utilisation des ressources équilibrées (par défaut)
- `SPEED` : Vitesse de téléchargement maximale
- `EFFICIENCY` : Efficacité de bande passante maximale
- `LOW_RESOURCE` : Optimisé pour les systèmes à faibles ressources
- `CUSTOM` : Utiliser des paramètres personnalisés sans remplacements de profil

Modèle de configuration d'optimisation : [ccbt/models.py:OptimizationConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuration de Sécurité

Paramètres de sécurité : [ccbt.toml:173-178](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L173-L178)

Modèle de configuration de sécurité : [ccbt/models.py:SecurityConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

#### Configuration du Chiffrement

ccBitTorrent prend en charge BEP 3 Message Stream Encryption (MSE) et Protocol Encryption (PE) pour des connexions de pairs sécurisées.

**Paramètres de Chiffrement :**

- `enable_encryption` (bool, par défaut : `false`) : Activer le support du chiffrement de protocole
- `encryption_mode` (str, par défaut : `"preferred"`) : Mode de chiffrement
  - `"disabled"` : Pas de chiffrement (connexions en clair uniquement)
  - `"preferred"` : Tenter le chiffrement, repli en clair si indisponible
  - `"required"` : Chiffrement obligatoire, la connexion échoue si le chiffrement est indisponible
- `encryption_dh_key_size` (int, par défaut : `768`) : Taille de clé Diffie-Hellman en bits (768 ou 1024)
- `encryption_prefer_rc4` (bool, par défaut : `true`) : Préférer le chiffrement RC4 pour la compatibilité avec les anciens clients
- `encryption_allowed_ciphers` (list[str], par défaut : `["rc4", "aes"]`) : Types de chiffrement autorisés
  - `"rc4"` : Chiffrement de flux RC4 (le plus compatible)
  - `"aes"` : Chiffrement AES en mode CFB (plus sécurisé)
  - `"chacha20"` : Chiffrement ChaCha20 (pas encore implémenté)
- `encryption_allow_plain_fallback` (bool, par défaut : `true`) : Autoriser le repli en connexion en clair si le chiffrement échoue (s'applique uniquement lorsque `encryption_mode` est `"preferred"`)

**Variables d'Environnement :**

- `CCBT_ENABLE_ENCRYPTION` : Activer/désactiver le chiffrement (`true`/`false`)
- `CCBT_ENCRYPTION_MODE` : Mode de chiffrement (`disabled`/`preferred`/`required`)
- `CCBT_ENCRYPTION_DH_KEY_SIZE` : Taille de clé DH (`768` ou `1024`)
- `CCBT_ENCRYPTION_PREFER_RC4` : Préférer RC4 (`true`/`false`)
- `CCBT_ENCRYPTION_ALLOWED_CIPHERS` : Liste séparée par des virgules (ex. `"rc4,aes"`)
- `CCBT_ENCRYPTION_ALLOW_PLAIN_FALLBACK` : Autoriser le repli en clair (`true`/`false`)

**Exemple de Configuration :**

```toml
[security]
enable_encryption = true
encryption_mode = "preferred"
encryption_dh_key_size = 768
encryption_prefer_rc4 = true
encryption_allowed_ciphers = ["rc4", "aes"]
encryption_allow_plain_fallback = true
```

**Considérations de Sécurité :**

1. **Compatibilité RC4** : RC4 est pris en charge pour la compatibilité mais est cryptographiquement faible. Utilisez AES pour une meilleure sécurité lorsque possible.
2. **Taille de Clé DH** : Les clés DH de 768 bits fournissent une sécurité adéquate pour la plupart des cas d'usage. 1024 bits fournit une sécurité plus forte mais augmente la latence du handshake.
3. **Modes de Chiffrement** :
   - `preferred` : Meilleur pour la compatibilité - tente le chiffrement mais replie élégamment
   - `required` : Le plus sécurisé mais peut échouer à se connecter avec des pairs qui ne supportent pas le chiffrement
4. **Impact sur les Performances** : Le chiffrement ajoute une surcharge minimale (~1-5% pour RC4, ~2-8% pour AES) mais améliore la confidentialité et aide à éviter le traffic shaping.

**Détails d'Implémentation :**

Implémentation du chiffrement : [ccbt/security/encryption.py:EncryptionManager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/encryption.py#L131)

- Handshake MSE : [ccbt/security/mse_handshake.py:MSEHandshake](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/mse_handshake.py#L45)
- Suites de Chiffrement : [ccbt/security/ciphers/__init__.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/ciphers/__init__.py) (RC4, AES)
- Échange Diffie-Hellman : [ccbt/security/dh_exchange.py:DHPeerExchange](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/security/dh_exchange.py)

### Configuration ML

Paramètres de machine learning : [ccbt.toml:180-183](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L180-L183)

Modèle de configuration ML : [ccbt/models.py:MLConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Configuration du Tableau de Bord

Paramètres du tableau de bord : [ccbt.toml:185-191](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L185-L191)

Modèle de configuration du tableau de bord : [ccbt/models.py:DashboardConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

## Variables d'Environnement

Les variables d'environnement utilisent le préfixe `CCBT_` et suivent un schéma de nommage hiérarchique.

Référence : [env.example](https://github.com/ccBittorrent/ccbt/blob/main/env.example)

Format : `CCBT_<SECTION>_<OPTION>=<value>`

Exemples :
- Réseau : [env.example:10-58](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L10-L58)
- Disque : [env.example:62-102](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L62-L102)
- Stratégie : [env.example:106-121](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L106-L121)
- Découverte : [env.example:125-141](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L125-L141)
- Observabilité : [env.example:145-162](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L145-L162)
- Limites : [env.example:166-180](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L166-L180)
- Sécurité : [env.example:184-189](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L184-L189)
- ML : [env.example:193-196](https://github.com/ccBittorrent/ccbt/blob/main/env.example#L193-L196)

Analyse des variables d'environnement : [ccbt/config/config.py:_get_env_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py)

## Schéma de Configuration

Schéma de configuration et validation : [ccbt/config/config_schema.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_schema.py)

Le schéma définit :
- Types de champs et contraintes
- Valeurs par défaut
- Règles de validation
- Documentation

## Capacités de Configuration

Capacités de configuration et détection de fonctionnalités : [ccbt/config/config_capabilities.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_capabilities.py)

## Modèles de Configuration

Modèles de configuration prédéfinis : [ccbt/config/config_templates.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_templates.py)

Modèles pour :
- Configuration haute performance
- Configuration à faible ressource
- Configuration axée sur la sécurité
- Configuration de développement

## Exemples de Configuration

Les configurations d'exemple sont disponibles dans le répertoire [examples/](examples/) :

- Configuration de base : [example-config-basic.toml](examples/example-config-basic.toml)
- Configuration avancée : [example-config-advanced.toml](examples/example-config-advanced.toml)
- Configuration de performance : [example-config-performance.toml](examples/example-config-performance.toml)
- Configuration de sécurité : [example-config-security.toml](examples/example-config-security.toml)

## Rechargement à Chaud

Support du rechargement à chaud de la configuration : [ccbt/config/config.py:ConfigManager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config.py#L40)

Le système de configuration prend en charge le rechargement des modifications sans redémarrer le client.

## Migration de Configuration

Utilitaires de migration de configuration : [ccbt/config/config_migration.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_migration.py)

Outils pour migrer entre les versions de configuration.

## Sauvegarde et Diff de Configuration

Utilitaires de gestion de configuration :
- Sauvegarde : [ccbt/config/config_backup.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_backup.py)
- Diff : [ccbt/config/config_diff.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_diff.py)

## Configuration Conditionnelle

Support de configuration conditionnelle : [ccbt/config/config_conditional.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/config/config_conditional.py)

## Configuration par Torrent

La configuration par torrent vous permet de remplacer les paramètres globaux pour des torrents individuels. Ces paramètres sont persistés dans les points de contrôle et l'état du démon, garantissant qu'ils survivent aux redémarrages.

### Options par Torrent

Les options par torrent sont stockées dans `AsyncTorrentSession.options` et peuvent inclure :

- `piece_selection` : Stratégie de sélection de pièces (`"rarest_first"`, `"sequential"`, `"random"`)
- `streaming_mode` : Activer le mode streaming pour les fichiers multimédias (`true`/`false`)
- `sequential_window_size` : Taille de la fenêtre de téléchargement séquentiel (octets)
- `max_peers_per_torrent` : Nombre maximum de pairs pour ce torrent
- Options personnalisées selon les besoins

Implémentation : [ccbt/session/session.py:AsyncTorrentSession](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py#L63)

### Limites de Débit par Torrent

Les limites de débit peuvent être définies par torrent en utilisant `AsyncSessionManager.set_rate_limits()` :

- `down_kib` : Limite de débit de téléchargement en KiB/s (0 = illimité)
- `up_kib` : Limite de débit d'upload en KiB/s (0 = illimité)

Implémentation : [ccbt/session/session.py:set_rate_limits](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py#L1735)

### Valeurs par Défaut Globales par Torrent

Vous pouvez définir des options par défaut par torrent dans votre fichier `ccbt.toml` :

```toml
[per_torrent_defaults]
piece_selection = "rarest_first"
streaming_mode = false
max_peers_per_torrent = 50
sequential_window_size = 10485760  # 10 MiB
```

Ces valeurs par défaut sont fusionnées dans les options de chaque torrent lorsque la session torrent est créée.

Modèle : [ccbt/models.py:PerTorrentDefaultsConfig](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py)

### Définir les Options par Torrent

#### Via CLI

```bash
# Définir une option par torrent
uv run btbt torrent config set <info_hash> piece_selection sequential

# Définir les limites de débit (via le gestionnaire de session)
# Note : Les limites de débit sont généralement définies via la TUI ou programmatiquement
```

Voir [Référence CLI](btbt-cli.md#per-torrent-configuration) pour la documentation CLI complète.

#### Via TUI

Le tableau de bord terminal fournit une interface interactive pour gérer la configuration par torrent :

- Naviguer vers l'écran de configuration torrent
- Modifier les options et les limites de débit
- Les modifications sont automatiquement enregistrées dans les points de contrôle

Implémentation : [ccbt/interface/screens/config/torrent_config.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/screens/config/torrent_config.py)

#### Programmatiquement

```python
# Définir les options par torrent
torrent_session.options["piece_selection"] = "sequential"
torrent_session.options["streaming_mode"] = True
torrent_session._apply_per_torrent_options()

# Définir les limites de débit
await session_manager.set_rate_limits(info_hash_hex, down_kib=100, up_kib=50)
```

### Persistance

La configuration par torrent est persistée dans :

1. **Points de Contrôle** : Enregistrés automatiquement lorsque les points de contrôle sont créés. Restaurés lors de la reprise depuis un point de contrôle.
   - Modèle : [ccbt/models.py:TorrentCheckpoint](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/models.py#L2017)
   - Enregistrer : [ccbt/session/checkpointing.py:save_checkpoint_state](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/checkpointing.py)
   - Charger : [ccbt/session/session.py:_resume_from_checkpoint](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py#L947)

2. **État du Démon** : Enregistré lorsque l'état du démon est persisté. Restauré lors du redémarrage du démon.
   - Modèle : [ccbt/daemon/state_models.py:TorrentState](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/state_models.py)
   - Enregistrer : [ccbt/daemon/state_manager.py:_build_state](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/state_manager.py#L212)
   - Charger : [ccbt/daemon/main.py:_restore_torrent_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/daemon/main.py#L29)

## Conseils et Meilleures Pratiques

### Réglage des Performances

- Augmentez `disk.write_buffer_kib` pour les grandes écritures séquentielles : [ccbt.toml:64](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L64)
- Activez `direct_io` sur Linux/NVMe pour un meilleur débit d'écriture : [ccbt.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L81)
- Ajustez `network.pipeline_depth` et `network.block_size_kib` pour votre réseau : [ccbt.toml:11-13](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L11-L13)

### Optimisation des Ressources

- Ajustez `disk.hash_workers` en fonction des cœurs CPU : [ccbt.toml:70](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L70)
- Configurez `disk.cache_size_mb` en fonction de la RAM disponible : [ccbt.toml:78](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L78)
- Définissez `network.max_global_peers` en fonction de la bande passante : [ccbt.toml:6](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L6)

### Configuration Réseau

- Configurez les timeouts en fonction des conditions réseau : [ccbt.toml:22-26](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L22-L26)
- Activez/désactivez les protocoles selon les besoins : [ccbt.toml:34-36](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L34-L36)
- Définissez les limites de débit de manière appropriée : [ccbt.toml:39-42](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L39-L42)

Pour un réglage détaillé des performances, consultez le [Guide de Réglage des Performances](performance.md).
