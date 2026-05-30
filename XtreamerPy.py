"""
XtreamerPy - Client desktop Xtream Codes
https://github.com/Edmondio/XtreamerPy

Dependances :
    pip install PyQt5 requests urllib3

Lancement :
    python xtreamerpy.py
"""

import sys
import json
import os
import shutil
import subprocess
import platform
import base64
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QListWidget,
    QListWidgetItem, QSplitter, QMessageBox, QFileDialog, QDialog,
    QFormLayout, QCheckBox, QStatusBar, QProgressBar, QTextEdit, QComboBox,
    QTreeWidget, QTreeWidgetItem, QMenu, QAction, QRadioButton, QButtonGroup,
    QGroupBox, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

APP_NAME = "XtreamerPy"
APP_VERSION = "1.1.0"
CONFIG_FILE = os.path.expanduser("~/.xtreamerpy.json")

USER_AGENTS = {
    "VLC (recommande)":      "VLC/3.0.20 LibVLC/3.0.20",
    "IPTV Smarters":         "IPTVSmartersPlayer",
    "TiviMate":              "TiviMate/4.7.0 (Linux;Android 11)",
    "Kodi":                  "Kodi/20.2 (Windows NT 10.0; Win64; x64) App_Bitness/64 Version/20.2",
    "Mozilla Firefox":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "python-requests (debug)": None,
}

STAR_FILLED = "⭐"
STAR_EMPTY = "☆"


# ---------------------------------------------------------------------------
# Config + Favoris
# ---------------------------------------------------------------------------
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Erreur sauvegarde config : {e}")


class FavoritesManager:
    """Gere les favoris persistants pour live/vod/series."""

    def __init__(self):
        cfg = load_config()
        favs = cfg.get("favorites", {})
        self.data = {
            "live": favs.get("live", []),
            "vod": favs.get("vod", []),
            "series": favs.get("series", []),
        }

    def _key(self, item):
        return item.get("stream_id") or item.get("series_id") or item.get("id")

    def save(self):
        cfg = load_config()
        cfg["favorites"] = self.data
        save_config(cfg)

    def is_favorite(self, kind, item):
        kid = self._key(item)
        return any(self._key(f) == kid for f in self.data.get(kind, []))

    def toggle(self, kind, item):
        """Retourne True si maintenant en favoris, False sinon."""
        kid = self._key(item)
        if self.is_favorite(kind, item):
            self.data[kind] = [f for f in self.data[kind] if self._key(f) != kid]
            self.save()
            return False
        else:
            # Stocker une copie reduite pour ne pas tout dupliquer
            self.data[kind].append(dict(item))
            self.save()
            return True

    def get_all(self, kind):
        return list(self.data.get(kind, []))

    def count(self, kind):
        return len(self.data.get(kind, []))


# ---------------------------------------------------------------------------
# Detection VLC
# ---------------------------------------------------------------------------
def find_vlc():
    system = platform.system()
    if system == "Windows":
        candidates = [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ]
    elif system == "Darwin":
        candidates = ["/Applications/VLC.app/Contents/MacOS/VLC"]
    else:
        candidates = ["/usr/bin/vlc", "/usr/local/bin/vlc", "/snap/bin/vlc"]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return shutil.which("vlc")


def launch_vlc(vlc_path, url, user_agent=None, title=None):
    if not vlc_path or not os.path.isfile(vlc_path):
        raise RuntimeError(
            "VLC introuvable. Installe VLC ou configure son chemin "
            "via le bouton 'Chemin VLC'."
        )
    args = [vlc_path]
    if user_agent:
        args.append(f"--http-user-agent={user_agent}")
    if title:
        args.append(f"--meta-title={title}")
    args.append(url)
    kwargs = {}
    if platform.system() == "Windows":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)


# ---------------------------------------------------------------------------
# Helpers EPG
# ---------------------------------------------------------------------------
def decode_b64(s):
    if not s:
        return ""
    try:
        return base64.b64decode(s).decode("utf-8", errors="replace")
    except Exception:
        return s


def format_epg_time(ts):
    """Convertit un timestamp Xtream (str ou int) en heure lisible."""
    if not ts:
        return "?"
    try:
        if isinstance(ts, str) and "-" in ts:
            # Format "YYYY-MM-DD HH:MM:SS"
            dt = datetime.strptime(ts.split(" ")[0] + " " + ts.split(" ")[1],
                                   "%Y-%m-%d %H:%M:%S")
        else:
            dt = datetime.fromtimestamp(int(ts))
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return str(ts)


