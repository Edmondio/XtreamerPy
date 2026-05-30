# 📺 Xtream Codes Client

Client de bureau **PyQt5** pour explorer un abonnement IPTV Xtream Codes : chaînes Live, films (VOD), séries — avec lecture directe dans VLC, recherche, export M3U et gestion multi-User-Agent.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/License-MIT-orange)

---

## ✨ Fonctionnalités

- 🔐 **Connexion sécurisée** à n'importe quel panel Xtream Codes (URL + username + password)
- 📺 **3 onglets** : Chaînes Live, Films (VOD), Séries — chacun avec navigation par catégories
- 🔍 **Recherche instantanée** dans chaque onglet
- ▶️ **Lecture intégrée avec VLC** : clic sur le bouton, double-clic ou clic droit
- 📼 **Navigation par épisodes** pour les séries (saisons + épisodes via `get_series_info`)
- ⬇️ **Téléchargement du fichier M3U** complet avec barre de progression
- 📋 **Copie d'URL** (M3U ou stream individuel) en un clic
- 🎭 **6 User-Agents** prédéfinis (VLC, IPTV Smarters, TiviMate, Kodi, Firefox, requests)
- 🔁 **Retry automatique** sur erreurs réseau et 5xx
- 💾 **Mémorisation des identifiants** (optionnel, stockés en local)
- ℹ️ **Infos compte en temps réel** : statut, expiration, connexions actives/max

---

## 📦 Installation

### Prérequis

- **Python 3.8+**
- **VLC media player** ([videolan.org](https://www.videolan.org/vlc/)) — auto-détecté au lancement
- Un abonnement IPTV au format Xtream Codes (URL + identifiants)

### Installation des dépendances

```bash
pip install -r requirements.txt
```

Ou directement :

```bash
pip install PyQt5 requests urllib3
```

### Lancement

```bash
python xtream_client.py
```

---

## 🚀 Utilisation

### 1. Connexion

Au lancement, une fenêtre de connexion s'affiche :

| Champ | Description |
|-------|-------------|
| **Host** | URL complète avec port, ex : `http://exemple.com:8080` |
| **Utilisateur** | Le username fourni par ton provider |
| **Mot de passe** | Le password fourni par ton provider |
| **User-Agent** | Laisse sur `VLC (recommandé)` par défaut — change si la connexion échoue |
| **Chemin VLC** | Auto-détecté, sinon clique sur *Parcourir...* |
| **Vérifier SSL** | Décoche si certificat auto-signé |
| **Mémoriser** | Sauvegarde les identifiants dans `~/.xtream_client.json` |

### 2. Navigation

- Sélectionne une catégorie à gauche → la liste des contenus s'affiche au centre
- Clique sur un élément → les détails apparaissent à droite (synopsis, note, URL, etc.)
- Tape dans la barre de recherche pour filtrer la catégorie courante

### 3. Lecture

**3 façons de lancer un stream :**
- 🖱️ Sélectionne un élément puis clique sur **▶️ Lire avec VLC**
- 🖱️🖱️ **Double-clic** sur un élément de la liste
- 🖱️➡️ **Clic droit** → menu contextuel

Pour les séries, le bouton ouvre une fenêtre avec les saisons/épisodes — double-clic sur un épisode pour le lancer.

### 4. Export M3U

- **⬇️ Télécharger le M3U** : sauvegarde le fichier `playlist.m3u` complet (chaînes + VOD + séries)
- **📋 Copier URL M3U** : copie le lien direct pour le coller dans VLC/Kodi/TiviMate

---

## 🛠️ Dépannage

### Erreur `ConnectionResetError 10054` ou `Connection aborted`

C'est typiquement un **filtre User-Agent côté serveur**. Solutions à essayer dans l'ordre :

1. Change le User-Agent dans la fenêtre de login (essaie `IPTV Smarters` puis `TiviMate`)
2. Vérifie que l'URL est complète avec **schéma** (`http://` ou `https://`) et **port**
3. Décoche `Vérifier SSL` si le serveur a un certificat auto-signé
4. Teste l'URL dans un navigateur : `http://TON_HOST:PORT/player_api.php?username=X&password=Y`
   - Si ça affiche du JSON → c'est sûrement un filtre UA
   - Si ça ne marche pas non plus → IP bannie, mauvais port, ou serveur down

### Erreur `Auth refused (auth=0)`

Identifiants incorrects ou abonnement expiré.

### VLC ne se lance pas

- Vérifie que VLC est installé : [videolan.org](https://www.videolan.org/vlc/)
- Clique sur **⚙️ Chemin VLC** dans la barre du haut pour configurer manuellement
- Sur Linux : `sudo apt install vlc` ou équivalent

### Réponse non-JSON

Le serveur renvoie une page HTML d'erreur. Souvent un mauvais host/port, ou le panel est down.

---

## 📁 Structure du projet

```
xtream-client/
├── xtream_client.py      # Application principale (un seul fichier)
├── requirements.txt      # Dépendances Python
├── README.md             # Ce fichier
└── LICENSE               # Licence MIT
```

**Fichier de config** : `~/.xtream_client.json` (créé automatiquement si « Mémoriser » est coché)

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
| `?action=get_series_info&series_id=X` | Saisons/épisodes d'une série |
| `get.php?type=m3u_plus` | Fichier M3U complet |
| `/live/{user}/{pass}/{id}.ts` | Stream live direct |
| `/movie/{user}/{pass}/{id}.{ext}` | Stream film direct |
| `/series/{user}/{pass}/{id}.{ext}` | Stream épisode direct |

---

## 🗺️ Roadmap

- [ ] EPG (guide TV) via `get_short_epg` dans l'onglet Live
- [ ] Système de favoris (étoile sur chaque élément)
- [ ] Export M3U filtré (favoris uniquement ou par catégorie)
- [ ] Lecteur intégré via `python-vlc` (sans VLC externe)
- [ ] Cache local des catégories pour démarrage plus rapide
- [ ] Support multi-comptes (switch entre plusieurs serveurs)
- [ ] Thème sombre
- [ ] Affichage des affiches/logos (champ `stream_icon`)

---

## ⚠️ Avertissement légal

Ce client est un **outil technique** conçu pour interagir avec l'API Xtream Codes. Il ne fournit **aucun contenu** par lui-même.

- ✅ Utilise-le uniquement avec des **abonnements IPTV légitimes** auxquels tu as souscrit
- ✅ Tu es responsable du respect des **lois locales** sur la diffusion et la consommation de contenus
- ❌ Les développeurs **n'endossent aucune responsabilité** quant à l'usage qui est fait de cet outil
- ❌ Aucune assistance ne sera fournie pour l'accès à des contenus piratés

---

## 🤝 Contribution

Les PR sont les bienvenues. Pour les changements majeurs, ouvre d'abord une issue pour discuter de ce que tu veux changer.

### Workflow

```bash
git clone https://github.com/TON_USER/xtream-client.git
cd xtream-client
pip install -r requirements.txt
python xtream_client.py
```

---

## 📄 Licence

[MIT](LICENSE) — fais-en ce que tu veux, mais sans garantie.

---

## 🙏 Crédits

- [PyQt5](https://riverbankcomputing.com/software/pyqt/) — Interface graphique
- [Requests](https://requests.readthedocs.io/) — Client HTTP
- [VLC](https://www.videolan.org/vlc/) — Lecture des streams
- Spécification API Xtream Codes (documentation communautaire)
