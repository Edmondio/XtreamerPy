"""
Xtream Codes Client - PyQt5
Connexion API Xtream, navigation Live/Films/Series, lecture VLC, export M3U.

Dependances :
    pip install PyQt5 requests urllib3

Lancement :
    python xtream_client.py
"""

import sys
import json
import os
import shutil
import subprocess
import platform
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QListWidget,
    QListWidgetItem, QSplitter, QMessageBox, QFileDialog, QDialog,
    QFormLayout, QCheckBox, QStatusBar, QProgressBar, QTextEdit, QComboBox,
    QTreeWidget, QTreeWidgetItem, QMenu, QAction
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

CONFIG_FILE = os.path.expanduser("~/.xtream_client.json")

USER_AGENTS = {
    "VLC (recommande)":      "VLC/3.0.20 LibVLC/3.0.20",
    "IPTV Smarters":         "IPTVSmartersPlayer",
    "TiviMate":              "TiviMate/4.7.0 (Linux;Android 11)",
    "Kodi":                  "Kodi/20.2 (Windows NT 10.0; Win64; x64) App_Bitness/64 Version/20.2",
    "Mozilla Firefox":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "python-requests (debug)": None,
}


# ---------------------------------------------------------------------------
# Detection VLC
# ---------------------------------------------------------------------------
def find_vlc():
    """Cherche l'executable VLC. Retourne le chemin ou None."""
    system = platform.system()
    candidates = []
    if system == "Windows":
        candidates = [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ]
    elif system == "Darwin":
        candidates = [
            "/Applications/VLC.app/Contents/MacOS/VLC",
        ]
    else:  # Linux
        candidates = ["/usr/bin/vlc", "/usr/local/bin/vlc", "/snap/bin/vlc"]

    for c in candidates:
        if os.path.isfile(c):
            return c
    # Fallback PATH
    found = shutil.which("vlc")
    if found:
        return found
    return None


def launch_vlc(vlc_path, url, user_agent=None, title=None):
    """Lance VLC en non-bloquant avec l'URL fournie."""
    if not vlc_path or not os.path.isfile(vlc_path):
        raise RuntimeError(
            "VLC introuvable. Installe VLC ou configure son chemin "
            "dans Parametres > Chemin VLC."
        )
    args = [vlc_path]
    if user_agent:
        args.append(f"--http-user-agent={user_agent}")
    if title:
        args.append(f"--meta-title={title}")
    args.append(url)
    # Lancement detache pour ne pas bloquer / capturer stdout
    kwargs = {}
    if platform.system() == "Windows":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008  # DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)


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
            raise RuntimeError(
                "Erreur SSL. Decoche 'Verifier SSL' dans la fenetre de connexion.\n\n"
                f"Detail : {e}"
            )
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
# Login
# ---------------------------------------------------------------------------
class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Connexion Xtream Codes")
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

        # Chemin VLC
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

        # Auto-detect VLC
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

        # Charger config
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    cfg = json.load(f)
                self.host_input.setText(cfg.get("host", ""))
                self.user_input.setText(cfg.get("username", ""))
                self.pass_input.setText(cfg.get("password", ""))
                ua_label = cfg.get("user_agent_label")
                if ua_label and ua_label in USER_AGENTS:
                    self.ua_combo.setCurrentText(ua_label)
                self.verify_ssl.setChecked(cfg.get("verify_ssl", True))
                if cfg.get("vlc_path"):
                    self.vlc_input.setText(cfg["vlc_path"])
                self.remember.setChecked(True)
            except Exception:
                pass

    def _browse_vlc(self):
        if platform.system() == "Windows":
            ext = "vlc.exe (vlc.exe)"
        else:
            ext = "Tous les fichiers (*)"
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
# Fenetre series (saisons + episodes)
# ---------------------------------------------------------------------------
class SeriesDetailsDialog(QDialog):
    def __init__(self, api, vlc_path, series_data, parent=None):
        super().__init__(parent)
        self.api = api
        self.vlc_path = vlc_path
        self.series_data = series_data
        self.setWindowTitle(f"Serie : {series_data.get('name', '?')}")
        self.resize(700, 600)

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
        self.tree.setColumnWidth(0, 400)
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

        # Chargement async
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
        # episodes est un dict { "1": [...], "2": [...] } par saison
        for season_num in sorted(episodes.keys(), key=lambda x: int(x) if str(x).isdigit() else 0):
            season_eps = episodes[season_num]
            season_item = QTreeWidgetItem([f"Saison {season_num}  ({len(season_eps)} episodes)"])
            self.tree.addTopLevelItem(season_item)
            for ep in season_eps:
                title = ep.get("title") or f"Episode {ep.get('episode_num', '?')}"
                info_ep = ep.get("info", {}) or {}
                duration = info_ep.get("duration", "")
                rating = info_ep.get("rating", "")
                ep_item = QTreeWidgetItem([title, str(duration), str(rating)])
                ep_item.setData(0, Qt.UserRole, ep)
                season_item.addChild(ep_item)
            season_item.setExpanded(True)

    def _on_error(self, msg):
        self.tree.clear()
        self.tree.addTopLevelItem(QTreeWidgetItem([f"Erreur : {msg}"]))

    def _play_episode(self, ep):
        ext = ep.get("container_extension", "mkv")
        ep_id = ep.get("id")
        url = self.api.stream_url(ep_id, "series", ext)
        title = ep.get("title", "Episode")
        try:
            launch_vlc(self.vlc_path, url, user_agent=self.api.user_agent, title=title)
        except Exception as e:
            QMessageBox.warning(self, "Erreur VLC", str(e))

    def play_selected(self):
        items = self.tree.selectedItems()
        if not items:
            return
        ep = items[0].data(0, Qt.UserRole)
        if ep:
            self._play_episode(ep)

    def on_double_click(self, item, _column):
        ep = item.data(0, Qt.UserRole)
        if ep:
            self._play_episode(ep)