# ---------------------------------------------------------------------------
# API Xtream Codes
# ---------------------------------------------------------------------------
class XtreamAPI:
    def __init__(self, host, username, password, user_agent=None, verify_ssl=True):
        host = host.strip().rstrip("/")
        if not host.startswith(("http://", "https://")):
            host = "http://" + host
        self.host = host
        self.username = username
        self.password = password
        self.user_agent = user_agent
        self.verify_ssl = verify_ssl
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.session = requests.Session()
        retry = Retry(
            total=3, backoff_factor=1.5,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        if user_agent:
            self.session.headers.update({"User-Agent": user_agent})
        self.session.headers.update({
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        })
        self.base = f"{self.host}/player_api.php"

    def _get(self, action=None, **params):
        p = {"username": self.username, "password": self.password}
        if action:
            p["action"] = action
        p.update(params)
        try:
            r = self.session.get(self.base, params=p, timeout=30, verify=self.verify_ssl)
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(
                "Connexion refusee/coupee par le serveur.\n\n"
                "Causes frequentes :\n"
                "- User-Agent bloque (essaie VLC ou IPTVSmarters)\n"
                "- Mauvais port ou mauvais schema (http vs https)\n"
                "- IP bannie ou geo-bloquee\n\n"
                f"Detail : {e}"
            )
        except requests.exceptions.Timeout:
            raise RuntimeError("Le serveur ne repond pas (timeout 30s).")
        except requests.exceptions.SSLError as e:
            raise RuntimeError(f"Erreur SSL. Decoche 'Verifier SSL'.\n\nDetail : {e}")
        r.raise_for_status()
        try:
            return r.json()
        except json.JSONDecodeError:
            snippet = r.text[:200].replace("\n", " ")
            raise RuntimeError(f"Reponse non-JSON. Debut : {snippet}")

    def user_info(self):
        return self._get()

    def live_categories(self):
        return self._get("get_live_categories")

    def live_streams(self, category_id=None):
        if category_id is not None:
            return self._get("get_live_streams", category_id=category_id)
        return self._get("get_live_streams")

    def vod_categories(self):
        return self._get("get_vod_categories")

    def vod_streams(self, category_id=None):
        if category_id is not None:
            return self._get("get_vod_streams", category_id=category_id)
        return self._get("get_vod_streams")

    def series_categories(self):
        return self._get("get_series_categories")

    def series(self, category_id=None):
        if category_id is not None:
            return self._get("get_series", category_id=category_id)
        return self._get("get_series")

    def series_info(self, series_id):
        return self._get("get_series_info", series_id=series_id)

    def short_epg(self, stream_id, limit=10):
        return self._get("get_short_epg", stream_id=stream_id, limit=limit)

    def m3u_url(self, output="ts"):
        return (
            f"{self.host}/get.php?username={self.username}"
            f"&password={self.password}&type=m3u_plus&output={output}"
        )

    def stream_url(self, stream_id, kind="live", ext="ts"):
        if kind == "live":
            return f"{self.host}/live/{self.username}/{self.password}/{stream_id}.{ext}"
        elif kind == "movie":
            return f"{self.host}/movie/{self.username}/{self.password}/{stream_id}.{ext}"
        elif kind == "series":
            return f"{self.host}/series/{self.username}/{self.password}/{stream_id}.{ext}"


# ---------------------------------------------------------------------------
# M3U Generation
# ---------------------------------------------------------------------------
def build_m3u(items, kind, api):
    """Construit un M3U Plus a partir d'une liste d'items live ou vod."""
    lines = ["#EXTM3U"]
    for it in items:
        sid = it.get("stream_id") or it.get("id")
        if not sid:
            continue
        name = it.get("name") or it.get("title", "?")
        tvg_id = it.get("epg_channel_id", "") or ""
        tvg_logo = it.get("stream_icon", "") or ""
        group = it.get("category_name", "") or ""
        if kind == "live":
            ext = "ts"
            url = api.stream_url(sid, "live", ext)
        else:
            ext = it.get("container_extension", "mp4")
            url = api.stream_url(sid, "movie", ext)
        # Escaper les guillemets dans les attributs
        safe_name = str(name).replace('"', "'")
        safe_logo = str(tvg_logo).replace('"', "'")
        safe_group = str(group).replace('"', "'")
        safe_tvg = str(tvg_id).replace('"', "'")
        lines.append(
            f'#EXTINF:-1 tvg-id="{safe_tvg}" tvg-name="{safe_name}" '
            f'tvg-logo="{safe_logo}" group-title="{safe_group}",{safe_name}'
        )
        lines.append(url)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------
class LoaderThread(QThread):
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.finished_ok.emit(self.func(*self.args, **self.kwargs))
        except Exception as e:
            self.failed.emit(str(e))


class M3UDownloadThread(QThread):
    progress = pyqtSignal(int)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, session, url, dest_path, verify_ssl):
        super().__init__()
        self.session = session
        self.url = url
        self.dest_path = dest_path
        self.verify_ssl = verify_ssl

    def run(self):
        try:
            with self.session.get(self.url, stream=True, timeout=120, verify=self.verify_ssl) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                with open(self.dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            self.progress.emit(int(downloaded * 100 / total))
            self.finished_ok.emit(self.dest_path)
        except Exception as e:
            self.failed.emit(str(e))


# ---------------------------------------------------------------------------
# Dialog Export M3U
# ---------------------------------------------------------------------------
class M3UExportDialog(QDialog):
    """Choix du mode d'export M3U."""

    MODE_FULL_SERVER = "full_server"
    MODE_FAVORITES = "favorites"
    MODE_CATEGORY = "category"

    def __init__(self, favorites_count, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Exporter en M3U")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Choisis ce que tu veux exporter :</b>"))

        self.group = QButtonGroup(self)

        self.rb_full = QRadioButton("📦  M3U complet du serveur (tout)")
        self.rb_full.setChecked(True)
        layout.addWidget(self.rb_full)
        layout.addWidget(QLabel(
            "<i style='color:#666;'>Telecharge le fichier directement depuis le serveur "
            "(chaines + films + series).</i>"
        ))

        fav_count_live = favorites_count.get("live", 0)
        fav_count_vod = favorites_count.get("vod", 0)
        total_favs = fav_count_live + fav_count_vod

        self.rb_favs = QRadioButton(
            f"⭐  Favoris uniquement ({fav_count_live} chaines + {fav_count_vod} films)"
        )
        self.rb_favs.setEnabled(total_favs > 0)
        layout.addWidget(self.rb_favs)
        layout.addWidget(QLabel(
            "<i style='color:#666;'>Genere localement un M3U avec tes favoris Live + Films. "
            "Les series ne sont pas incluses (multi-episodes).</i>"
        ))

        self.group.addButton(self.rb_full)
        self.group.addButton(self.rb_favs)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def selected_mode(self):
        if self.rb_favs.isChecked():
            return self.MODE_FAVORITES
        return self.MODE_FULL_SERVER


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - Connexion")
        self.setMinimumWidth(520)

        layout = QFormLayout(self)
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("http://exemple.com:8080")
        self.user_input = QLineEdit()
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.Password)

        self.ua_combo = QComboBox()
        for label in USER_AGENTS.keys():
            self.ua_combo.addItem(label)

        vlc_row = QHBoxLayout()
        self.vlc_input = QLineEdit()
        self.vlc_input.setPlaceholderText("Auto-detecte au demarrage")
        vlc_browse = QPushButton("Parcourir...")
        vlc_browse.clicked.connect(self._browse_vlc)
        vlc_row.addWidget(self.vlc_input)
        vlc_row.addWidget(vlc_browse)
        vlc_widget = QWidget()
        vlc_widget.setLayout(vlc_row)

        self.verify_ssl = QCheckBox("Verifier le certificat SSL")
        self.verify_ssl.setChecked(True)
        self.remember = QCheckBox("Memoriser ces identifiants")

        layout.addRow("Host :", self.host_input)
        layout.addRow("Utilisateur :", self.user_input)
        layout.addRow("Mot de passe :", self.pass_input)
        layout.addRow("User-Agent :", self.ua_combo)
        layout.addRow("Chemin VLC :", vlc_widget)
        layout.addRow("", self.verify_ssl)
        layout.addRow("", self.remember)

        detected = find_vlc()
        if detected:
            self.vlc_input.setText(detected)

        btns = QHBoxLayout()
        self.connect_btn = QPushButton("Se connecter")
        self.connect_btn.clicked.connect(self.accept)
        self.connect_btn.setDefault(True)
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        btns.addWidget(self.connect_btn)
        layout.addRow(btns)

        cfg = load_config()
        if cfg:
            self.host_input.setText(cfg.get("host", ""))
            self.user_input.setText(cfg.get("username", ""))
            self.pass_input.setText(cfg.get("password", ""))
            ua_label = cfg.get("user_agent_label")
            if ua_label and ua_label in USER_AGENTS:
                self.ua_combo.setCurrentText(ua_label)
            self.verify_ssl.setChecked(cfg.get("verify_ssl", True))
            if cfg.get("vlc_path"):
                self.vlc_input.setText(cfg["vlc_path"])
            if cfg.get("host"):
                self.remember.setChecked(True)

    def _browse_vlc(self):
        ext = "vlc.exe (vlc.exe)" if platform.system() == "Windows" else "Tous (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Selectionner VLC", "", ext)
        if path:
            self.vlc_input.setText(path)

    def credentials(self):
        ua_label = self.ua_combo.currentText()
        return {
            "host": self.host_input.text().strip(),
            "username": self.user_input.text().strip(),
            "password": self.pass_input.text(),
            "user_agent_label": ua_label,
            "user_agent": USER_AGENTS.get(ua_label),
            "verify_ssl": self.verify_ssl.isChecked(),
            "vlc_path": self.vlc_input.text().strip(),
            "remember": self.remember.isChecked(),
        }


