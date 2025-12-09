# Bitonic - Tableau de Bord Terminal

**Bitonic** est le point d'entrée principal de ccBitTorrent, fournissant un tableau de bord terminal interactif en direct pour surveiller et gérer les torrents, les pairs, les vitesses et les métriques système.

- Point d'entrée : [ccbt/interface/terminal_dashboard.py:main](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3914)
- Défini dans : [pyproject.toml:81](https://github.com/ccBittorrent/ccbt/blob/main/pyproject.toml#L81)
- Classe principale : [ccbt/interface/terminal_dashboard.py:TerminalDashboard](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3009)

## Lancement de Bitonic

Lancez Bitonic en utilisant le point d'entrée dédié :
```bash
uv run bitonic
```

Ou via la CLI :
```bash
uv run ccbt dashboard
```

Avec options :
```bash
# Intervalle de rafraîchissement personnalisé (secondes)
uv run bitonic --refresh 2.0

# Via CLI avec règles d'alerte
uv run ccbt dashboard --rules /path/to/alert-rules.json
```

Implémentation : [ccbt/cli/monitoring_commands.py:dashboard](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/cli/monitoring_commands.py#L20)

## Exemple Complet de Parcours Utilisateur

```
Flux d'Actions Utilisateur :
─────────────────

1. L'utilisateur appuie sur 'o' (Ajout Avancé) dans le tableau de bord principal
   ↓
2. Le modal de l'écran Ajouter Torrent apparaît
   ↓
3. Étape 1 : L'utilisateur entre le lien magnétique
   → Entrée : "magnet:?xt=urn:btih:abc123..."
   → Valide : ✓ URI magnétique valide
   → Charge : Métadonnées du torrent
   → Clique sur : [Suivant]
   ↓
4. Étape 2 : L'utilisateur entre le répertoire de sortie
   → Entrée : "/home/user/downloads"
   → Clique sur : [Suivant]
   ↓
5. Étape 3 : L'utilisateur sélectionne les fichiers
   → Sélectionne : Fichiers 0, 1, 3 (ignore le fichier 2)
   → Définit : Fichier 1 priorité à "élevée"
   → Clique sur : [Suivant]
   ↓
6. Étape 4 : L'utilisateur définit les limites de débit
   → Téléchargement : 1000 KiB/s
   → Téléversement : 500 KiB/s
   → Clique sur : [Suivant]
   ↓
7. Étape 5 : L'utilisateur sélectionne la priorité de la file
   → Sélectionne : "Élevée"
   → Clique sur : [Suivant]
   ↓
8. Étape 6 : L'utilisateur active la reprise
   → Interrupteur : ACTIVÉ
   → Clique sur : [Suivant]
   ↓
9. Étape 7 : L'utilisateur active Xet avec déduplication
   → Activer Xet : ACTIVÉ
   → Déduplication : ACTIVÉ
   → P2P CAS : DÉSACTIVÉ
   → Compression : DÉSACTIVÉ
   → Clique sur : [Suivant]
   ↓
10. Étape 8 : L'utilisateur ignore IPFS
    → Activer IPFS : DÉSACTIVÉ
    → Clique sur : [Suivant]
    ↓
11. Étape 9 : L'utilisateur active l'auto-scrape
    → Auto-scrape : ACTIVÉ
    → Clique sur : [Suivant]
    ↓
12. Étape 10 : L'utilisateur active uTP
    → Activer uTP : ACTIVÉ
    → Clique sur : [Suivant]
    ↓
13. Étape 11 : L'utilisateur active le mappage NAT
    → Activer NAT : ACTIVÉ
    → Clique sur : [Envoyer]
    ↓
14. Le formulaire est soumis
    → Dictionnaire d'options construit
    → Modal fermé
    → dashboard._process_add_torrent() appelé
    → Torrent ajouté avec toutes les options spécifiées
```


## Visualisation du Tableau de Bord Terminal

### Disposition du Tableau de Bord Principal

```
┌─────────────────────────────────────────────────────────────────────────┐
│ En-tête (with clock)                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────┐  ┌──────────────────────────────────────┐ │
│  │ LEFT PANEL              │  │ RIGHT PANEL                          │ │
│  │                         │  │                                      │ │
│  │ ┌────────────────────┐  │  │ ┌──────────────────────────────────┐ │ │
│  │ │ Overview           │  │  │ │ Torrents Table                  │ │ │
│  │ │                    │  │  │ │ (2fr height)                    │ │ │
│  │ │ • Torrents         │  │  │ │                                 │ │ │
│  │ │ • Active           │  │  │ │ Hash d'Information | Nom | Statut | ... │ │ │
│  │ │ • En pause           │  │  │ │ ─────────────────────────────── │ │ │
│  │ │ • Seeding          │  │  │ │ abc123... | file.torrent | ... │ │ │
│  │ │ • Down Rate        │  │  │ │ def456... | movie.torrent | ... │ │ │
│  │ │ • Up Rate          │  │  │ │ ...                             │ │ │
│  │ │ • Avg Progression     │  │  │ │                                 │ │ │
│  │ │                    │  │  │ └──────────────────────────────────┘ │ │
│  │ └────────────────────┘  │  │                                      │ │
│  │                         │  │ ┌──────────────────────────────────┐ │ │
│  │ ┌────────────────────┐  │  │ │ Peers Table                     │ │ │
│  │ │ Speed Sparklines   │  │  │ │ (1fr height)                    │ │ │
│  │ │                    │  │  │ │                                 │ │ │
│  │ │ Téléchargement : ▁▂▃▅▆▇█  │  │  │ │ IP | Port | Down | Up | ...    │ │ │
│  │ │ Téléversement :   ▁▂▃▅▆▇█  │  │  │ │ ─────────────────────────────── │ │ │
│  │ │                    │  │  │ │ 192.168.1.1 | 6881 | ...       │ │ │
│  │ └────────────────────┘  │  │ │ ...                             │ │ │
│  │                         │  │ └──────────────────────────────────┘ │ │
│  │                         │  │                                      │ │
│  │                         │  │ ┌──────────────────────────────────┐ │ │
│  │                         │  │ │ Details                          │ │ │
│  │                         │  │ │ (1fr height)                     │ │ │
│  │                         │  │ │ Sélectionnered torrent details...     │ │ │
│  │                         │  │ └──────────────────────────────────┘ │ │
│  │                         │  │                                      │ │
│  │                         │  │ ┌──────────────────────────────────┐ │ │
│  │                         │  │ │ Logs (RichLog)                  │ │ │
│  │                         │  │ │ (1fr height)                     │ │ │
│  │                         │  │ │ [INFO] Connected to peer...     │ │ │
│  │                         │  │ │ [WARN] Tracker timeout...        │ │ │
│  │                         │  │ │ ...                             │ │ │
│  │                         │  │ └──────────────────────────────────┘ │ │
│  └──────────────────────────┘  └──────────────────────────────────────┘ │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ Statut Bar                                                              │
├─────────────────────────────────────────────────────────────────────────┤
│ Alerts Container                                                        │
├─────────────────────────────────────────────────────────────────────────┤
│ Pied de page                                                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Raccourcis Clavier

#### Actions du Tableau de Bord Principal
- `p` - Mettre en pause le torrent
- `r` - Reprendre le torrent
- `q` - Quitter
- `i` - Ajout rapide de torrent
- `o` - Ajout avancé de torrent
- `b` - Parcourir pour ajouter un torrent
- `?` - Aide

#### Configuration
- `g` - Configuration globale
- `t` - Configuration du torrent

#### Écrans de Surveillance
- `s` - Ressources Système
- `m` - Métriques de Performance
- `n` - Qualité du Réseau
- `h` - Tendances Historiques
- `a` - Tableau de Bord des Alertes
- `e` - Explorateur de Métriques
- `x` - Analyse de Sécurité

#### Gestion des Protocoles
- `Ctrl+X` - Gestion Xet
- `Ctrl+I` - Gestion IPFS
- `Ctrl+S` - Configuration SSL
- `Ctrl+P` - Configuration Proxy
- `Ctrl+R` - Résultats de Scrape
- `Ctrl+N` - Gestion NAT
- `Ctrl+U` - Configuration uTP

#### Navigation
- `Ctrl+M` - Menu de Navigation

## Ajouter un Torrent 

L'écran Ajouter Torrent est un formulaire modal complet en 11 étapes qui guide les utilisateurs pour ajouter un torrent avec toutes les options de configuration disponibles. Il fournit une interface structurée et conviviale pour configurer les téléchargements de torrents avec des fonctionnalités avancées.

### Flux de Processus

```
┌─────────────────────────────────────────────────────────────┐
│                    Processus d'Ajout de Torrent                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Étape 1 : Entrée Torrent                                      │
│    ↓                                                        │
│  Étape 2 : Répertoire de Sortie                                    │
│    ↓                                                        │
│  Step 3: Fichier Sélectionnerion (if applicable)                     │
│    ↓                                                        │
│  Étape 4 : Limites de Débit                                        │
│    ↓                                                        │
│  Étape 5 : Priorité de la File                                     │
│    ↓                                                        │
│  Étape 6 : Option de Reprise                                      │
│    ↓                                                        │
│  Étape 7 : Options du Protocole Xet                               │
│    ↓                                                        │
│  Étape 8 : Options du Protocole IPFS                              │
│    ↓                                                        │
│  Étape 9 : Options de Scrape                                     │
│    ↓                                                        │
│  Étape 10 : Options du Protocole uTP                              │
│    ↓                                                        │
│  Étape 11 : Options de Traversée NAT                             │
│    ↓                                                        │
│  Envoyer → Traiter l'Ajout de Torrent                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Étape 1 : Entrée Torrent

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1/11: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Entrez le chemin vers un fichier .torrent ou un lien magnétique :    │ │
│ │                                                         │ │
│ │ Exemples :                                               │ │
│ │   /path/to/file.torrent                                │ │
│ │   magnet:?xt=urn:btih:...                              │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [magnet:?xt=urn:btih:abc123def456...________________]  │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Annuler]                    [Précédent] [Suivant]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Fonctionnalités :
- Champ de saisie pour torrent path or magnet URI
- Texte d'aide avec exemples
- Validation : Doit être non vide et valide torrent/magnet
- Sur Suivant : Charge les données du torrent pour les étapes suivantes
- Clavier : Le champ de saisie est automatiquement mis en focus
```

### Étape 2 : Répertoire de Sortie

```
┌─────────────────────────────────────────────────────────────┐
│ Step 2/11: ✓ → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Entrez le répertoire où les fichiers doivent être téléchargés :  │ │
│ │                                                         │ │
│ │ Laissez vide pour utiliser le répertoire actuel.                  │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [/home/user/downloads_____________________________]     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Annuler]                    [Précédent] [Suivant]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Fonctionnalités :
- Champ de saisie pour output directory path
- Par défaut : Répertoire actuel (.)
- Texte d'aide expliquant comportement par défaut
- Validation : Chemin du répertoire (validé lors de la soumission)
- Clavier : Le champ de saisie est automatiquement mis en focus
```

### Step 3: Fichier Sélectionnerion

```
┌─────────────────────────────────────────────────────────────┐
│ Step 3/11: ✓ → ✓ → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Sélectionnez les fichiers à télécharger et définissez les priorités :            │ │
│ │   Espace : Basculer la sélection                               │ │
│ │   P : Changer la priorité                                    │ │
│ │   A : Tout sélectionner                                        │ │
│ │   D : Tout désélectionner                                      │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Sélectionner  Priorité  Taille        Fichier Nom                 │ │
│ │ ──────────────────────────────────────────────────────── │ │
│ │ ✓        normal    500.00 MB  movie.mp4                │ │
│ │ ✓        high      1.20 GB    movie.mkv                │ │
│ │          normal    300.00 MB  subtitles.srt            │ │
│ │ ✓        low       800.00 MB  trailer.avi              │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Annuler]                    [Précédent] [Suivant]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Fonctionnalités :
- DataTable affichant tous les fichiers du torrent
- Colonnes : Sélectionner (✓/space), Priorité, Taille, Fichier Nom
- Sélection interactive avec raccourcis clavier
- Par défaut : Tous les fichiers sélectionnés avec priorité "normale"
- Validation : Aucune (étape optionnelle)
- Cas Spéciaux :
  - Si le torrent n'a pas de fichiers : Affiche "Ce torrent n'a pas de fichiers à sélectionner"
  - Si les données du torrent ne sont pas chargées : Affiche une erreur, invite à revenir en arrière
