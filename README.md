# 📺 XtreamerPy

> Client de bureau Python pour les abonnements IPTV Xtream Codes.
> Chaînes Live + EPG, films, séries, favoris, export M3U et lecture VLC intégrée.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15-green)](https://pypi.org/project/PyQt5/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()
[![License](https://img.shields.io/badge/License-MIT-orange)](LICENSE)

🔗 **Repo :** [github.com/Edmondio/XtreamerPy](https://github.com/Edmondio/XtreamerPy)

---

## ✨ Fonctionnalités

- 🔐 **Connexion** à n'importe quel panel Xtream Codes (URL + identifiants)
- 📺 **3 onglets** : Chaînes Live, Films (VOD), Séries — navigation par catégories
- 📅 **Guide TV (EPG)** intégré dans l'onglet Live (via `get_short_epg`)
- ⭐ **Système de favoris** persistants par catégorie (Live / Films / Séries)
- 🔍 **Recherche instantanée** dans chaque onglet
- ▶️ **Lecture intégrée avec VLC** : clic, double-clic ou clic droit
- 📼 **Navigation par épisodes** pour les séries (saisons + épisodes)
- ⬇️ **Export M3U flexible** :
  - M3U complet du serveur (téléchargement direct)
  - **M3U des favoris uniquement** (généré localement, chaînes + films)
- 📋 **Copie d'URL** (M3U ou stream individuel)
- 🎭 **6 User-Agents** prédéfinis (VLC, IPTV Smarters, TiviMate, Kodi, Firefox)
- 🔁 **Retry automatique** sur erreurs réseau et 5xx
- 💾 **Mémorisation des identifiants** et des favoris (local)
- ℹ️ **Infos compte en temps réel** (statut, expiration, connexions)

---

## 📦 Installation

### Prérequis

- **Python 3.8+**
- **VLC media player** ([videolan.org](https://www.videolan.org/vlc/)) — auto-détecté
- Un abonnement IPTV au format Xtream Codes

### Dépendances

```bash
pip install -r requirements.txt
```

Ou directement :

```bash
pip install PyQt5 requests urllib3
```

### Lancement

```bash
python xtreamerpy.py
```

---

## 🚀 Utilisation

### 1. Connexion

| Champ | Description |
|-------|-------------|
| **Host** | URL complète avec port, ex : `http://exemple.com:8080` |
| **Utilisateur / Mot de passe** | Fournis par ton provider |
| **User-Agent** | Laisse sur `VLC` par défaut, change si la connexion échoue |
| **Chemin VLC** | Auto-détecté, sinon clique sur *Parcourir...* |
| **Vérifier SSL** | Décoche si certificat auto-signé |
| **Mémoriser** | Sauvegarde dans `~/.xtreamerpy.json` |

### 2. Navigation

```
┌──────────────┬─────────────────────┬─────────────────────┐
│ ⭐ Favoris   │ ⭐ TF1              │ Détails             │
│ 📂 Tout      │    France 2         │                     │
│ FR Generale  │ ⭐ M6               │ ▶️ Lire avec VLC    │
│ FR Sport     │    BFM TV           │ ☆ Ajouter aux fav.  │
│ FR Cinema    │    LCI              │ 📋 Copier URL       │
│ ...          │ ...                 │                     │
│              │                     │ 📅 Guide TV (EPG)   │
└──────────────┴─────────────────────┴─────────────────────┘
```

- Catégorie spéciale **⭐ Favoris** en haut avec compteur
- Les éléments en favoris ont une **étoile** devant leur nom
- L'**EPG** se charge automatiquement quand tu cliques sur une chaîne Live

### 3. Lecture VLC

**3 façons :**
- 🖱️ Bouton **▶️ Lire avec VLC**
- 🖱️🖱️ **Double-clic** sur un élément
- 🖱️➡️ **Clic droit** → menu contextuel

Pour les séries, le bouton ouvre une fenêtre saisons/épisodes — double-clic sur un épisode pour le lancer.

### 4. Favoris

- Sélectionne un élément → **☆ Ajouter aux favoris** dans le panneau de droite
- Ou clic droit → **Ajouter aux favoris**
- Compteur global dans la barre du haut : `⭐ N favoris`
- Catégorie **⭐ Favoris** dans chaque onglet
- **Persistants** entre les sessions (stockés dans `~/.xtreamerpy.json`)

### 5. Export M3U

Clique sur **⬇️ Exporter M3U...** puis choisis :

- **📦 M3U complet du serveur** : télécharge tout (chaînes + films + séries) via `get.php`
- **⭐ Favoris uniquement** : génère localement un M3U avec tes favoris Live + Films
  *(les séries sont exclues car ce sont des collections multi-épisodes)*

Format **M3U Plus** standard avec attributs `tvg-id`, `tvg-name`, `tvg-logo`, `group-title`.

---

## 🛠️ Dépannage

### Erreur `ConnectionResetError 10054` ou `Connection aborted`

**Filtre User-Agent** côté serveur. Solutions dans l'ordre :

1. Change le User-Agent (essaie `IPTV Smarters` puis `TiviMate`)
2. Vérifie le **schéma** (`http://` ou `https://`) et le **port**
3. Décoche `Vérifier SSL` si certificat auto-signé
4. Teste l'URL dans un navigateur : `http://HOST:PORT/player_api.php?username=X&password=Y`

### `Auth refused (auth=0)`

Identifiants incorrects ou abonnement expiré.

### VLC ne se lance pas

- Vérifie l'installation : [videolan.org](https://www.videolan.org/vlc/)
- Bouton **⚙️ Chemin VLC** dans la barre du haut
- Linux : `sudo apt install vlc`

### EPG vide ou erreur

Tous les serveurs Xtream n'exposent pas l'EPG. Le message *« EPG indisponible »* apparaît alors. Pas bloquant pour le reste.

### Réponse non-JSON

Page HTML d'erreur du serveur. Souvent un mauvais host/port, panel down, ou IP bannie.

---

## 📁 Structure du projet

```
XtreamerPy/
├── xtreamerpy.py         # Application principale (un seul fichier)
├── requirements.txt      # Dépendances Python
├── README.md             # Ce fichier
└── LICENSE               # Licence MIT
```

**Fichier de config** : `~/.xtreamerpy.json`

```json
{
  "host": "...",
  "username": "...",
  "password": "...",
  "user_agent_label": "VLC (recommande)",
  "verify_ssl": true,
  "vlc_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",
  "favorites": {
    "live": [...],
    "vod": [...],
    "series": [...]
  }
}
```

---

## 🔧 Endpoints Xtream Codes utilisés

| Endpoint | Description |
|----------|-------------|
| `player_api.php` | Infos compte (auth, expiration, connexions) |
| `?action=get_live_categories` | Catégories des chaînes live |
| `?action=get_live_streams` | Liste des chaînes |
| `?action=get_vod_categories` | Catégories des films |
| `?action=get_vod_streams` | Liste des films |
| `?action=get_series_categories` | Catégories des séries |
| `?action=get_series` | Liste des séries |
| `?action=get_series_info&series_id=X` | Saisons/épisodes |
| `?action=get_short_epg&stream_id=X&limit=N` | **Guide TV (EPG)** |
| `get.php?type=m3u_plus` | Fichier M3U complet |
| `/live/{user}/{pass}/{id}.ts` | Stream live |
| `/movie/{user}/{pass}/{id}.{ext}` | Stream film |
| `/series/{user}/{pass}/{id}.{ext}` | Stream épisode |

---

## 🗺️ Roadmap

- [x] EPG (guide TV) via `get_short_epg` dans l'onglet Live
- [x] Système de favoris (étoile sur chaque élément)
- [x] Export M3U filtré (favoris uniquement)
- [ ] Export M3U par catégorie courante
- [ ] Affichage des affiches/logos (`stream_icon`)
- [ ] Lecteur intégré via `python-vlc` (sans VLC externe)
- [ ] Cache local des catégories pour démarrage plus rapide
- [ ] Support multi-comptes (switch entre serveurs)
- [ ] Thème sombre
- [ ] EPG complet (`get_simple_data_table`) avec grille horaire
- [ ] Historique des chaînes regardées

---

## ⚠️ Avertissement légal

**XtreamerPy** est un outil technique conçu pour interagir avec l'API Xtream Codes. Il ne fournit **aucun contenu**.

- ✅ Utilise-le uniquement avec des **abonnements IPTV légitimes** auxquels tu as souscrit
- ✅ Tu es responsable du respect des **lois locales** sur la diffusion et la consommation de contenus
- ❌ Les développeurs **n'endossent aucune responsabilité** quant à l'usage de cet outil
- ❌ Aucune assistance ne sera fournie pour l'accès à des contenus piratés

---

## 🤝 Contribution

Les PR sont les bienvenues. Pour les changements majeurs, ouvre d'abord une issue.

```bash
git clone https://github.com/Edmondio/XtreamerPy.git
cd XtreamerPy
pip install -r requirements.txt
python xtreamerpy.py
```

---

## 📄 Licence

[MIT](LICENSE)

---

## 🙏 Crédits

- [PyQt5](https://riverbankcomputing.com/software/pyqt/) — Interface graphique
- [Requests](https://requests.readthedocs.io/) — Client HTTP
- [VLC](https://www.videolan.org/vlc/) — Lecture des streams
- Spécification API Xtream Codes (documentation communautaire)

---

<p align="center">
  Made with ❤️ in Python by <a href="https://github.com/Edmondio">@Edmondio</a>
</p>