# ---------------------------------------------------------------------------
# Series Dialog
# ---------------------------------------------------------------------------
class SeriesDetailsDialog(QDialog):
    def __init__(self, api, vlc_path, series_data, parent=None):
        super().__init__(parent)
        self.api = api
        self.vlc_path = vlc_path
        self.series_data = series_data
        self.setWindowTitle(f"Serie : {series_data.get('name', '?')}")
        self.resize(750, 600)

        layout = QVBoxLayout(self)
        title = QLabel(f"<h2>{series_data.get('name', '?')}</h2>")
        layout.addWidget(title)

        info = QLabel(
            f"<b>Genre :</b> {series_data.get('genre', '?')} &nbsp;|&nbsp; "
            f"<b>Annee :</b> {series_data.get('releaseDate', '?')} &nbsp;|&nbsp; "
            f"<b>Note :</b> {series_data.get('rating', '?')}"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        if series_data.get("plot"):
            plot = QTextEdit()
            plot.setReadOnly(True)
            plot.setMaximumHeight(80)
            plot.setPlainText(series_data["plot"])
            layout.addWidget(plot)

        layout.addWidget(QLabel("<b>Saisons & Episodes :</b>"))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Titre", "Duree", "Note"])
        self.tree.setColumnWidth(0, 420)
        self.tree.itemDoubleClicked.connect(self.on_double_click)
        layout.addWidget(self.tree)

        btns = QHBoxLayout()
        self.play_btn = QPushButton("▶️  Lire l'episode selectionne")
        self.play_btn.clicked.connect(self.play_selected)
        self.play_btn.setEnabled(False)
        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.accept)
        btns.addWidget(self.play_btn)
        btns.addStretch()
        btns.addWidget(close_btn)
        layout.addLayout(btns)

        self.tree.itemSelectionChanged.connect(self._on_select)

        self.tree.addTopLevelItem(QTreeWidgetItem(["Chargement..."]))
        self.thread = LoaderThread(self.api.series_info, series_data.get("series_id"))
        self.thread.finished_ok.connect(self._on_loaded)
        self.thread.failed.connect(self._on_error)
        self.thread.start()

    def _on_select(self):
        items = self.tree.selectedItems()
        self.play_btn.setEnabled(bool(items and items[0].data(0, Qt.UserRole)))

    def _on_loaded(self, info):
        self.tree.clear()
        episodes = info.get("episodes", {}) if info else {}
        if not episodes:
            self.tree.addTopLevelItem(QTreeWidgetItem(["Aucun episode trouve"]))
            return
        for season_num in sorted(episodes.keys(),
                                  key=lambda x: int(x) if str(x).isdigit() else 0):
            season_eps = episodes[season_num]
            season_item = QTreeWidgetItem([f"Saison {season_num}  ({len(season_eps)} episodes)"])
            self.tree.addTopLevelItem(season_item)
            for ep in season_eps:
                title = ep.get("title") or f"Episode {ep.get('episode_num', '?')}"
                info_ep = ep.get("info", {}) or {}
                ep_item = QTreeWidgetItem([title, str(info_ep.get("duration", "")),
                                            str(info_ep.get("rating", ""))])
                ep_item.setData(0, Qt.UserRole, ep)
                season_item.addChild(ep_item)
            season_item.setExpanded(True)

    def _on_error(self, msg):
        self.tree.clear()
        self.tree.addTopLevelItem(QTreeWidgetItem([f"Erreur : {msg}"]))

    def _play_episode(self, ep):
        ext = ep.get("container_extension", "mkv")
        url = self.api.stream_url(ep.get("id"), "series", ext)
        try:
            launch_vlc(self.vlc_path, url, user_agent=self.api.user_agent,
                       title=ep.get("title", "Episode"))
        except Exception as e:
            QMessageBox.warning(self, "Erreur VLC", str(e))

    def play_selected(self):
        items = self.tree.selectedItems()
        if items and items[0].data(0, Qt.UserRole):
            self._play_episode(items[0].data(0, Qt.UserRole))

    def on_double_click(self, item, _column):
        ep = item.data(0, Qt.UserRole)
        if ep:
            self._play_episode(ep)