- Clavier : Le tableau est en focus, prend en charge la navigation
```

### Étape 4 : Limites de Débit

```
┌─────────────────────────────────────────────────────────────┐
│ Step 4/11: ✓ → ✓ → ✓ → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Définir les limites de débit pour ce torrent :                      │ │
│ │                                                         │ │
│ │ Enter 0 or leave empty for illimité.                  │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Limite de Téléchargement (KiB/s) :                                     │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [1000_____________________________________________]     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Limite de Téléversement (KiB/s) :                                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [500______________________________________________]     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Annuler]                    [Précédent] [Suivant]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Fonctionnalités :
- Deux champs de saisie : Limites de téléchargement et de téléversement
- Unités : KiB/s (Kibioctets par seconde)
- Par défaut : 0 (illimité)
- Validation : Doit être des entiers non négatifs
- Texte d'aide expliquant l'option illimitée
- Clavier : Le champ de limite de téléchargement est mis en focus en premier
```

### Étape 5 : Priorité de la File

```
┌─────────────────────────────────────────────────────────────┐
│ Step 5/11: ✓ → ✓ → ✓ → ✓ → 5 → 6 → 7 → 8 → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Sélectionnez la priorité de la file pour ce torrent :                 │ │
│ │                                                         │ │
│ │ Élevéeer priorité àrrents will be started first.         │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Priorité: [▼ Normale                    ]               │ │
│ │                                                         │ │
│ │ Options :                                               │ │
│ │   • Maximum                                            │ │
│ │   • Élevée                                               │ │
│ │   • Normale  ← Sélectionnered                                 │ │
│ │   • Faible                                                │ │
│ │   • En pause                                             │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Annuler]                    [Précédent] [Suivant]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Fonctionnalités :
- Widget de sélection avec options de priorité
- Options : Maximum, Élevée, Normale, Faible, En pause
- Par défaut : Normale
- Texte d'aide expliquant le système de priorité
- Clavier : Le widget de sélection est en focus
```

### Étape 6 : Option de Reprise

```
┌─────────────────────────────────────────────────────────────┐
│ Step 6/11: ✓ → ✓ → ✓ → ✓ → ✓ → 6 → 7 → 8 → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Reprendre depuis un point de contrôle si disponible :                   │ │
│ │                                                         │ │
│ │ If enabled, the download will resume from the last     │ │
│ │ checkpoint.                                            │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Reprendre depuis un point de contrôle : [ ]                                │
│                          ↑                                  │
│                      Switch (DÉSACTIVÉ)                           │
│                                                             │
│ [Annuler]                    [Précédent] [Suivant]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Fonctionnalités :
- Widget d'interrupteur pour option de reprise
- Par défaut : Faux (désactivé)
- Texte d'aide expliquant la fonctionnalité de reprise depuis un point de contrôle
- Clavier : L'interrupteur est en focus
```

### Étape 7 : Options du Protocole Xet

```
┌─────────────────────────────────────────────────────────────┐
│ Step 7/11: ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → 7 → 8 → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Xet Protocol Options :                                  │ │
│ │                                                         │ │
│ │ Xet active le découpage défini par contenu et la déduplication.│ │
│ │ Useful for reducing storage when downloading similar   │ │
│ │ content.                                               │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Activer le Protocole Xet :              [ ]                       │
│ Enable Déduplication :            [ ]                       │
│ Activer le Stockage Adressé par Contenu P2P: [ ]                  │
│ Activer la Compression :               [ ]                      │
│                                                             │
│ Press Ctrl+X in main dashboard to manage Xet settings      │
│ globally                                                    │
│                                                             │
│ [Annuler]                    [Précédent] [Suivant]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Fonctionnalités :
- Quatre widgets d'interrupteur pour les options Xet :
  1. Activer le Protocole Xet (interrupteur principal)
  2. Activer la Déduplication
  3. Activer le Stockage Adressé par Contenu P2P
  4. Activer la Compression
- Par défaut : Tous désactivés
- Texte d'aide expliquant les avantages du protocole Xet
- Lien vers l'écran de gestion Xet global (Ctrl+X)
- Clavier : Le premier interrupteur (Activer Xet) est en focus
```

### Étape 8 : Options du Protocole IPFS

```
┌─────────────────────────────────────────────────────────────┐
│ Step 8/11: ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → 8 → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ IPFS Protocol Options :                                  │ │
│ │                                                         │ │
│ │ IPFS enables content-addressed storage and peer-to-peer │ │
│ │ content sharing. Content can be accessed via IPFS CID  │ │
│ │ after download.                                         │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Activer le Protocole IPFS :          [ ]                         │
│ Épingler le Contenu dans IPFS:           [ ]                         │
│                                                             │
│ Press Ctrl+I in main dashboard to manage IPFS content and  │
│ peers                                                       │
│                                                             │
│ [Annuler]                    [Précédent] [Suivant]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Fonctionnalités :
- Deux widgets d'interrupteur pour les options IPFS :
  1. Activer le Protocole IPFS (interrupteur principal)
  2. Épingler le Contenu dans IPFS