# ---------------------------------------------------------------------------
# Onglet generique
# ---------------------------------------------------------------------------
class BrowseTab(QWidget):
    def __init__(self, api, kind, get_vlc_path):
        super().__init__()
        self.api = api
        self.kind = kind
        self.get_vlc_path = get_vlc_path  # callback pour avoir le chemin VLC a jour
        self.all_items = []
        self.current_data = None

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

        # Panneau droit : details + boutons
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        right_layout.addWidget(self.details)

        self.play_btn = QPushButton("▶️  Lire avec VLC")
        self.play_btn.clicked.connect(self.play_current)
        self.play_btn.setEnabled(False)
        self.play_btn.setStyleSheet(
            "QPushButton { padding: 8px; font-weight: bold; background: #ff6b35; color: white; border-radius: 4px; }"
            "QPushButton:disabled { background: #ccc; }"
            "QPushButton:hover:!disabled { background: #ff8555; }"
        )
        right_layout.addWidget(self.play_btn)

        self.copy_url_btn = QPushButton("📋  Copier URL")
        self.copy_url_btn.clicked.connect(self.copy_current_url)
        self.copy_url_btn.setEnabled(False)
        right_layout.addWidget(self.copy_url_btn)

        right_panel.setMaximumWidth(380)
        splitter.addWidget(right_panel)

        splitter.setSizes([250, 500, 350])
        root.addWidget(splitter)

        self.count_label = QLabel("")
        root.addWidget(self.count_label)

        self.load_categories()

    def load_categories(self):
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
        all_item = QListWidgetItem("📂 Tout")
        all_item.setData(Qt.UserRole, None)
        self.cat_list.addItem(all_item)
        for c in cats or []:
            item = QListWidgetItem(c.get("category_name", "?"))
            item.setData(Qt.UserRole, c.get("category_id"))
            self.cat_list.addItem(item)

    def _on_error(self, msg):
        self.cat_list.clear()
        self.item_list.clear()
        QMessageBox.warning(self, "Erreur", msg)

    def on_category_clicked(self, item):
        cat_id = item.data(Qt.UserRole)
        self.item_list.clear()
        self.item_list.addItem("Chargement...")
        getter = {
            "live": self.api.live_streams,
            "vod": self.api.vod_streams,
            "series": self.api.series,
        }[self.kind]
        self.item_thread = LoaderThread(getter, cat_id)
        self.item_thread.finished_ok.connect(self._on_items_loaded)
        self.item_thread.failed.connect(self._on_error)
        self.item_thread.start()

    def _on_items_loaded(self, items):
        self.all_items = items or []
        self.render_items(self.all_items)

    def render_items(self, items):
        self.item_list.clear()
        for it in items:
            name = it.get("name") or it.get("title") or "?"
            qitem = QListWidgetItem(name)
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

    def _url_for(self, data):
        """Retourne (url, label_action) pour l'item. Pour series, pas d'URL directe."""
        sid = data.get("stream_id") or data.get("series_id")
        if not sid:
            return None
        if self.kind == "live":
            ext = data.get("container_extension", "ts")
            return self.api.stream_url(sid, "live", ext)
        elif self.kind == "vod":
            ext = data.get("container_extension", "mp4")
            return self.api.stream_url(sid, "movie", ext)
        return None  # series : pas d'URL directe

    def on_item_clicked(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        self.current_data = data
        url = self._url_for(data)
        sid = data.get("stream_id") or data.get("series_id")

        if self.kind == "series":
            url_display = "Multi-episodes (bouton Lire ouvre les saisons)"
        else:
            url_display = url or "(URL indisponible)"

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

        # Activer les boutons
        if self.kind == "series":
            self.play_btn.setText("📼  Voir saisons & episodes")
            self.play_btn.setEnabled(True)
            self.copy_url_btn.setEnabled(False)
        else:
            self.play_btn.setText("▶️  Lire avec VLC")
            self.play_btn.setEnabled(bool(url))
            self.copy_url_btn.setEnabled(bool(url))

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
            QMessageBox.warning(self, "Erreur", "URL indisponible pour cet element")
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
        menu.exec_(self.item_list.mapToGlobal(pos))


# ---------------------------------------------------------------------------
# Fenetre principale
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self, api, vlc_path):
        super().__init__()
        self.api = api
        self.vlc_path = vlc_path
        self.setWindowTitle("Xtream Codes Client")
        self.resize(1300, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.account_label = QLabel("Chargement du compte...")
        self.account_label.setStyleSheet("padding: 6px; background: #f0f0f0; border-radius: 4px;")
        layout.addWidget(self.account_label)

        actions = QHBoxLayout()
        self.dl_btn = QPushButton("⬇️  Telecharger le M3U")
        self.dl_btn.clicked.connect(self.download_m3u)
        self.copy_btn = QPushButton("📋  Copier URL M3U")
        self.copy_btn.clicked.connect(self.copy_m3u_url)
        self.refresh_btn = QPushButton("🔄  Rafraichir compte")
        self.refresh_btn.clicked.connect(self.load_account_info)
        self.vlc_btn = QPushButton("⚙️  Chemin VLC")
        self.vlc_btn.clicked.connect(self.change_vlc_path)
        actions.addWidget(self.dl_btn)
        actions.addWidget(self.copy_btn)
        actions.addWidget(self.refresh_btn)
        actions.addWidget(self.vlc_btn)
        actions.addStretch()
        self.vlc_status = QLabel()
        actions.addWidget(self.vlc_status)
        layout.addLayout(actions)
        self._update_vlc_status()

        self.tabs = QTabWidget()
        self.tabs.addTab(BrowseTab(api, "live", lambda: self.vlc_path), "📺 Chaines Live")
        self.tabs.addTab(BrowseTab(api, "vod", lambda: self.vlc_path), "🎬 Films")
        self.tabs.addTab(BrowseTab(api, "series", lambda: self.vlc_path), "📼 Series")
        layout.addWidget(self.tabs)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
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

    def change_vlc_path(self):
        if platform.system() == "Windows":
            ext = "vlc.exe (vlc.exe)"
        else:
            ext = "Tous les fichiers (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Selectionner VLC", "", ext)
        if path:
            self.vlc_path = path
            self._update_vlc_status()
            # Sauvegarder dans config
            try:
                cfg = {}
                if os.path.exists(CONFIG_FILE):
                    with open(CONFIG_FILE) as f:
                        cfg = json.load(f)
                cfg["vlc_path"] = path
                with open(CONFIG_FILE, "w") as f:
                    json.dump(cfg, f)
            except Exception:
                pass

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
            from datetime import datetime
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
            f"<b>Serveur :</b> {s.get('url', '?')}:{s.get('port', '?')} &nbsp;|&nbsp; "
            f"<b>TZ :</b> {s.get('timezone', '?')}"
        )
        self.account_label.setText(msg)

    def copy_m3u_url(self):
        QApplication.clipboard().setText(self.api.m3u_url())
        self.status.showMessage("URL M3U copiee dans le presse-papier", 4000)

    def download_m3u(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le M3U", "playlist.m3u", "Fichiers M3U (*.m3u *.m3u8)"
        )
        if not path:
            return
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.dl_btn.setEnabled(False)
        self.status.showMessage("Telechargement du M3U en cours...")

        self.dl_thread = M3UDownloadThread(
            self.api.session, self.api.m3u_url(), path, self.api.verify_ssl
        )
        self.dl_thread.progress.connect(self.progress.setValue)
        self.dl_thread.finished_ok.connect(self._on_dl_ok)
        self.dl_thread.failed.connect(self._on_dl_fail)
        self.dl_thread.start()

    def _on_dl_ok(self, path):
        self.progress.setVisible(False)
        self.dl_btn.setEnabled(True)
        self.status.showMessage(f"M3U enregistre : {path}", 8000)
        QMessageBox.information(self, "Telechargement termine", f"Fichier enregistre :\n{path}")

    def _on_dl_fail(self, msg):
        self.progress.setVisible(False)
        self.dl_btn.setEnabled(True)
        self.status.showMessage("Echec du telechargement", 5000)
        QMessageBox.warning(self, "Erreur", msg)


# ---------------------------------------------------------------------------
# Entree
# ---------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
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
                raise RuntimeError("Identifiants refuses par le serveur (auth=0)")
        except Exception as e:
            QMessageBox.critical(None, "Connexion echouee", str(e))
            continue

        if creds["remember"]:
            try:
                with open(CONFIG_FILE, "w") as f:
                    json.dump({
                        "host": creds["host"],
                        "username": creds["username"],
                        "password": creds["password"],
                        "user_agent_label": creds["user_agent_label"],
                        "verify_ssl": creds["verify_ssl"],
                        "vlc_path": creds["vlc_path"],
                    }, f)
            except Exception:
                pass

        win = MainWindow(api, creds["vlc_path"])
        win.show()
        return app.exec_()


if __name__ == "__main__":
    sys.exit(main())