# ---------------------------------------------------------------------------
# Onglet generique
# ---------------------------------------------------------------------------
class BrowseTab(QWidget):
    """Onglet Live/VOD/Series avec favoris, EPG (live), recherche."""

    favorites_changed = pyqtSignal()  # pour rafraichir le compteur global

    def __init__(self, api, kind, favorites, get_vlc_path):
        super().__init__()
        self.api = api
        self.kind = kind
        self.favorites = favorites
        self.get_vlc_path = get_vlc_path
        self.all_items = []
        self.current_data = None
        self.current_category_id = None
        self.epg_thread = None

        root = QVBoxLayout(self)

        search_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher...")
        self.search_input.textChanged.connect(self.filter_items)
        search_bar.addWidget(QLabel("🔍"))
        search_bar.addWidget(self.search_input)
        root.addLayout(search_bar)

        splitter = QSplitter(Qt.Horizontal)
        self.cat_list = QListWidget()
        self.cat_list.itemClicked.connect(self.on_category_clicked)
        splitter.addWidget(self.cat_list)

        self.item_list = QListWidget()
        self.item_list.itemClicked.connect(self.on_item_clicked)
        self.item_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.item_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.item_list.customContextMenuRequested.connect(self._show_context_menu)
        splitter.addWidget(self.item_list)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        right_layout.addWidget(self.details, stretch=2)

        if self.kind == "live":
            epg_label = QLabel("<b>📅 Guide TV (EPG) :</b>")
            right_layout.addWidget(epg_label)
            self.epg_view = QTextEdit()
            self.epg_view.setReadOnly(True)
            self.epg_view.setMaximumHeight(180)
            right_layout.addWidget(self.epg_view, stretch=1)
        else:
            self.epg_view = None

        self.play_btn = QPushButton("▶️  Lire avec VLC")
        self.play_btn.clicked.connect(self.play_current)
        self.play_btn.setEnabled(False)
        self.play_btn.setStyleSheet(
            "QPushButton { padding: 8px; font-weight: bold; background: #ff6b35;"
            " color: white; border-radius: 4px; }"
            "QPushButton:disabled { background: #ccc; }"
            "QPushButton:hover:!disabled { background: #ff8555; }"
        )
        right_layout.addWidget(self.play_btn)

        self.fav_btn = QPushButton(f"{STAR_EMPTY}  Ajouter aux favoris")
        self.fav_btn.clicked.connect(self.toggle_favorite)
        self.fav_btn.setEnabled(False)
        right_layout.addWidget(self.fav_btn)

        self.copy_url_btn = QPushButton("📋  Copier URL")
        self.copy_url_btn.clicked.connect(self.copy_current_url)
        self.copy_url_btn.setEnabled(False)
        right_layout.addWidget(self.copy_url_btn)

        right_panel.setMaximumWidth(420)
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 500, 400])
        root.addWidget(splitter)

        self.count_label = QLabel("")
        root.addWidget(self.count_label)

        self.load_categories()

    # ----- Chargement -----
    def load_categories(self):
        self.cat_list.clear()
        self.cat_list.addItem("Chargement...")
        getter = {
            "live": self.api.live_categories,
            "vod": self.api.vod_categories,
            "series": self.api.series_categories,
        }[self.kind]
        self.cat_thread = LoaderThread(getter)
        self.cat_thread.finished_ok.connect(self._on_categories_loaded)
        self.cat_thread.failed.connect(self._on_error)
        self.cat_thread.start()

    def _on_categories_loaded(self, cats):
        self.cat_list.clear()
        # Categorie speciale Favoris en haut
        fav_count = self.favorites.count(self.kind)
        fav_item = QListWidgetItem(f"⭐ Favoris ({fav_count})")
        fav_item.setData(Qt.UserRole, "__favorites__")
        self.cat_list.addItem(fav_item)

        all_item = QListWidgetItem("📂 Tout")
        all_item.setData(Qt.UserRole, None)
        self.cat_list.addItem(all_item)

        for c in cats or []:
            item = QListWidgetItem(c.get("category_name", "?"))
            item.setData(Qt.UserRole, c.get("category_id"))
            self.cat_list.addItem(item)

    def refresh_favorites_category(self):
        """Met a jour le compteur de la categorie favoris."""
        if self.cat_list.count() == 0:
            return
        first = self.cat_list.item(0)
        if first and first.data(Qt.UserRole) == "__favorites__":
            fav_count = self.favorites.count(self.kind)
            first.setText(f"⭐ Favoris ({fav_count})")

    def _on_error(self, msg):
        self.cat_list.clear()
        self.item_list.clear()
        QMessageBox.warning(self, "Erreur", msg)

    def on_category_clicked(self, item):
        cat_data = item.data(Qt.UserRole)
        self.current_category_id = cat_data

        if cat_data == "__favorites__":
            # Afficher uniquement les favoris
            favs = self.favorites.get_all(self.kind)
            self.all_items = favs
            self.render_items(favs)
            return

        self.item_list.clear()
        self.item_list.addItem("Chargement...")
        getter = {
            "live": self.api.live_streams,
            "vod": self.api.vod_streams,
            "series": self.api.series,
        }[self.kind]
        self.item_thread = LoaderThread(getter, cat_data)
        self.item_thread.finished_ok.connect(self._on_items_loaded)
        self.item_thread.failed.connect(self._on_error)
        self.item_thread.start()

    def _on_items_loaded(self, items):
        self.all_items = items or []
        self.render_items(self.all_items)

    def _format_item_label(self, it):
        name = it.get("name") or it.get("title") or "?"
        if self.favorites.is_favorite(self.kind, it):
            return f"{STAR_FILLED}  {name}"
        return name

    def render_items(self, items):
        self.item_list.clear()
        for it in items:
            qitem = QListWidgetItem(self._format_item_label(it))
            qitem.setData(Qt.UserRole, it)
            self.item_list.addItem(qitem)
        self.count_label.setText(f"{len(items)} elements")

    def filter_items(self, text):
        text = text.lower().strip()
        if not text:
            self.render_items(self.all_items)
            return
        filtered = [
            it for it in self.all_items
            if text in (it.get("name") or it.get("title") or "").lower()
        ]
        self.render_items(filtered)

    # ----- Selection -----
    def _url_for(self, data):
        sid = data.get("stream_id") or data.get("series_id")
        if not sid:
            return None
        if self.kind == "live":
            ext = data.get("container_extension", "ts")
            return self.api.stream_url(sid, "live", ext)
        elif self.kind == "vod":
            ext = data.get("container_extension", "mp4")
            return self.api.stream_url(sid, "movie", ext)
        return None

    def on_item_clicked(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        self.current_data = data
        url = self._url_for(data)
        sid = data.get("stream_id") or data.get("series_id")

        url_display = ("Multi-episodes (bouton Lire ouvre les saisons)"
                       if self.kind == "series" else (url or "(URL indisponible)"))

        info_lines = [
            f"<b>Nom :</b> {data.get('name') or data.get('title')}",
            f"<b>ID :</b> {sid}",
            f"<b>URL :</b><br><code style='font-size:10px;'>{url_display}</code>",
        ]
        if data.get("rating"):
            info_lines.append(f"<b>Note :</b> {data['rating']}")
        if data.get("plot"):
            info_lines.append(f"<br><b>Synopsis :</b><br>{data['plot']}")
        if data.get("genre"):
            info_lines.append(f"<b>Genre :</b> {data['genre']}")
        if data.get("releaseDate") or data.get("release_date"):
            info_lines.append(f"<b>Sortie :</b> {data.get('releaseDate') or data.get('release_date')}")
        self.details.setHtml("<br>".join(info_lines))

        # Boutons
        if self.kind == "series":
            self.play_btn.setText("📼  Voir saisons & episodes")
            self.play_btn.setEnabled(True)
            self.copy_url_btn.setEnabled(False)
        else:
            self.play_btn.setText("▶️  Lire avec VLC")
            self.play_btn.setEnabled(bool(url))
            self.copy_url_btn.setEnabled(bool(url))

        # Favoris button
        if self.favorites.is_favorite(self.kind, data):
            self.fav_btn.setText(f"{STAR_FILLED}  Retirer des favoris")
        else:
            self.fav_btn.setText(f"{STAR_EMPTY}  Ajouter aux favoris")
        self.fav_btn.setEnabled(True)

        # EPG pour live
        if self.kind == "live" and self.epg_view is not None:
            self._load_epg(sid)

    def _load_epg(self, stream_id):
        if not stream_id:
            return
        self.epg_view.setHtml("<i>Chargement du guide TV...</i>")
        if self.epg_thread and self.epg_thread.isRunning():
            self.epg_thread.terminate()
        self.epg_thread = LoaderThread(self.api.short_epg, stream_id, 8)
        self.epg_thread.finished_ok.connect(self._on_epg_loaded)
        self.epg_thread.failed.connect(
            lambda m: self.epg_view.setHtml(f"<i style='color:#a00;'>EPG indisponible : {m}</i>")
        )
        self.epg_thread.start()

    def _on_epg_loaded(self, data):
        listings = data.get("epg_listings", []) if data else []
        if not listings:
            self.epg_view.setHtml("<i>Aucun programme disponible.</i>")
            return
        rows = []
        for prog in listings:
            title = decode_b64(prog.get("title", "")) or "(sans titre)"
            desc = decode_b64(prog.get("description", "") or "")
            start = format_epg_time(prog.get("start"))
            end = format_epg_time(prog.get("end"))
            now_flag = " 🔴 EN COURS" if str(prog.get("now_playing", "")) == "1" else ""
            rows.append(
                f"<div style='margin-bottom:8px;'>"
                f"<b>{start} → {end}{now_flag}</b><br>"
                f"<span style='color:#000;'>{title}</span>"
                f"{f'<br><span style=\"color:#666; font-size:11px;\">{desc}</span>' if desc else ''}"
                f"</div>"
            )
        self.epg_view.setHtml("".join(rows))

    def on_item_double_clicked(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        self.current_data = data
        self.play_current()

    def play_current(self):
        if not self.current_data:
            return
        if self.kind == "series":
            dlg = SeriesDetailsDialog(self.api, self.get_vlc_path(), self.current_data, self)
            dlg.exec_()
            return
        url = self._url_for(self.current_data)
        if not url:
            QMessageBox.warning(self, "Erreur", "URL indisponible")
            return
        title = self.current_data.get("name") or self.current_data.get("title", "Stream")
        try:
            launch_vlc(self.get_vlc_path(), url, user_agent=self.api.user_agent, title=title)
        except Exception as e:
            QMessageBox.warning(self, "Erreur VLC", str(e))

    def copy_current_url(self):
        if not self.current_data:
            return
        url = self._url_for(self.current_data)
        if url:
            QApplication.clipboard().setText(url)

    def toggle_favorite(self):
        if not self.current_data:
            return
        is_now_fav = self.favorites.toggle(self.kind, self.current_data)
        if is_now_fav:
            self.fav_btn.setText(f"{STAR_FILLED}  Retirer des favoris")
        else:
            self.fav_btn.setText(f"{STAR_EMPTY}  Ajouter aux favoris")
        # Rafraichir la liste pour mettre a jour l'etoile
        # Si on est sur "Favoris" et qu'on retire, l'item disparait
        if self.current_category_id == "__favorites__":
            self.all_items = self.favorites.get_all(self.kind)
        self.render_items(self.all_items)
        self.refresh_favorites_category()
        self.favorites_changed.emit()

    def _show_context_menu(self, pos):
        item = self.item_list.itemAt(pos)
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data:
            return
        self.current_data = data
        menu = QMenu(self)

        if self.kind == "series":
            act = QAction("📼  Voir saisons & episodes", self)
        else:
            act = QAction("▶️  Lire avec VLC", self)
        act.triggered.connect(self.play_current)
        menu.addAction(act)

        if self.kind != "series":
            copy_act = QAction("📋  Copier l'URL", self)
            copy_act.triggered.connect(self.copy_current_url)
            menu.addAction(copy_act)

        menu.addSeparator()
        is_fav = self.favorites.is_favorite(self.kind, data)
        fav_act = QAction(
            f"{STAR_FILLED}  Retirer des favoris" if is_fav else f"{STAR_EMPTY}  Ajouter aux favoris",
            self
        )
        fav_act.triggered.connect(self.toggle_favorite)
        menu.addAction(fav_act)

        menu.exec_(self.item_list.mapToGlobal(pos))


# ---------------------------------------------------------------------------
# Fenetre principale
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self, api, vlc_path):
        super().__init__()
        self.api = api
        self.vlc_path = vlc_path
        self.favorites = FavoritesManager()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1320, 820)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.account_label = QLabel("Chargement du compte...")
        self.account_label.setStyleSheet("padding: 6px; background: #f0f0f0; border-radius: 4px;")
        layout.addWidget(self.account_label)

        actions = QHBoxLayout()
        self.export_btn = QPushButton("⬇️  Exporter M3U...")
        self.export_btn.clicked.connect(self.export_m3u)
        self.copy_btn = QPushButton("📋  Copier URL M3U")
        self.copy_btn.clicked.connect(self.copy_m3u_url)
        self.refresh_btn = QPushButton("🔄  Rafraichir compte")
        self.refresh_btn.clicked.connect(self.load_account_info)
        self.vlc_btn = QPushButton("⚙️  Chemin VLC")
        self.vlc_btn.clicked.connect(self.change_vlc_path)
        actions.addWidget(self.export_btn)
        actions.addWidget(self.copy_btn)
        actions.addWidget(self.refresh_btn)
        actions.addWidget(self.vlc_btn)
        actions.addStretch()
        self.vlc_status = QLabel()
        self.fav_status = QLabel()
        actions.addWidget(self.fav_status)
        actions.addWidget(QLabel(" | "))
        actions.addWidget(self.vlc_status)
        layout.addLayout(actions)
        self._update_vlc_status()
        self._update_fav_status()

        self.tabs = QTabWidget()
        self.live_tab = BrowseTab(api, "live", self.favorites, lambda: self.vlc_path)
        self.vod_tab = BrowseTab(api, "vod", self.favorites, lambda: self.vlc_path)
        self.series_tab = BrowseTab(api, "series", self.favorites, lambda: self.vlc_path)
        for tab in (self.live_tab, self.vod_tab, self.series_tab):
            tab.favorites_changed.connect(self._update_fav_status)
        self.tabs.addTab(self.live_tab, "📺 Chaines Live")
        self.tabs.addTab(self.vod_tab, "🎬 Films")
        self.tabs.addTab(self.series_tab, "📼 Series")
        layout.addWidget(self.tabs)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage(f"Bienvenue dans {APP_NAME} !", 5000)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximumWidth(200)
        self.status.addPermanentWidget(self.progress)

        self.load_account_info()

    def _update_vlc_status(self):
        if self.vlc_path and os.path.isfile(self.vlc_path):
            self.vlc_status.setText(f"VLC : ✅ {os.path.basename(self.vlc_path)}")
            self.vlc_status.setStyleSheet("color: green;")
        else:
            self.vlc_status.setText("VLC : ❌ non configure")
            self.vlc_status.setStyleSheet("color: red;")

    def _update_fav_status(self):
        n = (self.favorites.count("live") +
             self.favorites.count("vod") +
             self.favorites.count("series"))
        self.fav_status.setText(f"⭐ {n} favoris")
        self.fav_status.setStyleSheet("color: #d4a017;")

    def change_vlc_path(self):
        ext = "vlc.exe (vlc.exe)" if platform.system() == "Windows" else "Tous (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Selectionner VLC", "", ext)
        if path:
            self.vlc_path = path
            self._update_vlc_status()
            cfg = load_config()
            cfg["vlc_path"] = path
            save_config(cfg)

    def load_account_info(self):
        self.account_label.setText("Chargement du compte...")
        self.info_thread = LoaderThread(self.api.user_info)
        self.info_thread.finished_ok.connect(self._on_info_loaded)
        self.info_thread.failed.connect(lambda m: self.account_label.setText(f"Erreur : {m}"))
        self.info_thread.start()

    def _on_info_loaded(self, info):
        u = info.get("user_info", {})
        s = info.get("server_info", {})
        status = u.get("status", "?")
        exp = u.get("exp_date")
        if exp:
            try:
                exp_str = datetime.fromtimestamp(int(exp)).strftime("%Y-%m-%d %H:%M")
            except Exception:
                exp_str = str(exp)
        else:
            exp_str = "?"
        connections = f"{u.get('active_cons', '?')}/{u.get('max_connections', '?')}"
        msg = (
            f"<b>Statut :</b> {status} &nbsp;|&nbsp; "
            f"<b>Expire :</b> {exp_str} &nbsp;|&nbsp; "
            f"<b>Connexions :</b> {connections} &nbsp;|&nbsp; "
            f"<b>Serveur :</b> {s.get('url', '?')}:{s.get('port', '?')}"
        )
        self.account_label.setText(msg)

    def copy_m3u_url(self):
        QApplication.clipboard().setText(self.api.m3u_url())
        self.status.showMessage("URL M3U copiee dans le presse-papier", 4000)

    def export_m3u(self):
        counts = {
            "live": self.favorites.count("live"),
            "vod": self.favorites.count("vod"),
        }
        dlg = M3UExportDialog(counts, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        mode = dlg.selected_mode()

        if mode == M3UExportDialog.MODE_FULL_SERVER:
            self._download_full_m3u()
        elif mode == M3UExportDialog.MODE_FAVORITES:
            self._export_favorites_m3u()

    def _download_full_m3u(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le M3U complet", "playlist_full.m3u",
            "Fichiers M3U (*.m3u *.m3u8)"
        )
        if not path:
            return
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.export_btn.setEnabled(False)
        self.status.showMessage("Telechargement du M3U en cours...")

        self.dl_thread = M3UDownloadThread(
            self.api.session, self.api.m3u_url(), path, self.api.verify_ssl
        )
        self.dl_thread.progress.connect(self.progress.setValue)
        self.dl_thread.finished_ok.connect(self._on_dl_ok)
        self.dl_thread.failed.connect(self._on_dl_fail)
        self.dl_thread.start()

    def _export_favorites_m3u(self):
        live_favs = self.favorites.get_all("live")
        vod_favs = self.favorites.get_all("vod")
        if not live_favs and not vod_favs:
            QMessageBox.information(self, "Favoris vides",
                                     "Aucun favori a exporter (live ou films).")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le M3U des favoris", "playlist_favoris.m3u",
            "Fichiers M3U (*.m3u *.m3u8)"
        )
        if not path:
            return
        try:
            content = "#EXTM3U\n"
            if live_favs:
                content += build_m3u(live_favs, "live", self.api).replace("#EXTM3U\n", "", 1)
            if vod_favs:
                content += build_m3u(vod_favs, "vod", self.api).replace("#EXTM3U\n", "", 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            n = len(live_favs) + len(vod_favs)
            QMessageBox.information(
                self, "Export reussi",
                f"{n} favoris exportes vers :\n{path}"
            )
            self.status.showMessage(f"Favoris exportes : {path}", 8000)
        except Exception as e:
            QMessageBox.warning(self, "Erreur export", str(e))

    def _on_dl_ok(self, path):
        self.progress.setVisible(False)
        self.export_btn.setEnabled(True)
        self.status.showMessage(f"M3U enregistre : {path}", 8000)
        QMessageBox.information(self, "Telechargement termine",
                                 f"Fichier enregistre :\n{path}")

    def _on_dl_fail(self, msg):
        self.progress.setVisible(False)
        self.export_btn.setEnabled(True)
        self.status.showMessage("Echec du telechargement", 5000)
        QMessageBox.warning(self, "Erreur", msg)


# ---------------------------------------------------------------------------
# Entree
# ---------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")

    while True:
        dlg = LoginDialog()
        if dlg.exec_() != QDialog.Accepted:
            return 0
        creds = dlg.credentials()
        if not creds["host"] or not creds["username"] or not creds["password"]:
            QMessageBox.warning(None, "Erreur", "Tous les champs sont requis")
            continue

        api = XtreamAPI(
            creds["host"], creds["username"], creds["password"],
            user_agent=creds["user_agent"],
            verify_ssl=creds["verify_ssl"],
        )
        try:
            info = api.user_info()
            if not info or "user_info" not in info:
                raise RuntimeError("Reponse invalide")
            if info.get("user_info", {}).get("auth") == 0:
                raise RuntimeError("Identifiants refuses (auth=0)")
        except Exception as e:
            QMessageBox.critical(None, "Connexion echouee", str(e))
            continue

        if creds["remember"]:
            cfg = load_config()
            cfg.update({
                "host": creds["host"],
                "username": creds["username"],
                "password": creds["password"],
                "user_agent_label": creds["user_agent_label"],
                "verify_ssl": creds["verify_ssl"],
                "vlc_path": creds["vlc_path"],
            })
            save_config(cfg)
        else:
            # Si on decoche, on retire les creds mais on garde favoris + vlc_path
            cfg = load_config()
            for k in ("host", "username", "password", "user_agent_label", "verify_ssl"):
                cfg.pop(k, None)
            save_config(cfg)

        win = MainWindow(api, creds["vlc_path"])
        win.show()
        return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