- Par défaut : Les deux désactivés
- Texte d'aide expliquant les avantages du protocole IPFS
- Lien vers l'écran de gestion IPFS global (Ctrl+I)
- Clavier : Le premier interrupteur (Activer IPFS) est en focus
```

### Étape 9 : Options de Scrape

```
┌─────────────────────────────────────────────────────────────┐
│ Step 9/11: ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → 9 → 10 → 11   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Scrape Options :                                         │ │
│ │                                                         │ │
│ │ Scraping queries tracker statistics (seeders, leechers, │ │
│ │ completed downloads). Auto-scrape will automatically   │ │
│ │ scrape the tracker when the torrent is added.           │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Auto-scrape à l'Ajout :            [ ]                         │
│                                                             │
│ Appuyez sur Ctrl+R dans le tableau de bord principal pour voir les résultats de scrape      │
│                                                             │
│ [Annuler]                    [Précédent] [Suivant]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Fonctionnalités :
- Widget d'interrupteur unique pour option d'auto-scrape
- Par défaut : Désactivé
- Texte d'aide expliquant la fonctionnalité de scraping
- Lien vers l'écran des résultats de scrape (Ctrl+R)
- Clavier : L'interrupteur est en focus
```

### Étape 10 : Options du Protocole uTP

```
┌─────────────────────────────────────────────────────────────┐
│ Step 10/11: ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → 10 → 11 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ uTP (uTorrent Transport Protocol) Options :             │ │
│ │                                                         │ │
│ │ uTP provides reliable, ordered delivery over UDP with  │ │
│ │ delay-based congestion control (BEP 29). Useful for    │ │
│ │ better performance on networks with high latency or     │ │
│ │ packet loss.                                            │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Activer le Transport uTP :          [ ]                        │
│                                                             │
│ Press Ctrl+U in main dashboard to configure uTP settings   │
│ globally                                                    │
│                                                             │
│ [Annuler]                    [Précédent] [Suivant]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Fonctionnalités :
- Widget d'interrupteur unique pour option uTP
- Par défaut : Désactivé
- Texte d'aide expliquant les avantages du protocole uTP (BEP 29)
- Lien vers l'écran de configuration uTP global (Ctrl+U)
- Clavier : L'interrupteur est en focus
```

### Étape 11 : Options de Traversée NAT

```
┌─────────────────────────────────────────────────────────────┐
│ Step 11/11: ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → ✓ → 11  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ NAT Traversal Options :                                  │ │
│ │                                                         │ │
│ │ NAT traversal (NAT-PMP/UPnP) automatically maps ports  │ │
│ │ on your router. This allows peers to connect to you    │ │
│ │ directly, improving download speeds.                    │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Activer le Mappage de Port NAT :       [ ]                        │
│                                                             │
│ Press Ctrl+N in main dashboard to manage NAT settings      │
│ globally                                                    │
│                                                             │
│ [Annuler]                    [Précédent] [Envoyer]            │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Fonctionnalités :
- Widget d'interrupteur unique pour option de mappage NAT
- Par défaut : Désactivé
- Texte d'aide expliquant les avantages de la traversée NAT
- Lien vers l'écran de gestion NAT global (Ctrl+N)
- Clavier : L'interrupteur est en focus
- Note : Le bouton "Suivant" devient "Envoyer" à l'étape finale
```



## Hiérarchie des Widgets

```
TerminalDashboard (App)
├── En-tête (with clock)
├── Horizontal (#body)
│   ├── Container (#left)
│   │   ├── Overview (#overview)
│   │   │   └── Rich Table (Torrents, Active, En pause, Seeding, Rates, Progression)
│   │   └── SpeedSparklines (#speeds)
│   │       ├── Sparkline (Download)
│   │       └── Sparkline (Upload)
│   └── Container (#right)
│       ├── TorrentsTable (#torrents)
│       │   └── DataTable columns: Hash d'Information, Nom, Statut, Progression, Down/Up
│       ├── PeersTable (#peers)
│       │   └── DataTable columns: IP, Port, Down, Up, Latency, Quality, Health, Étranglé, Client
│       ├── Static (#details)
│       └── RichLog (#logs)
├── Static (#statusbar)
├── Container
│   └── Static (#alerts)
└── Pied de page
```


## Écrans Disponibles

### Écrans de Surveillance
1. **SystemResourcesScreen** - CPU, memory, disk, network usage
2. **PerformanceMetricsScreen** - Performance metrics from MetricsCollector
3. **NetworkQualityScreen** - Network quality metrics for peers
4. **HistoricalTrendsScreen** - Historical trends with sparklines
5. **AlertsDashboardScreen** - Enhanced alerts with filtering
6. **MetricsExplorerScreen** - Explore all metrics with export
7. **QueueMetricsScreen** - Queue metrics (position, priority, waiting time)
8. **DiskIOMetricsScreen** - Disk I/O statistics
9. **TrackerMetricsScreen** - Tracker metrics (announce/scrape success)
10. **PerformanceAnalysisScreen** - Performance analysis from CLI
11. **DiskAnalysisScreen** - Disk analysis from disk-detect/stats

### Écrans de Configuration
1. **GlobalConfigMainScreen** - Main global config with section selector
2. **GlobalConfigDetailScreen** - Detail screen for global config sections
3. **PerTorrentConfigMainScreen** - Main per-torrent config with torrent selector
4. **TorrentConfigDetailScreen** - Detail screen for per-torrent config

### Écrans de Gestion des Protocoles
1. **XetManagementScreen** - Xet protocol management
2. **IPFSManagementScreen** - IPFS protocol management
3. **SSLConfigScreen** - SSL/TLS configuration
4. **ProxyConfigScreen** - Proxy configuration
5. **ScrapeResultsScreen** - View cached scrape results
6. **NATManagementScreen** - NAT traversal (NAT-PMP, UPnP)
7. **UTPConfigScreen** - uTP configuration

### Écrans Utilitaires
1. **AideScreen** - Keyboard shortcuts and help
2. **NavigationMenuScreen** - Navigation menu/sidebar
3. **AddTorrentScreen** - Advanced torrent addition (multi-step form)
4. **FichierSélectionnerionScreen** - Fichier selection management
5. **ConfirmationDialog** - Modal confirmation dialog

## Exemples de Disposition d'Écran

### Ressources Système Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Ressources Système                                     │ │
│ │ Resource    Usage    Progression                        │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ CPU         75.0%    ████████████████░░░░░░░░        │ │
│ │ Memory      85.0%    ████████████████████░░░░        │ │
│ │ Disk        60.0%    ████████████░░░░░░░░░░░░        │ │
│ │ Processes   142      (no progress bar)               │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Network I/O                                          │ │
│ │ Direction   Bytes          Formatted                │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Sent        1,234,567,890  1.15 GB                   │ │
│ │ Received    987,654,321    941.89 MB                 │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Métriques de Performance Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Métriques de Performance                                 │ │
│ │ Metric              Value      Description          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Peer Connections    45         Total connected...   │ │
│ │ Vitesse de Téléchargement      2.5 MB/s   Global download...   │ │
│ │ Vitesse de Téléversement        1.2 MB/s   Global upload...     │ │
│ │ Pieces Completed    1,234      Successfully...       │ │
│ │ Pieces Failed       5          Failed piece...       │ │
│ │ Tracker Requests    89         Total tracker...      │ │
│ │ Tracker Responses   87         Successful...         │ │
│ │ Tracker Success     97.8%      Response success...  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Event-Driven Metrics (MetricsPlugin)                │ │
│ │ Metric          Count  Avg    Min    Max    Sum     │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ download_speed  1000   2.5MB  0.1MB  5.0MB  2.5GB   │ │
│ │ upload_speed    1000   1.2MB  0.05MB 3.0MB  1.2GB   │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Statistics                                          │ │
│ │ Metric              Value                            │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total Metrics       25                              │ │
│ │ Active Metrics      20                              │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Qualité du Réseau Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Global Network Statistics                          │ │
│ │ Metric                  Value                      │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total Torrents          5                          │ │
│ │ Torrents Actifs         3                          │ │
│ │ Global Download Rate    2.5 MB/s                   │ │
│ │ Global Upload Rate      1.2 MB/s                   │ │
│ │ Download Utilization    62.5%                      │ │
│ │ Upload Utilization      60.0%                      │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Per-Torrent Qualité du Réseau                        │ │
│ │ Torrent        Down Rate  Up Rate  Progression Statut │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ example.torrent 1.2 MB/s  500 KB/s  45%   Active   │ │
│ │ movie.torrent   800 KB/s  300 KB/s  78%   Seeding  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Peer Metrics Summary                                │ │
│ │ Metric                      Value                   │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total Peers                  25                     │ │
│ │ Étranglé Peers                 8                      │ │
│ │ Unchoke Ratio                68.0%                   │ │
│ │ Average Latency               45.2 ms                │ │
│ │ Piece Request Success Rate    95.5%                  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Peer Quality (Torrent: abc123...)                   │ │
│ │ IP            Down      Up      Quality            │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ 192.168.1.1   1.2 MB/s  500 KB/s  85% ████████     │ │
│ │ 10.0.0.5      800 KB/s  300 KB/s  70% ██████░░     │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Tendances Historiques Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Tendances Historiques                                  │ │
│ │ Metric              Current    Trend               │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Vitesse de Téléchargement      2.5 MB/s   ▁▂▃▅▆▇█            │ │
│ │ Vitesse de Téléversement        1.2 MB/s   ▁▂▃▅▆▇█            │ │
│ │ Peer Connections    45         ▁▂▃▅▆▇█            │ │
│ │ Pieces Completed    1,234       ▁▂▃▅▆▇█            │ │
│ │ Tracker Success     97.8%       ▁▂▃▅▆▇█            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Sparklines Group                                    │ │
│ │ [Vitesse de Téléchargement Sparkline]                          │ │
│ │ [Vitesse de Téléversement Sparkline]                            │ │
│ │ [Peer Connections Sparkline]                       │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Tableau de Bord des Alertes Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Alert Rules                                         │ │
│ │ Nom        Metric          Condition    Severity  │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ high_cpu    cpu_usage        > 80%        WARNING   │ │
│ │ low_disk    disk_usage      > 90%        ERROR      │ │
│ │ slow_dl     download_speed   < 100 KB/s  WARNING   │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Active Alerts                                       │ │
│ │ Severity  Rule        Metric        Value    Time   │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ WARNING   high_cpu    cpu_usage     85%      14:32  │ │
│ │ ERROR     low_disk    disk_usage    92%      14:30  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Alert History (Last 50)                             │ │
│ │ Severity  Rule        Value    Time      Resolved  │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ WARNING   high_cpu    85%      14:32:15  No        │ │
│ │ ERROR     low_disk    92%      14:30:10  No        │ │
│ │ WARNING   slow_dl     50 KB/s  14:25:00  Yes       │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Alert Statistics                                    │ │
│ │ Statistic              Value                       │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Alerts Triggered       15                          │ │
│ │ Alerts Resolved        8                           │ │
│ │ Notifications Sent     12                          │ │
│ │ Notification Failures  0                           │ │
│ │ Suppressed Alerts      2                           │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Explorateur de Métriques Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ Filter: [download________________________________]      │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Metrics Table                                       │ │
│ │ Metric Nom        Type      Current Value  Desc   │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ download_speed     gauge     2.5 MB/s       ...    │ │
│ │ upload_speed       gauge     1.2 MB/s       ...    │ │
│ │ peer_connections   counter   45             ...    │ │
│ │ pieces_completed   counter   1,234          ...    │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Metric Details                                      │ │
│ │ Nom: download_speed                                │ │
│ │ Type: gauge                                         │ │
│ │ Current Value: 2.5 MB/s                            │ │
│ │ Description: Global download speed in bytes/sec     │ │
│ │ Unit: bytes/sec                                     │ │
│ │ Min: 0.0                                            │ │
│ │ Max: 10.0 MB/s                                      │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q, Export: e/p)               │
└─────────────────────────────────────────────────────────┘
```

### Queue Metrics Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Queue Statistics                                    │ │
│ │ Metric              Value      Description          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total Torrents      10         Total torrents...    │ │
│ │ Active Downloading  3          Currently...         │ │
│ │ Active Seeding      2          Currently...         │ │
│ │ Queued              5          Torrents waiting... │ │
│ │ En pause              0          En pause torrents      │ │
│ │                                                     │ │
│ │ By Priorité                                         │ │
│ │   Maximum           1          Torrents with...     │ │
│ │   Élevée              2          Torrents with...     │ │
│ │   Normale            5          Torrents with...     │ │
│ │   Faible               2          Torrents with...     │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Queue Summary                                       │ │
│ │ Metric              Value                          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Queue Length        10                             │ │
│ │ Queued (Waiting)    5                              │ │
│ │ Active              5                              │ │
│ │ Avg Waiting Time    15m                            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Queue Entries                                       │ │
│ │ Pos  Torrent        Priorité  Statut    Wait  Down │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ 1    example.torrent Maximum   Active   0s    1000 │ │
│ │ 2    movie.torrent   Élevée      Active   5m    800   │ │
│ │ 3    file.torrent    Normale    Queued   10m   -    │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Disk I/O Metrics Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Disk I/O Statistics                                 │ │
│ │ Metric              Value      Description          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total Writes        1,234,567  Number of write...   │ │
│ │ Bytes Written       5.2 GB     Total bytes...       │ │
│ │ Queue Full Errors   5          Times write...        │ │
│ │ Preallocations      100        Fichier preallocation... │ │
│ │ io_uring Operations 50,000     Operations using...   │ │
│ │ Queue Depth         15/100     Current queue...      │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Cache Statistics                                    │ │
│ │ Metric              Value      Description          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Cache Entries       500        Number of cached...  │ │
│ │ Cache Taille          2.5 GB     Total size of...      │ │
│ │ Cache Hits          10,000     Successful cache...  │ │
│ │ Cache Misses        500        Failed cache...       │ │
│ │ Hit Rate            95.2%      Cache hit percentage │ │
│ │ Bytes Served        1.5 GB     Bytes served from...  │ │
│ │ Cache Efficiency    92.5%      Cache efficiency...  │ │
│ │ Evictions           50         Cache entries...      │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Disk I/O Configuration                              │ │
│ │ Setting              Value                          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Max Workers         8                              │ │
│ │ Queue Taille          100                            │ │
│ │ Cache Taille          512 MB                         │ │
│ │ Storage Type        NVME                           │ │
│ │ io_uring Enabled    Yes                            │ │
│ │ Direct I/O Enabled  Yes                            │ │
│ │ NVMe Optimized      Yes                            │ │
│ │ Write Cache Enabled Yes                            │ │
│ │ Adaptive Workers    Active                         │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Tracker Metrics Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Tracker Statistics                                  │ │
│ │ Tracker        Requests  Avg Response  Error  Reuse │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ tracker1.com   1,234     45.2 ms       0.00%  95%   │ │
│ │ tracker2.org  567       120.5 ms      2.50%  90%   │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Summary                                             │ │
│ │ Metric              Value                          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total Trackers      2                              │ │
│ │ Total Requests      1,801                          │ │
│ │ Total Errors        14                             │ │
│ │ Success Rate        99.22%                         │ │
│ │ Avg Response Time   67.8 ms                        │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Tracker Sessions                                    │ │
│ │ URL            Last Announce  Interval  Fail Statut│ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ tracker1.com   2m ago         30m       0   Healthy │ │
│ │ tracker2.org   5m ago         60m       1   Degraded │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Menu de Navigation Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Menu de Navigation                                      │ │
│ │ Category      Screen              Shortcut          │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Monitoring    Ressources Système    s                │ │
│ │ Monitoring    Métriques de Performance m                │ │
│ │ Monitoring    Qualité du Réseau     n                │ │
│ │ Monitoring    Tendances Historiques   h                │ │
│ │ Monitoring    Tableau de Bord des Alertes    a                │ │
│ │ Monitoring    Explorateur de Métriques    e                │ │
│ │ Monitoring    Queue Metrics      u                │ │
│ │ Monitoring    Disk I/O Metrics   j                │ │
│ │ Monitoring    Tracker Metrics    k                │ │
│ │ Configuration Global Config      g                │ │
│ │ Configuration Torrent Config     t                │ │
│ │ Protocols     Gestion Xet     Ctrl+X            │ │
│ │ Protocols     Gestion IPFS    Ctrl+I            │ │
│ │ Protocols     Configuration SSL         Ctrl+S            │ │
│ │ Protocols     Configuration Proxy       Ctrl+P            │ │
│ │ Protocols     Gestion NAT     Ctrl+N            │ │
│ │ Protocols     Configuration uTP         Ctrl+U            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Menu de Navigation                                      │ │
│ │ Sélectionner a screen to open. Press Enter to navigate,  │ │
│ │ Escape to go back.                                  │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Aide Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Keyboard Shortcuts                                  │ │
│ │ Key         Action              Description         │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ p           Mettre en pause le torrent       Pause selected...   │ │
│ │ r           Reprendre le torrent      Resume selected...  │ │
│ │ q           Quitter                 Exit dashboard      │ │
│ │ i           Quick Add           Quick torrent add   │ │
│ │ o           Advanced Add         Advanced torrent... │ │
│ │ g           Global Config        Open global...      │ │
│ │ t           Torrent Config       Open per-torrent... │ │
│ │ s           Ressources Système     Open system...      │ │
│ │ m           Métriques de Performance Open performance... │ │
│ │ n           Qualité du Réseau      Open network...     │ │
│ │ h           Tendances Historiques   Open historical...  │ │
│ │ a           Tableau de Bord des Alertes     Open alerts...      │ │
│ │ e           Explorateur de Métriques    Open metrics...      │ │
│ │ ?           Aide                 Show this help     │ │
│ │ Ctrl+M      Menu de Navigation     Open navigation...  │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Global Config Main Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Configuration Sections                              │ │
│ │ Section              Description          Modified │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ network              Network configuration...        │ │
│ │ network.protocol_v2  BitTorrent Protocol...         │ │
│ │ network.utp          uTP transport...               │ │
│ │ disk                 Disk I/O configuration...       │ │
│ │ disk.attributes      Fichier attributes...              │ │
│ │ disk.xet             Xet protocol...                │ │
│ │ strategy             Piece selection...              │ │
│ │ discovery            Peer discovery...               │ │
│ │ observability        Logging, metrics...             │ │
│ │ limits               Rate limit...                   │ │
│ │ security             Security settings...            │ │
│ │ security.ip_filter   IP filtering...                │ │
│ │ security.ssl         SSL/TLS settings...            │ │
│ │ proxy                Proxy configuration            │ │
│ │ ml                   Machine learning...             │ │
│ │ dashboard            Dashboard/web UI...             │ │
│ │ queue                Torrent queue...                │ │
│ │ nat                  NAT traversal...                │ │
│ │ ipfs                 IPFS protocol...                │ │
│ │ webtorrent           WebTorrent protocol...          │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Global Configuration                                │ │
│ │ Sélectionner a section to configure. Press Enter to edit, │ │
│ │ Escape to go back.                                  │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Global Config Detail Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Network Configuration                               │ │
│ │ Option          Current Value    Type               │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ max_connections 200              number             │ │
│ │ max_peers       50                number             │ │
│ │ connect_timeout 30                number             │ │
│ │ enable_utp       true              bool               │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Métriques de Performance                                 │ │
│ │ [Metrics displayed here]                            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Configuration Editors                               │ │
│ │ max_connections: Network max connections            │ │
│ │ [200________________________________]              │ │
│ │ max_peers: Maximum peers per torrent                │ │
│ │ [50_________________________________]              │ │
│ │ connect_timeout: Connection timeout in seconds     │ │
│ │ [30_________________________________]              │ │
│ │ enable_utp: Enable uTP transport                    │ │
│ │ [✓] Enable uTP                                      │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Errors                                              │ │
│ │ (Validation errors appear here)                    │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Save (Runtime)] [Save to Fichier] [Annuler]               │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Per-Torrent Config Main Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────┐ ┌────────────────┐ │
│ │ Torrents                         │ │ Summary        │ │
│ │ Hash d'Information  Nom      Statut ...   │ │ Key      Value │ │
│ │ ──────────────────────────────── │ │ ─────────────── │ │
│ │ abc123...  example   Active 45%   │ │ Total    10    │ │
│ │ def456...  movie     Seeding 100% │ │ With     5     │ │
│ │ ghi789...  file      Active 78%   │ │ Without  5     │ │
│ │ ...                               │ │                │ │
│ └──────────────────────────────────┘ └────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Per-Torrent Configuration                           │ │
│ │ Sélectionner a torrent to configure. Press Enter to edit, │ │
│ │ Escape to go back.                                  │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q)                             │
└─────────────────────────────────────────────────────────┘
```

### Torrent Config Detail Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Rate Limit Configuration                            │ │
│ │ Setting         Current Value    Description        │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Download Limit  1000 KiB/s      Per-torrent...      │ │
│ │ Upload Limit    500 KiB/s       Per-torrent...      │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Torrent: example.torrent                            │ │
│ │ Key              Value                              │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Hash d'Information        abc123...                          │ │
│ │ Statut           Active                             │ │
│ │ Progression         45.0%                              │ │
│ │ Current Down     1.2 MB/s (1171.9 KiB/s)          │ │
│ │ Current Up       500 B/s (0.5 KiB/s)               │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Métriques de Performance                                 │ │
│ │ [Metrics displayed here]                            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Configuration Inputs                                │ │
│ │ Download Limit (KiB/s, 0 = illimité):              │ │
│ │ [1000________________________________]              │ │
│ │ Upload Limit (KiB/s, 0 = illimité):                │ │
│ │ [500_________________________________]              │ │
│ │ Queue Priorité:                                     │ │
│ │ [normal________________________________]            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Queue Configuration                                 │ │
│ │ Key              Value                              │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Queue Statut     Priorité: NORMAL, Position: 3     │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Fichiers Section                                       │ │
│ │ [Fichier information displayed here]                  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Operations                                          │ │
│ │ [Announce] [Scrape] [PEX] [Rehash] [Pause] [Resume] │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Save] [Reset Limits] [Manage Fichiers] [Annuler]          │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q, Announce: a, Scrape: s...) │
└─────────────────────────────────────────────────────────┘
```

### Fichier Sélectionnerion Screen
```
┌─────────────────────────────────────────────────────────┐
│ Fichier Sélectionnerion                                           │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Fichiers Table                                         │ │
│ │ #  Sélectionnered  Priorité  Progression  Taille    Fichier Nom │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ 0  ✓         normal    100.0%    500 MB  file1.mp4 │ │
│ │ 1  ✓         high      45.0%     1.2 GB  file2.mkv │ │
│ │ 2            normal    0.0%      300 MB  file3.srt  │ │
│ │ 3  ✓         low       78.0%     800 MB  file4.avi  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Fichier Sélectionnerion Statut                               │ │
│ │ Total: 4 | Sélectionnered: 3 | Deselected: 1              │ │
│ └─────────────────────────────────────────────────────┘ │
│ Commands: Space=Toggle, A=Sélectionner All, D=Deselect All,  │
│           P=Priorité, S=Save, Esc=Back                  │
└─────────────────────────────────────────────────────────┘
```

### Add Torrent Screen (Multi-step Form)
```
┌─────────────────────────────────────────────────────────┐
│ Step 1/11: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11│
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Étape 1 : Entrée Torrent                               │ │
│ │                                                     │ │
│ │ Enter torrent path or magnet URI:                  │ │
│ │ [magnet:?xt=urn:btih:abc123...________________]    │ │
│ │                                                     │ │
│ │ Or browse for .torrent file                         │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ [Annuler]                    [Précédent] [Suivant] [Envoyer] │
└─────────────────────────────────────────────────────────┘

Étape 2 : Répertoire de Sortie
Step 3: Fichier Sélectionnerion
Étape 4 : Limites de Débit
Étape 5 : Priorité de la File
Étape 6 : Option de Reprise
Step 7: Xet Options
Step 8: IPFS Options
Étape 9 : Options de Scrape
Step 10: uTP Options
Step 11: NAT Options
```

### Gestion Xet Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Xet Protocol Statut                                 │ │
│ │ Enabled: Yes                                        │ │
│ │ Déduplication : Enabled                              │ │
│ │ P2P CAS : Enabled                                    │ │
│ │ Compression : Enabled                                │ │
│ │ Chunk size range: 512-16384 bytes                   │ │
│ │ Target chunk size: 8192 bytes                       │ │
│ │ Cache DB: /path/to/cache.db                         │ │
│ │ Chunk store: /path/to/chunks                        │ │
│ │                                                     │ │
│ │ Runtime Statut:                                     │ │
│ │   Protocol state: active                            │ │
│ │   P2P CAS client: Active                            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Xet Deduplication Cache Statistics                  │ │
│ │ Metric              Value                           │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total chunks        10,000                          │ │
│ │ Unique chunks       5,000                           │ │
│ │ Total size          5.2 GB                          │ │
│ │ Cache size          2.6 GB                          │ │
│ │ Average chunk size  8192 bytes                      │ │
│ │ Deduplication ratio 2.0                            │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Xet Métriques de Performance                             │ │
│ │ Metric                      Value                   │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Deduplication Efficiency    50.0%                   │ │
│ │ Space Saved                 2.6 GB (50.0%)         │ │
│ │ Deduplication Ratio         2.0x                    │ │
│ │ Average Chunk Taille          8.0 KB                  │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Enable] [Disable] [Refresh] [Cache Info] [Cleanup]    │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q, Enable: e, Disable: d...)  │
└─────────────────────────────────────────────────────────┘
```

### Gestion IPFS Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ IPFS Protocol Statut                                │ │
│ │ Connection: Connected                               │ │
│ │ Protocol state: active                              │ │
│ │ IPFS API URL: http://localhost:5001                 │ │
│ │ Gateway URLs: 2                                      │ │
│ │ Connected: Yes                                      │ │
│ │ Connected peers: 15                                 │ │
│ │ Content items: 25                                   │ │
│ │ Pinned items: 10                                    │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ IPFS Métriques de Performance                            │ │
│ │ [Performance metrics displayed here]                │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌──────────────────────────┐ ┌──────────────────────┐ │
│ │ IPFS Content             │ │ IPFS Peers            │ │
│ │ CID          Taille  Pin   │ │ Peer ID    Multiaddr │ │
│ │ ──────────── ───── ───── │ │ ────────── ──────────│ │
│ │ QmAbc123...  500MB  Yes  │ │ 12D3Koo... /ip4/... │ │
│ │ QmDef456...  1.2GB  No   │ │ 12D3Koo... /ip6/... │ │
│ └──────────────────────────┘ └──────────────────────┘ │
│ [Add Fichier] [Get Content] [Pin] [Unpin] [Refresh]      │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q, Add: a, Get: g, Pin: p...) │
└─────────────────────────────────────────────────────────┘
```

### Configuration SSL Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ SSL/TLS Statut                                      │ │
│ │ Tracker SSL: Enabled                                │ │
│ │ Peer SSL: Enabled                                   │ │
│ │ Certificate Verification: Enabled                   │ │
│ │ Protocol Version: TLSv1.3                           │ │
│ │ CA Certificates: /path/to/ca.crt                   │ │
│ │ Client Certificate: /path/to/client.crt             │ │
│ │ Client Key: Set                                     │ │
│ │ Allow Insecure Peers: No                            │ │
│ │ Cipher Suites: System default                       │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ SSL/TLS Configuration                               │ │
│ │ Setting              Current Value    Action        │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Tracker SSL          Enabled          Press 1/2    │ │
│ │ Peer SSL             Enabled          Press 3/4    │ │
│ │ Certificate Verify   Enabled          Press v/V    │ │
│ │ Protocol Version     TLSv1.3          Click Set... │ │
│ │ CA Certificates      /path/to/ca.crt   Click Set... │ │
│ │ Client Certificate   /path/to/client.crt Click...  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ SSL Métriques de Performance                             │ │
│ │ [Performance metrics displayed here]                │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Enable Trackers] [Disable Trackers] [Enable Peers]     │
│ [Disable Peers] [Set CA Certs] [Set Client Cert]        │
│ [Set Protocol] [Verify On] [Verify Off] [Refresh]       │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q, Refresh: r, Enable: 1/3...)│
└─────────────────────────────────────────────────────────┘
```

### Configuration Proxy Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Proxy Statut                                        │ │
│ │ Enabled: Yes                                        │ │
│ │ Type: SOCKS5                                        │ │
│ │ Host: proxy.example.com                             │ │
│ │ Port: 1080                                          │ │
│ │ Username: user                                      │ │
│ │ Password: ***                                      │ │
│ │ For Trackers: Yes                                  │ │
│ │ For Peers: Yes                                     │ │
│ │ For WebSeeds: No                                   │ │
│ │ Bypass List: localhost, 127.0.0.1                  │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Proxy Statistics                                    │ │
│ │ Metric              Value                           │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Total Connections   1,234                          │ │
│ │ Successful          1,200                          │ │
│ │ Failed              34                             │ │
│ │ Auth Failures       2                              │ │
│ │ Timeouts            5                              │ │
│ │ Bytes Sent          500 MB                         │ │
│ │ Bytes Received      2.5 GB                         │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Proxy Métriques de Performance                           │ │
│ │ [Performance metrics displayed here]                │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Set Proxy] [Test Connection] [Disable] [Refresh]       │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q, Test: t, Refresh: r)       │
└─────────────────────────────────────────────────────────┘
```

### Résultats de Scrape Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Scrape Cache Statut                                 │ │
│ │ Total cached results: 25                            │ │
│ │                                                     │ │
│ │ Scrape results show tracker statistics (seeders,   │ │
│ │ leechers, completed downloads).                    │ │
│ │ Results are cached to avoid excessive tracker...    │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Cached Résultats de Scrape                               │ │
│ │ Hash d'Information      Seeders  Leechers  Completed  Count │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ abc123...      1,234    567       5,678     15     │ │
│ │ def456...      890      234       3,456     12     │ │
│ │ ghi789...      567      123       2,345     8      │ │
│ │ ...                                                │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Refresh] [Scrape All]                                   │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q, Refresh: r)                 │
└─────────────────────────────────────────────────────────┘
```

### Gestion NAT Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ NAT Traversal Statut                                │ │
│ │ Active Protocol: UPnP                               │ │
│ │ External IP: 203.0.113.42                          │ │
│ │                                                     │ │
│ │ Configuration:                                      │ │
│ │   Auto-map ports: Yes                              │ │
│ │   NAT-PMP enabled: Yes                             │ │
│ │   UPnP enabled: Yes                                 │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ NAT Métriques de Performance                             │ │
│ │ [Performance metrics displayed here]                │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Active Port Mappings                                │ │
│ │ Protocol  Internal  External  Source    Expires    │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ TCP       6881      6881      UPnP      3600s      │ │
│ │ UDP       6881      6881      UPnP      3600s      │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Discover] [Map Port] [Unmap Port] [External IP] [Refresh]│
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q, Discover: d, Refresh: r)    │
└─────────────────────────────────────────────────────────┘
```

### Configuration uTP Screen
```
┌─────────────────────────────────────────────────────────┐
│ En-tête                                                   │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ uTP Statut                                          │ │
│ │ Enabled: Yes                                        │ │
│ │                                                     │ │
│ │ uTP provides reliable, ordered delivery over UDP    │ │
│ │ with delay-based congestion control (BEP 29).      │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Configuration uTPuration                                   │ │
│ │ Setting                  Value          Description │ │
│ │ ─────────────────────────────────────────────────── │ │
│ │ Prefer over TCP          true           Prefer uTP..│ │
│ │ Connection Timeout       30s            Connection..│ │
│ │ Max Window Taille          2,097,152 bytes Max receive│ │
│ │ MTU                      1,500 bytes    Maximum...  │ │
│ │ Initial Rate             64,000 B/s     Initial...  │ │
│ │ Min Rate                 1,000 B/s      Minimum...  │ │
│ │ Max Rate                 10,000,000 B/s Maximum...  │ │
│ │ ACK Interval             0.1s           ACK packet..│ │
│ │ Retransmit Timeout       2.0            RTT...      │ │
│ │ Max Retransmits          5              Maximum...  │ │
│ └─────────────────────────────────────────────────────┘ │
│ [Enable] [Disable] [Config Get] [Config Set] [Config   │
│ Reset] [Refresh]                                         │
├─────────────────────────────────────────────────────────┤
│ Pied de page (Back: Esc, Quitter: q, Enable: e, Disable: d...)   │
└─────────────────────────────────────────────────────────┘
```

### Confirmation Dialog (Modal)
```
┌─────────────────────────────────────────────────────────┐
│                                                          │
│              ┌────────────────────────────┐              │
│              │ Confirmation              │              │
│              ├────────────────────────────┤              │
│              │                            │              │
│              │ Are you sure you want to   │              │
│              │ delete this torrent?        │              │
│              │                            │              │
│              │                            │              │
│              │    [Yes]        [No]       │              │
│              └────────────────────────────┘              │
│                                                          │
└─────────────────────────────────────────────────────────┘
```



## Fonctionnalités

### Mises à Jour en Temps Réel
Suivi en direct du statut et de la progression des torrents, mis à jour à intervalles configurables. See [ccbt/interface/terminal_dashboard.py:_poll_once](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L389).

### Surveillance des Pairs
Voir les pairs connectés, leurs vitesses et les informations du client. See [ccbt/interface/terminal_dashboard.py:PeersTable](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L228).

### Visualisation de la Vitesse
Graphiques de vitesse de téléchargement/téléversement avec sparklines. See [ccbt/interface/terminal_dashboard.py:SpeedSparklines](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L250).

### Système d'Alertes
Notifications en temps réel pour les événements importants. See [ccbt/interface/terminal_dashboard.py:491](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L491) for alert display.

### Contrôles Interactifs
Raccourcis clavier pour les opérations courantes. See [ccbt/interface/terminal_dashboard.py:on_key](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3240).

### Support Multi-Torrent
Surveiller plusieurs téléchargements simultanément. See [ccbt/interface/terminal_dashboard.py:TorrentsTable](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L221).

### Écrans de Surveillance
Écrans spécialisés pour les métriques de surveillance détaillées :
- **Ressources Système** (`s`) - Utilisation CPU, mémoire, disque, I/O réseau
- **Métriques de Performance** (`m`) - Données de performance de MetricsCollector et MetricsPlugin
- **Qualité du Réseau** (`n`) - Qualité de connexion des pairs et statistiques réseau
- **Tendances Historiques** (`h`) - Tendances de métriques historiques avec sparklines
- **Tableau de Bord des Alertes** (`a`) - Règles d'alerte, alertes actives et historique des alertes
- **Explorateur de Métriques** (`e`) - Parcourir et explorer toutes les métriques disponibles

Voir la section [Écrans de Surveillance](#monitoring-screens) pour plus de détails.

## Disposition du Tableau de Bord

Le tableau de bord est construit avec [Textual](https://textual.textualize.io/) et organisé en panneaux:

### Structure de Disposition
- **En-tête**: Horloge et titre de l'application. Voir [ccbt/interface/terminal_dashboard.py:323](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L323)
- **Corps**: Divisé en sections gauche et droite. Voir [ccbt/interface/terminal_dashboard.py:324](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L324)
- **Panneau Gauche**: Vue d'ensemble et graphiques de vitesse
- **Panneau Droit**: Torrents, pairs, détails et journaux
- **Pied de page**: Barre d'état et alertes. Voir [ccbt/interface/terminal_dashboard.py:333-334](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L333-L334)

Style CSS : [ccbt/interface/terminal_dashboard.py:279-297](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L279-L297)

### Panneaux

#### Panneau de Vue d'Ensemble
Affiche les statistiques globales. Implémentation : [ccbt/interface/terminal_dashboard.py:Overview](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L174)
- Vitesse de Téléchargement: Taux de téléchargement global actuel
- Vitesse de Téléversement: Taux de téléversement global actuel
- Pairs Connectés: Nombre total de pairs connectés
- Torrents Actifs: Nombre de torrents en téléchargement/partage
- Progressionion Moyenne: Pourcentage de progression global

#### Panneau des Torrents
Affiche tous les torrents actifs dans un tableau. Implémentation : [ccbt/interface/terminal_dashboard.py:TorrentsTable](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L196)
- Hash d'Information: Identifiant du torrent
- Nom: Nom du torrent
- Statut: Statut actuel (téléchargement, partage, en pause)
- Progression: Pourcentage de complétion
- Taux Descendant/Montant: Vitesses de transfert

#### Panneau des Pairs
Affiche les pairs pour le torrent sélectionné. Implémentation : [ccbt/interface/terminal_dashboard.py:PeersTable](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L228)
- Adresse IP: Adresse IP du pair
- Port: Port du pair
- Taux Descendant/Montant: Vitesses de transfert vers/depuis le pair
- Étranglé: Si le pair est étranglé
- Client: Identification du client BitTorrent

#### Sparklines de Vitesse
Visualisation de vitesse en temps réel. Implémentation : [ccbt/interface/terminal_dashboard.py:SpeedSparklines](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L250)
- Graphique de Téléchargement: Sparkline affichant l'historique de la vitesse de téléchargement
- Graphique de Téléversement: Sparkline affichant l'historique de la vitesse de téléversement
- Maintient les 120 derniers échantillons (~2 minutes à 1s de rafraîchissement). Voir [ccbt/interface/terminal_dashboard.py:269](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L269)

#### Panneau de Détails
Affiche des informations détaillées pour le torrent sélectionné. Implémentation : [ccbt/interface/terminal_dashboard.py:428-439](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L428-L439)

#### Panneau d'Alertes
Affiche les règles d'alerte et les alertes actives. Implémentation : [ccbt/interface/terminal_dashboard.py:3059-3102](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3059-L3102)

## Écrans de Surveillance

Bitonic fournit des écrans de surveillance spécialisés accessibles depuis le tableau de bord principal. Chaque écran se concentre sur un domaine de surveillance spécifique avec des métriques et visualisations détaillées.

### Écran des Ressources Système

**Accès** : Appuyez sur `s` depuis le tableau de bord principal

**Objectif** : Afficher l'utilisation des ressources système (CPU, mémoire, disque, I/O réseau).

**Fonctionnalités** :
- Pourcentage d'utilisation CPU avec barre de progression
- Pourcentage d'utilisation mémoire avec barre de progression
- Pourcentage d'utilisation disque avec barre de progression
- Nombre de processus
- Statistiques I/O réseau (octets envoyés/reçus)

**Implémentation** : [ccbt/interface/terminal_dashboard.py:SystemResourcesScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L690)

**Navigation** : Appuyez sur `Échap` ou `q` pour revenir au tableau de bord principal

### Écran des Métriques de Performance

**Accès** : Appuyez sur `m` depuis le tableau de bord principal

**Objectif** : Afficher les métriques de performance de MetricsCollector et MetricsPlugin.

**Fonctionnalités** :
- Nombre de connexions de pairs
- Vitesses de téléchargement/téléversement
- Statistiques de pièces complétées/échouées
- Statistiques de requêtes/réponses du tracker
- Métriques basées sur les événements de MetricsPlugin (si disponible)
- Statistiques de collecte de métriques

**Implémentation** : [ccbt/interface/terminal_dashboard.py:PerformanceMetricsScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L811)

**Sources de Données** :
- `MetricsCollector.get_performance_metrics()`
- `MetricsCollector.get_metrics_statistics()`
- `MetricsPlugin.get_aggregates()` (si disponible)

**Navigation** : Appuyez sur `Échap` ou `q` pour revenir au tableau de bord principal

### Écran de Qualité du Réseau

**Accès** : Appuyez sur `n` depuis le tableau de bord principal

**Objectif** : Afficher les métriques de qualité réseau pour les pairs et les connexions.

**Fonctionnalités** :
- Statistiques réseau globales
- Tableau de qualité réseau par torrent
- Métriques de qualité de connexion des pairs avec indicateurs visuels
- Score de qualité de connexion (0-100)

**Implémentation** : [ccbt/interface/terminal_dashboard.py:NetworkQualityScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L889)

**Calcul de Qualité** :
- Basé sur les vitesses des pairs et le statut d'étranglement
- Indicateurs visuels : ████████ (excellent), ██████░░ (bon), ████░░░░ (moyen), ██░░░░░░ (faible)

**Navigation** : Appuyez sur `Échap` ou `q` pour revenir au tableau de bord principal

### Écran des Tendances Historiques

**Accès** : Appuyez sur `h` depuis le tableau de bord principal

**Objectif** : Afficher les tendances historiques pour diverses métriques en utilisant des sparklines.

**Fonctionnalités** :
- Plusieurs widgets sparkline pour différentes métriques
- Stockage de données historiques (120 derniers échantillons, ~2 minutes)
- Tableau récapitulatif avec valeurs actuelles, min, max et moyennes
- Formatage automatique des métriques (taux, pourcentages, compteurs)

**Métriques Suivies** :
- Taux de téléchargement/téléversement
- Utilisation CPU
- Utilisation mémoire
- Connexions de pairs

**Implémentation** : [ccbt/interface/terminal_dashboard.py:HistoricalTrendsScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L1059)

**Navigation** : Appuyez sur `Échap` ou `q` pour revenir au tableau de bord principal

### Écran du Tableau de Bord des Alertes

**Accès** : Appuyez sur `a` depuis le tableau de bord principal

**Objectif** : Affichage amélioré des alertes avec filtrage et gestion.

**Fonctionnalités** :
- Tableau des règles d'alerte (nom, métrique, condition, sévérité, statut activé)
- Tableau des alertes actives (sévérité, règle, métrique, valeur, horodatage)
- Historique des alertes (50 dernières alertes avec statut de résolution)
- Statistiques des alertes (déclenchées, résolues, notifications envoyées)

**Implémentation** : [ccbt/interface/terminal_dashboard.py:AlertsDashboardScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L1201)

**Formatage de Sévérité** :
- **CRITIQUE** : Rouge gras
- **ERREUR** : Rouge
- **AVERTISSEMENT** : Jaune
- **INFO** : Atténué

**Navigation** : Appuyez sur `Échap` ou `q` pour revenir au tableau de bord principal

### Écran de l'Explorateur de Métriques

**Accès** : Appuyez sur `e` depuis le tableau de bord principal

**Objectif** : Explorer toutes les métriques disponibles avec filtrage et vues détaillées.

**Fonctionnalités** :
- Liste complète des métriques de MetricsCollector
- Filtrer/rechercher par nom ou description de métrique
- Panneau d'informations détaillées sur les métriques
- Type de métrique, description, agrégation, rétention
- Valeurs actuelles et agrégées
- Étiquettes et métadonnées

**Implémentation** : [ccbt/interface/terminal_dashboard.py:MetricsExplorerScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L1376)

**Utilisation** :
- Tapez dans le champ de filtre et appuyez sur `Entrée` pour filtrer les métriques
- Naviguez avec les touches fléchées pour sélectionner les métriques
- Consultez les informations détaillées dans le panneau de détails ci-dessous

**Navigation** : Appuyez sur `Échap` ou `q` pour revenir au tableau de bord principal

## Écrans de Configuration

Bitonic fournit des écrans de configuration pour gérer les paramètres globaux et par torrent.

### Écran de Configuration Globale

**Accès** : Appuyez sur `g` depuis le tableau de bord principal

**Objectif** : Configurer les paramètres globaux de l'application.

**Fonctionnalités** :
- Navigation de configuration basée sur les sections
- Champs de configuration modifiables avec validation
- Enregistrer en temps d'exécution ou dans un fichier
- Détection des modifications non enregistrées avec dialogue de confirmation

**Implémentation** : [ccbt/interface/terminal_dashboard.py:GlobalConfigMainScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L1793)

**Sections Disponibles** :
- Configuration réseau
- Paramètres I/O disque
- Découverte (DHT, PEX, trackers)
- Observabilité (journalisation, métriques, traçage)
- Paramètres de sécurité
- Et plus encore...

**Navigation** : Appuyez sur `Échap` ou `q` pour revenir au tableau de bord principal

### Écran de Configuration par Torrent

**Accès** : Appuyez sur `t` depuis le tableau de bord principal

**Objectif** : Configurer les paramètres pour les torrents individuels.

**Fonctionnalités** :
- Interface de sélection de torrent
- Configuration des limites de débit (téléchargement/téléversement)
- Gestion de la priorité de la file
- Statut de sélection des fichiers
- Opérations sur les torrents (annonce, scrape, pause, reprise, etc.)

**Implémentation** : [ccbt/interface/terminal_dashboard.py:PerTorrentConfigMainScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L2241)

**Opérations Disponibles** :
- Définir les limites de débit (KiB/s, 0 = illimité)
- Changer la priorité de la file
- Forcer l'annonce (touche `a`)
- Forcer le scrape (touche `s`)
- Actualiser PEX (touche `e`)
- Recalculer le hash du torrent (touche `h`)
- Mettre en pause/Reprendre le torrent (touches `p`/`r`)
- Supprimer le torrent (touche `Suppr`)

**Navigation** : Appuyez sur `Échap` ou `q` pour revenir au tableau de bord principal

## Raccourcis Clavier

Tous les raccourcis clavier sont définis dans [ccbt/interface/terminal_dashboard.py:on_key](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L505) et [ccbt/interface/terminal_dashboard.py:BINDINGS](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L337).

### Navigation
- `↑/↓` - Naviguer dans la liste des torrents (navigation DataTable)
- `Entrée` - Gérer la sélection du navigateur de fichiers. Voir [ccbt/interface/terminal_dashboard.py:714](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L714)

### Contrôle des Torrents
- `P` / `p` - Mettre en pause le torrent sélectionné. Voir [ccbt/interface/terminal_dashboard.py:534](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L534)
- `R` / `r` - Reprendre le torrent sélectionné. Voir [ccbt/interface/terminal_dashboard.py:541](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L541)
- `Suppr` - Supprimer le torrent sélectionné (avec confirmation). Voir [ccbt/interface/terminal_dashboard.py:510](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L510)
- `y` - Confirmer la suppression. Voir [ccbt/interface/terminal_dashboard.py:523](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L523)
- `n` - Annuler la suppression. Voir [ccbt/interface/terminal_dashboard.py:530](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L530)

### Actions Avancées
- `a` / `A` - Forcer l'annonce (lorsqu'un torrent est sélectionné). Voir [ccbt/interface/terminal_dashboard.py:3182](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3182)
- `s` / `S` - Forcer le scrape (lorsqu'un torrent est sélectionné). Voir [ccbt/interface/terminal_dashboard.py:3197](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3197)
- `e` / `E` - Actualiser PEX (lorsqu'un torrent est sélectionné). Voir [ccbt/interface/terminal_dashboard.py:3207](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3207)
- `h` / `H` - Recalculer le hash du torrent (lorsqu'un torrent est sélectionné). Voir [ccbt/interface/terminal_dashboard.py:3217](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3217)
- `x` / `X` - Exporter un instantané de session. Voir [ccbt/interface/terminal_dashboard.py:3227](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3227)

### Navigation des Écrans de Surveillance
- `s` - Ouvrir l'écran des Ressources Système. Voir [ccbt/interface/terminal_dashboard.py:action_system_resources](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3880)
- `m` - Ouvrir l'écran des Métriques de Performance. Voir [ccbt/interface/terminal_dashboard.py:action_performance_metrics](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3884)
- `n` - Ouvrir l'écran de Qualité du Réseau. Voir [ccbt/interface/terminal_dashboard.py:action_network_quality](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3888)
- `h` - Ouvrir l'écran des Tendances Historiques. Voir [ccbt/interface/terminal_dashboard.py:action_historical_trends](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3892)
- `a` - Ouvrir l'écran du Tableau de Bord des Alertes. Voir [ccbt/interface/terminal_dashboard.py:action_alerts_dashboard](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3896)
- `e` - Ouvrir l'écran de l'Explorateur de Métriques. Voir [ccbt/interface/terminal_dashboard.py:action_metrics_explorer](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3900)

### Écrans de Configuration
- `g` - Ouvrir l'écran de Configuration Globale. Voir [ccbt/interface/terminal_dashboard.py:action_global_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3870)
- `t` - Ouvrir l'écran de Configuration par Torrent. Voir [ccbt/interface/terminal_dashboard.py:action_torrent_config](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3875)

### Limitation de Débit
- `1` - Désactiver les limites de débit. Voir [ccbt/interface/terminal_dashboard.py:627](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L627)
- `2` - Définir les limites de débit à 1024 KiB/s. Voir [ccbt/interface/terminal_dashboard.py:635](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L635)

### Contrôle du Tableau de Bord
- `Q` / `q` - Quitter le tableau de bord. Voir [ccbt/interface/terminal_dashboard.py:507](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L507)
- `/` - Ouvrir le champ de filtre. Voir [ccbt/interface/terminal_dashboard.py:548](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L548)
- `:` - Ouvrir la palette de commandes. Voir [ccbt/interface/terminal_dashboard.py:561](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L561)
- `m` / `M` - Basculer l'intervalle de collecte des métriques. Voir [ccbt/interface/terminal_dashboard.py:645](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L645)
- `R` - Basculer l'intervalle de rafraîchissement du tableau de bord. Voir [ccbt/interface/terminal_dashboard.py:659](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L659)
- `t` / `T` - Basculer le thème clair/sombre. Voir [ccbt/interface/terminal_dashboard.py:673](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L673)
- `c` / `C` - Basculer le mode compact. Voir [ccbt/interface/terminal_dashboard.py:681](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L681)
- `k` / `K` - Reconnaître toutes les alertes actives. Voir [ccbt/interface/terminal_dashboard.py:723](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L723)

### Ajout de Torrents
- `i` / `I` - Ajout rapide de torrent. Voir [ccbt/interface/terminal_dashboard.py:702](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L702)
- `o` / `O` - Ajout avancé de torrent. Voir [ccbt/interface/terminal_dashboard.py:706](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L706)
- `b` / `B` - Parcourir pour un fichier torrent. Voir [ccbt/interface/terminal_dashboard.py:710](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L710)

## Configuration

Les paramètres du tableau de bord sont configurés dans [ccbt.toml:185-191](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L185-L191) :

- `refresh_interval` : Intervalle de rafraîchissement de l'interface utilisateur en secondes (par défaut : 1.0)
- `default_view` : Vue par défaut du tableau de bord

Les règles d'alerte sont chargées depuis le chemin spécifié dans [ccbt.toml:170](https://github.com/ccBittorrent/ccbt/blob/main/ccbt.toml#L170) (`alerts_rules_path`). Voir [ccbt/interface/terminal_dashboard.py:363-381](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L363-L381) pour le chargement automatique.

## Palette de Commandes

Appuyez sur `:` pour ouvrir la palette de commandes. Commandes disponibles :
- `pause` - Mettre en pause le torrent sélectionné
- `resume` - Reprendre le torrent sélectionné
- `remove` - Supprimer le torrent sélectionné
- `announce` - Forcer l'annonce
- `scrape` - Forcer le scrape
- `pex` - Actualiser PEX
- `rehash` - Recalculer le hash du torrent
- `limit <down> <up>` - Définir les limites de débit (KiB/s)
- `backup <path>` - Sauvegarder un point de contrôle
- `restore <path>` - Restaurer un point de contrôle

Implémentation : [ccbt/interface/terminal_dashboard.py:_run_command](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L776)

## Filtrage

Appuyez sur `/` pour filtrer les torrents par nom ou statut. Implémentation : [ccbt/interface/terminal_dashboard.py:_apply_filter_and_update](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L762)

## Intégration avec la Surveillance

Bitonic s'intègre avec le système de surveillance de ccBitTorrent :
- Collecte de métriques via [ccbt/monitoring/metrics_collector.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/monitoring/metrics_collector.py)
- Gestion des alertes via [ccbt/monitoring/alert_manager.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/monitoring/alert_manager.py)
- Système de plugins via [ccbt/plugins/base.py](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/plugins/base.py)
- Intégration MetricsPlugin pour les métriques basées sur les événements. Voir [ccbt/interface/terminal_dashboard.py:_get_metrics_plugin](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L626)
- Suivi des métriques système. Voir [ccbt/interface/terminal_dashboard.py:3001-3019](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L3001-L3019)

### Sources de Métriques

Bitonic affiche les métriques de plusieurs sources :

1. **MetricsCollector** : Métriques au niveau système et de performance
   - Utilisation CPU, mémoire, disque
   - Statistiques I/O réseau
   - Connexions de pairs, vitesses, statistiques de pièces

2. **MetricsPlugin** : Métriques basées sur les événements
   - Vitesses de téléchargement de pièces
   - Vitesses moyennes des torrents
   - Agrégations basées sur les événements

3. **AsyncSessionManager** : Statistiques au niveau de la session
   - Taux globaux de téléchargement/téléversement
   - Statut par torrent
   - Informations sur les pairs

### Intégration du Gestionnaire de Plugins

Bitonic utilise le singleton du gestionnaire de plugins global pour accéder aux plugins :
- Accès via la fonction `get_plugin_manager()`. Voir [ccbt/plugins/base.py:get_plugin_manager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/plugins/base.py#L403)
- Découverte de MetricsPlugin via plusieurs méthodes (PluginManager, bus d'événements, attributs de session)
- Gestion gracieuse lorsque les plugins ne sont pas disponibles

## Dépannage

### Le Tableau de Bord ne Démarre Pas
1. Vérifiez si Textual est installé : `uv pip install textual>=0.73.0`
2. Vérifiez que le terminal supporte Unicode et les couleurs
3. Vérifiez les messages d'erreur dans le terminal

L'implémentation gère la disponibilité de Textual : [ccbt/interface/terminal_dashboard.py:46-172](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L46-L172)

### Problèmes de Performance
1. Augmentez l'intervalle de rafraîchissement : `--refresh 2.0` ou appuyez sur `R` pour faire défiler les intervalles
2. Utilisez le mode compact : Appuyez sur `c` pour basculer
3. Désactivez les graphiques de vitesse si non nécessaires

### Données Manquantes
1. Assurez-vous que les torrents téléchargent activement
2. Vérifiez la connectivité réseau
3. Vérifiez que les connexions de pairs sont établies

## Architecture

Bitonic utilise :
- **Textual** : Framework d'interface utilisateur terminal. Voir [ccbt/interface/terminal_dashboard.py:47-60](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L47-L60)
- **Rich** : Texte enrichi et formatage élégant
- **AsyncSessionManager** : Gestion de session. Voir [ccbt/session/session.py:AsyncSessionManager](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/session/session.py#L605)
- **MetricsCollector** : Collecte de métriques (singleton via `get_metrics_collector()`)
- **AlertManager** : Gestion des alertes (singleton via `get_alert_manager()`)
- **PluginManager** : Gestion des plugins (singleton via `get_plugin_manager()`)

### Architecture des Écrans

Bitonic suit une structure d'écrans hiérarchique :

```
TerminalDashboard (Application Principale)
├── ConfigScreen (Classe de base)
│   ├── GlobalConfigMainScreen
│   ├── GlobalConfigDetailScreen
│   ├── PerTorrentConfigMainScreen
│   └── TorrentConfigDetailScreen
└── MonitoringScreen (Classe de base)
    ├── SystemResourcesScreen
    ├── PerformanceMetricsScreen
    ├── NetworkQualityScreen
    ├── HistoricalTrendsScreen
    ├── AlertsDashboardScreen
    └── MetricsExplorerScreen
```

**Classes de Base** :
- **MonitoringScreen** : Classe de base pour tous les écrans de surveillance avec fonctionnalités communes (intervalles de rafraîchissement, navigation, gestion des erreurs). Voir [ccbt/interface/terminal_dashboard.py:MonitoringScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L558)
- **ConfigScreen** : Classe de base pour les écrans de configuration avec détection des modifications non enregistrées. Voir [ccbt/interface/terminal_dashboard.py:ConfigScreen](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L433)

**Widgets Réutilisables** :
- **ProgressBarWidget** : Barres de progression pour les pourcentages. Voir [ccbt/interface/terminal_dashboard.py:ProgressBarWidget](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L309)
- **MetricsTableWidget** : Affichage des métriques en format tableau. Voir [ccbt/interface/terminal_dashboard.py:MetricsTableWidget](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L335)
- **SparklineGroup** : Plusieurs sparklines avec étiquettes. Voir [ccbt/interface/terminal_dashboard.py:SparklineGroup](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L379)

**Dialogues de Confirmation** :
- **ConfirmationDialog** : Dialogue modal pour les invites de confirmation (par exemple, modifications non enregistrées). Voir [ccbt/interface/terminal_dashboard.py:ConfirmationDialog](https://github.com/ccBittorrent/ccbt/blob/main/ccbt/interface/terminal_dashboard.py#L471)

Pour plus d'informations, voir :
- [Référence API](API.md) - Documentation de l'API Python incluant les fonctionnalités de surveillance
- [btbt CLI Reference](btbt-cli.md) - Command-line interface