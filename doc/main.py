import sys
import os
import re
import json
import shutil
import warnings
import urllib.request
import sqlite3
import subprocess
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QComboBox,
                             QFileDialog, QProgressBar, QMessageBox, QFrame,
                             QGraphicsDropShadowEffect, QStackedWidget, QTextEdit,
                             QCheckBox, QScrollArea, QTableWidget, QTableWidgetItem,
                             QHeaderView, QSizePolicy, QSpinBox, QSystemTrayIcon,
                             QMenu, QAction, QAbstractItemView)
from PyQt5.QtCore import (QThread, pyqtSignal, Qt, QPoint, QPropertyAnimation,
                          QEasingCurve, QTimer, QRect, QObject, pyqtProperty)
from PyQt5.QtGui import QFont, QColor, QPixmap, QIcon, QPainter, QLinearGradient, QBrush, QPalette
import yt_dlp

warnings.filterwarnings("ignore", category=DeprecationWarning)

# ─────────────────────────────────────────────
#  PyInstaller / MEIPASS YARDIMCI FONKSİYONLARI
# ─────────────────────────────────────────────
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

def get_ffmpeg_path():
    """
    ffmpeg yolunu bulur ve doğrular.
    Arama sırası:
    1. _MEIPASS içinde (PyInstaller paketi)
    2. exe/script yanındaki 'ffmpeg' alt klasörü
    3. exe/script yanındaki 'ffmpeg/bin' alt klasörü (resmi zip yapısı)
    4. exe/script'in doğrudan yanında
    5. Sistem PATH'inde (shutil.which ile doğrulayarak)
    Bulunamazsa None döner — caller hata mesajı gösterir.
    """
    ffmpeg_exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"

    # 1. _MEIPASS (PyInstaller paketi içinde)
    if hasattr(sys, '_MEIPASS'):
        candidate = os.path.join(sys._MEIPASS, ffmpeg_exe)
        if os.path.isfile(candidate):
            return candidate

    # Temel dizin: frozen ise exe'nin yanı, değilse script'in yanı
    base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) \
           else os.path.dirname(os.path.abspath(__file__))

    # 2. /ffmpeg/ alt klasörü
    candidate = os.path.join(base, "ffmpeg", ffmpeg_exe)
    if os.path.isfile(candidate):
        return candidate

    # 3. /ffmpeg/bin/ alt klasörü (resmi zip yapısı: ffmpeg-xxx/bin/ffmpeg.exe)
    candidate = os.path.join(base, "ffmpeg", "bin", ffmpeg_exe)
    if os.path.isfile(candidate):
        return candidate

    # 4. Doğrudan exe/script'in yanında
    candidate = os.path.join(base, ffmpeg_exe)
    if os.path.isfile(candidate):
        return candidate

    # 5. Sistem PATH'inde gerçekten var mı?
    which_result = shutil.which("ffmpeg")
    if which_result:
        return which_result

    # Bulunamadı
    return None

# Uygulama genelinde kullanılacak sabit yollar
BASE_DIR    = get_base_dir()
CONFIG_FILE = os.path.join(BASE_DIR, "settings.json")
DB_FILE     = os.path.join(BASE_DIR, "history.db")
FFMPEG_PATH = get_ffmpeg_path()

# ─────────────────────────────────────────────
#  DİL SÖZLÜĞÜ
# ─────────────────────────────────────────────
LANG = {
    "TR": {
        "menu_single": "⊞  İndirici",
        "menu_batch": "≡  Toplu İndirici",
        "menu_history": "◷  Geçmiş",
        "menu_settings": "⚙  Ayarlar",
        "title_single": "İndirici",
        "title_batch": "Toplu İndirme",
        "title_history": "İndirme Geçmişi",
        "title_settings": "Ayarlar",
        "lbl_url": "Video URL",
        "ph_url": "YouTube linki yapıştırın veya sürükleyin...",
        "lbl_format_qual": "Format ve Kalite",
        "mp4_opt": "MP4 (Video)",
        "mp3_opt": "MP3 (Ses)",
        "status_ready": "Hazır.",
        "btn_start": "İndirmeyi Başlat",
        "btn_start_batch": "Toplu İndirmeyi Başlat",
        "lbl_batch_desc": "JSON dosyası yükleyin veya Playlist URL girin.",
        "ph_json": "JSON Dosyası Seçin...",
        "btn_browse": "Gözat",
        "lbl_log": "İşlem Kaydı",
        "lbl_def_lang": "Varsayılan Dil",
        "lbl_def_type": "Varsayılan İndirme Türü",
        "lbl_def_mp4": "Varsayılan MP4 Çözünürlüğü",
        "lbl_def_mp3": "Varsayılan MP3 Kalitesi",
        "lbl_def_path": "Varsayılan Kayıt Klasörü",
        "lbl_concurrent": "Eşzamanlı İndirme Sayısı",
        "btn_change": "Değiştir",
        "btn_save": "Kaydet",
        "msg_success": "Başarılı",
        "msg_error": "Hata",
        "msg_warning": "Uyarı",
        "msg_enter_link": "Geçerli bir link giriniz.",
        "msg_downloading": "İndiriliyor",
        "msg_eta": "Kalan",
        "msg_done": "Tamamlandı.",
        "msg_batch_done": "Toplu indirme tamamlandı.",
        "msg_single_done": "İndirme tamamlandı.",
        "msg_settings_saved": "Ayarlar kaydedildi.",
        "msg_json_err": "JSON okunamadı:",
        "msg_invalid_json": "Geçerli JSON yükleyin.",
        "log_queued": "video kuyruğa eklendi.",
        "log_downloading": "İndiriliyor",
        "log_completed": "Tamamlandı",
        "btn_lang": "🌐 EN",
        "status_connecting": "Bağlanıyor...",
        "msg_fetching": "Video bilgileri getiriliyor...",
        "msg_size": "Tahmini Boyut:",
        "msg_unknown": "Hesaplanamadı",
        "lbl_trim": "Kırpma (Opsiyonel)",
        "lbl_trim_start": "Başlangıç",
        "lbl_trim_end": "Bitiş",
        "ph_trim": "örn: 01:20",
        "lbl_id3": "MP3'e Kapak ve Etiket Göm",
        "lbl_subtitle": "Altyazı İndir (.srt)",
        "lbl_playlist_url": "Playlist URL",
        "ph_playlist": "YouTube Playlist linki...",
        "btn_load_playlist": "Listeyi Getir",
        "btn_select_all": "Tümünü Seç",
        "btn_deselect": "Temizle",
        "lbl_concurrent_opt": "Eşzamanlı İndir",
        "col_title": "Başlık",
        "col_duration": "Süre",
        "col_select": "Seç",
        "hist_col_title": "Video Adı",
        "hist_col_size": "Boyut",
        "hist_col_date": "Tarih",
        "hist_col_actions": "İşlemler",
        "btn_open_folder": "📂",
        "btn_delete_hist": "🗑",
        "btn_clear_history": "Geçmişi Temizle",
        "update_check": "Güncelleme Kontrol Ediliyor...",
        "update_available": "yt-dlp güncellemesi mevcut! Güncellemek ister misiniz?",
        "update_done": "yt-dlp güncellendi.",
        "update_latest": "yt-dlp güncel.",
        "notify_done_title": "İndirme Tamamlandı",
        "notify_done_msg": "Video başarıyla indirildi.",
        "drop_hint": "↓ Linki buraya sürükleyin",
        "msg_ffmpeg_missing": (
            "ffmpeg bulunamadı!\n\n"
            "Lütfen ffmpeg.exe dosyasını indirip uygulamanın yanına koyun.\n"
            "İndirme: https://www.gyan.dev/ffmpeg/builds/\n\n"
            "'ffmpeg-release-essentials.zip' dosyasını indirip içindeki\n"
            "ffmpeg.exe dosyasını bu uygulamanın yanına kopyalayın."
        ),
    },
    "EN": {
        "menu_single": "⊞  Downloader",
        "menu_batch": "≡  Batch",
        "menu_history": "◷  History",
        "menu_settings": "⚙  Settings",
        "title_single": "Downloader",
        "title_batch": "Batch Download",
        "title_history": "Download History",
        "title_settings": "Settings",
        "lbl_url": "Video URL",
        "ph_url": "Paste or drag a YouTube link here...",
        "lbl_format_qual": "Format & Quality",
        "mp4_opt": "MP4 (Video)",
        "mp3_opt": "MP3 (Audio)",
        "status_ready": "Ready.",
        "btn_start": "Start Download",
        "btn_start_batch": "Start Batch Download",
        "lbl_batch_desc": "Upload a JSON file or paste a Playlist URL.",
        "ph_json": "Select JSON File...",
        "btn_browse": "Browse",
        "lbl_log": "Process Log",
        "lbl_def_lang": "Default Language",
        "lbl_def_type": "Default Download Type",
        "lbl_def_mp4": "Default MP4 Resolution",
        "lbl_def_mp3": "Default MP3 Quality",
        "lbl_def_path": "Default Save Folder",
        "lbl_concurrent": "Concurrent Downloads",
        "btn_change": "Change",
        "btn_save": "Save",
        "msg_success": "Success",
        "msg_error": "Error",
        "msg_warning": "Warning",
        "msg_enter_link": "Please enter a valid link.",
        "msg_downloading": "Downloading",
        "msg_eta": "ETA",
        "msg_done": "Completed.",
        "msg_batch_done": "Batch download completed.",
        "msg_single_done": "Download completed.",
        "msg_settings_saved": "Settings saved.",
        "msg_json_err": "Failed to read JSON:",
        "msg_invalid_json": "Please upload a valid JSON file.",
        "log_queued": "videos added to queue.",
        "log_downloading": "Downloading",
        "log_completed": "Completed",
        "btn_lang": "🌐 TR",
        "status_connecting": "Connecting...",
        "msg_fetching": "Fetching video details...",
        "msg_size": "Estimated Size:",
        "msg_unknown": "Unknown",
        "lbl_trim": "Trim (Optional)",
        "lbl_trim_start": "Start",
        "lbl_trim_end": "End",
        "ph_trim": "e.g. 01:20",
        "lbl_id3": "Embed Cover & Tags into MP3",
        "lbl_subtitle": "Download Subtitles (.srt)",
        "lbl_playlist_url": "Playlist URL",
        "ph_playlist": "YouTube Playlist link...",
        "btn_load_playlist": "Load Playlist",
        "btn_select_all": "Select All",
        "btn_deselect": "Deselect",
        "lbl_concurrent_opt": "Concurrent Downloads",
        "col_title": "Title",
        "col_duration": "Duration",
        "col_select": "Select",
        "hist_col_title": "Video Title",
        "hist_col_size": "Size",
        "hist_col_date": "Date",
        "hist_col_actions": "Actions",
        "btn_open_folder": "📂",
        "btn_delete_hist": "🗑",
        "btn_clear_history": "Clear History",
        "update_check": "Checking for updates...",
        "update_available": "yt-dlp update available! Update now?",
        "update_done": "yt-dlp updated.",
        "update_latest": "yt-dlp is up to date.",
        "notify_done_title": "Download Complete",
        "notify_done_msg": "Video downloaded successfully.",
        "drop_hint": "↓ Drop link here",
        "msg_ffmpeg_missing": (
            "ffmpeg not found!\n\n"
            "Please download ffmpeg.exe and place it next to this application.\n"
            "Download: https://www.gyan.dev/ffmpeg/builds/\n\n"
            "Download 'ffmpeg-release-essentials.zip', extract it and copy\n"
            "ffmpeg.exe next to this application."
        ),
    }
}

# ─────────────────────────────────────────────
#  AYARLAR
# ─────────────────────────────────────────────
DEFAULT_CONFIG = {
    "language": "TR",
    "default_format": "MP4",
    "default_mp4_quality": "720p",
    "default_mp3_quality": "192k",
    "save_path": os.path.expanduser('~/Downloads'),
    "concurrent_downloads": 2,
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        cfg = DEFAULT_CONFIG.copy()
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg.update(json.load(f))
        except Exception:
            pass
        return cfg
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Ayarlar kaydedilemedi: {e}")

# ─────────────────────────────────────────────
#  GEÇMİŞ VERİTABANI
# ─────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, url TEXT, size_mb REAL,
        format TEXT, quality TEXT, save_path TEXT,
        downloaded_at TEXT
    )""")
    conn.commit(); conn.close()

def add_history(title, url, size_mb, fmt, quality, save_path):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT INTO history (title,url,size_mb,format,quality,save_path,downloaded_at) VALUES (?,?,?,?,?,?,?)",
                 (title, url, round(size_mb,2), fmt, quality, save_path, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit(); conn.close()

def load_history():
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("SELECT id,title,size_mb,downloaded_at,save_path FROM history ORDER BY id DESC").fetchall()
    conn.close(); return rows

def delete_history(row_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM history WHERE id=?", (row_id,))
    conn.commit(); conn.close()

def clear_history():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM history")
    conn.commit(); conn.close()

# ─────────────────────────────────────────────
#  YARDIMCI: FADE ANİMASYONU
# ─────────────────────────────────────────────
class FadeStackedWidget(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 1.0
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)

    def setCurrentIndexAnimated(self, index):
        if index == self.currentIndex():
            return
        self.setCurrentIndex(index)
        self._fade_in()

    def _fade_in(self):
        self.setStyleSheet("QStackedWidget { opacity: 0; }")
        QTimer.singleShot(50, lambda: self.setStyleSheet(""))

# ─────────────────────────────────────────────
#  WORKER: BİLGİ GETİRME
# ─────────────────────────────────────────────
class InfoWorker(QThread):
    finished = pyqtSignal(dict, bytes)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__(); self.url = url

    def run(self):
        try:
            ydl_opts = {'quiet': True, 'noplaylist': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
            thumb_url = info.get('thumbnail'); thumb_data = b""
            if thumb_url:
                req = urllib.request.Request(thumb_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as r:
                    thumb_data = r.read()
            self.finished.emit(info, thumb_data)
        except Exception as e:
            self.error.emit(str(e))

# ─────────────────────────────────────────────
#  WORKER: PLAYLIST GETİRME
# ─────────────────────────────────────────────
class PlaylistWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__(); self.url = url

    def run(self):
        try:
            ydl_opts = {'quiet': True, 'extract_flat': True, 'noplaylist': False}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
            entries = info.get('entries', [])
            items = []
            for e in entries:
                if e:
                    dur = e.get('duration', 0) or 0
                    m, s = divmod(int(dur), 60)
                    items.append({
                        'title': e.get('title', 'Unknown'),
                        'url': e.get('url') or f"https://www.youtube.com/watch?v={e.get('id','')}",
                        'duration': f"{m:02d}:{s:02d}"
                    })
            self.finished.emit(items)
        except Exception as e:
            self.error.emit(str(e))

# ─────────────────────────────────────────────
#  WORKER: İNDİRME
# ─────────────────────────────────────────────
class DownloadWorker(QThread):
    progress = pyqtSignal(int, str, str)
    log = pyqtSignal(str)
    finished = pyqtSignal(str, str, float)
    error = pyqtSignal(str)

    def __init__(self, tasks, config, lang_dict, embed_id3=False, embed_subs=False,
                 trim_start="", trim_end="", concurrent=1):
        super().__init__()
        self.tasks = tasks
        self.config = config
        self.t = lang_dict
        self.embed_id3 = embed_id3
        self.embed_subs = embed_subs
        self.trim_start = trim_start.strip()
        self.trim_end = trim_end.strip()
        self.concurrent = max(1, concurrent)
        self._last_title = ""
        self._last_url = ""
        self._downloaded_mb = 0.0

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            ps = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_percent_str', '0%')).strip()
            sp = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_speed_str', '---')).strip()
            et = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_eta_str', '---')).strip()
            tb = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            if tb: self._downloaded_mb = tb / (1024*1024)
            try:
                self.progress.emit(int(float(ps.replace('%',''))), sp, et)
            except: pass

    def _build_opts(self, task):
        # ── ffmpeg kontrolü ──────────────────────────────
        if not FFMPEG_PATH:
            raise FileNotFoundError(self.t.get(
                "msg_ffmpeg_missing",
                "ffmpeg not found! Please place ffmpeg.exe next to the application.\n"
                "Download: https://www.gyan.dev/ffmpeg/builds/"
            ))

        fmt = task.get("format", self.config["default_format"])
        fmt_type = 'MP3' if 'MP3' in fmt.upper() else 'MP4'
        if fmt_type == 'MP3':
            qual = task.get("quality", self.config["default_mp3_quality"])
        else:
            qual = task.get("quality", self.config["default_mp4_quality"])

        opts = {
            'outtmpl': os.path.join(self.config["save_path"], '%(title)s.%(ext)s'),
            'progress_hooks': [self.progress_hook],
            'quiet': True,
            'noplaylist': True,
            'ffmpeg_location': FFMPEG_PATH,
        }

        # Trim
        if self.trim_start or self.trim_end:
            ss = self.trim_start or "0"
            to = self.trim_end or "9999:00"
            opts['postprocessors'] = opts.get('postprocessors', [])
            opts['postprocessors'].append({
                'key': 'FFmpegVideoRemuxer',
                'preferedformat': fmt_type.lower()
            })
            opts['external_downloader'] = 'ffmpeg'
            opts['external_downloader_args'] = {'ffmpeg_i': ['-ss', ss, '-to', to]}

        if fmt_type == 'MP3':
            opts['format'] = 'bestaudio/best'
            if self.embed_id3:
                opts['writethumbnail'] = True
                opts['convert_thumbnails'] = 'jpg'
                opts['postprocessors'] = [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': qual.replace('k', ''),
                    },
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    },
                    {
                        'key': 'EmbedThumbnail',
                        'already_have_thumbnail': False,
                    },
                ]
            else:
                opts['postprocessors'] = [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': qual.replace('k', ''),
                    },
                ]
        else:
            h = qual.replace('p', '')
            opts['format'] = f'bestvideo[ext=mp4][height<={h}]+bestaudio[ext=m4a]/best[ext=mp4][height<={h}]/best'
            opts['merge_output_format'] = 'mp4'
            if self.embed_subs:
                opts['writesubtitles'] = True
                opts['subtitlesformat'] = 'srt'
                opts['subtitleslangs'] = ['tr', 'en']

        return opts, fmt_type, qual

    def _download_one(self, index, total, task):
        url = task.get("url")
        if not url: return
        self._last_url = url
        opts, fmt_type, qual = self._build_opts(task)
        self._last_title = task.get("title", url)
        self.log.emit(f"[{index}/{total}] {self.t['log_downloading']}: {self._last_title} ({fmt_type} {qual})")
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info: self._last_title = info.get('title', self._last_title)
        self.log.emit(f"[{index}/{total}] {self.t['log_completed']}: {self._last_title}\n")

    def run(self):
        try:
            total = len(self.tasks)
            if self.concurrent > 1 and total > 1:
                lock = threading.Lock()
                counter = [0]
                def job(task):
                    with lock:
                        counter[0] += 1
                        idx = counter[0]
                    self._download_one(idx, total, task)
                with ThreadPoolExecutor(max_workers=self.concurrent) as ex:
                    futures = [ex.submit(job, t) for t in self.tasks]
                    for f in as_completed(futures):
                        f.result()
            else:
                for i, task in enumerate(self.tasks, 1):
                    self._download_one(i, total, task)
            self.finished.emit(self._last_title, self._last_url, self._downloaded_mb)
        except Exception as e:
            self.error.emit(str(e))

# ─────────────────────────────────────────────
#  WORKER: yt-dlp GÜNCELLEME
# ─────────────────────────────────────────────
class UpdateWorker(QThread):
    result = pyqtSignal(str)

    def __init__(self, do_update=False):
        super().__init__(); self.do_update = do_update

    def run(self):
        try:
            import yt_dlp.version as ytv
            current = ytv.__version__
            req = urllib.request.Request(
                "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest",
                headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())
            latest = data.get('tag_name', current)
            if latest <= current:
                self.result.emit("latest")
            elif self.do_update:
                if getattr(sys, 'frozen', False):
                    subprocess.run(
                        [sys.executable, "-m", "yt_dlp", "--update"],
                        check=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    )
                else:
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp", "--quiet"],
                        check=True
                    )
                self.result.emit("done")
            else:
                self.result.emit("available")
        except Exception as e:
            self.result.emit(f"error:{e}")

# ─────────────────────────────────────────────
#  ANA UYGULAMA
# ─────────────────────────────────────────────
GRADIENT_BTN_QSS = """
QPushButton.primaryBtn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #7B2FBE, stop:1 #C850C0);
    color: white; border: none; border-radius: 8px;
    padding: 14px; font-weight: bold; font-size: 15px;
}
QPushButton.primaryBtn:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #9D4EDD, stop:1 #E040E0);
}
QPushButton.primaryBtn:disabled {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #3A2450, stop:1 #4A2450);
    color: #8A8A9E;
}
QPushButton.accentBtn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #0F3460, stop:1 #533483);
    color: #E0E0FF; border: none; border-radius: 6px;
    padding: 10px 16px; font-weight: 600; font-size: 13px;
}
QPushButton.accentBtn:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #1a4a8a, stop:1 #7B2FBE);
}
"""

class MainApp(QWidget):
    def __init__(self):
        super().__init__()
        self.dragPos = QPoint()
        self.current_vid_info = None
        self.config = load_config()
        self.lang = self.config.get("language", "TR")
        self.batch_tasks = []
        self.playlist_items = []
        init_db()
        self.initUI()
        self.update_texts()
        self.setup_tray()
        # ffmpeg uyarısını başlangıçta göster
        if not FFMPEG_PATH:
            QTimer.singleShot(500, self.warn_ffmpeg_missing)
        QTimer.singleShot(2000, self.auto_check_update)

    def warn_ffmpeg_missing(self):
        t = LANG[self.lang]
        QMessageBox.warning(self, t["msg_error"], t["msg_ffmpeg_missing"])

    # ── TRAY ──────────────────────────────────
    def setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        size = 64
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, size, size)
        grad.setColorAt(0.0, QColor("#7B2FBE"))
        grad.setColorAt(1.0, QColor("#C850C0"))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, size - 4, size - 4)
        painter.setPen(QColor("#FFFFFF"))
        f = QFont("Segoe UI", 22, QFont.Bold)
        painter.setFont(f)
        painter.drawText(pix.rect(), Qt.AlignCenter, "▶")
        painter.end()
        self.tray.setIcon(QIcon(pix))
        menu = QMenu()
        show_act = QAction("Göster / Show", self)
        show_act.triggered.connect(self.showNormal)
        quit_act = QAction("Çıkış / Quit", self)
        quit_act.triggered.connect(QApplication.quit)
        menu.addAction(show_act)
        menu.addAction(quit_act)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage("YT Downloader", "Sistem tepsisinde çalışıyor.", QSystemTrayIcon.Information, 2000)

    # ── AUTO UPDATE ───────────────────────────
    def auto_check_update(self):
        self.upd_worker = UpdateWorker(do_update=False)
        self.upd_worker.result.connect(self.on_update_check)
        self.upd_worker.start()

    def on_update_check(self, result):
        t = LANG[self.lang]
        if result == "available":
            reply = QMessageBox.question(self, "yt-dlp", t["update_available"],
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.upd_worker2 = UpdateWorker(do_update=True)
                self.upd_worker2.result.connect(lambda r: QMessageBox.information(self,"yt-dlp", t["update_done"] if r=="done" else r))
                self.upd_worker2.start()

    # ── UI KURULUM ────────────────────────────
    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.resize(1060, 860)

        self.setStyleSheet("""
            QWidget { background-color: #0E0E18; color: #FFFFFF; font-family: 'Segoe UI'; }

            QWidget#appContainer { background-color: #0E0E18; border-radius: 14px; border: 1px solid #1E1E30; }
            QWidget#sidebar { background-color: #090912; border-top-left-radius: 14px; border-bottom-left-radius: 14px; border-right: 1px solid #1A1A2A; }

            QPushButton.menuBtn { background-color: transparent; color: #6A6A8E; border: none; text-align: left; padding: 14px 20px; font-size: 14px; font-weight: bold; border-left: 4px solid transparent; border-radius: 0; }
            QPushButton.menuBtn:hover { color: #FFFFFF; background-color: #13131F; }
            QPushButton.menuBtn[active="true"] { color: #FFFFFF; background-color: #16162A; border-left: 4px solid #C850C0; }

            QFrame { background-color: #0E0E18; }
            QFrame.card { background-color: #16162A; border-radius: 10px; border: 1px solid #22223A; }
            QFrame#previewCard { background-color: #12121E; border-radius: 8px; border: 1px solid #22223A; }
            QFrame#dropZone { background-color: #12121E; border-radius: 10px; border: 2px dashed #28283A; }
            QFrame#dropZone:hover { border: 2px dashed #9D4EDD; }

            QLabel { color: #FFFFFF; font-family: 'Segoe UI'; font-size: 14px; font-weight: 600; background: transparent; }
            QLabel.title { font-size: 20px; font-weight: 800; color: #E2E8F0; }
            QLabel.subtext { color: #6A6A8E; font-size: 12px; font-weight: 400; }
            QLabel.sectionLabel { color: #9D9DBE; font-size: 12px; font-weight: 700; letter-spacing: 1px; }

            QLineEdit { background-color: #0E0E18; border: 1px solid #22223A; border-radius: 6px; padding: 11px; color: #E2E8F0; font-size: 14px; selection-background-color: #7B2FBE; }
            QLineEdit:focus { border: 1px solid #9D4EDD; }
            QLineEdit:read-only { color: #8A8AAE; }

            QComboBox { background-color: #0E0E18; border: 1px solid #22223A; border-radius: 6px; padding: 11px; color: #E2E8F0; font-size: 14px; }
            QComboBox:focus { border: 1px solid #9D4EDD; }
            QComboBox::drop-down { border: none; width: 28px; background: transparent; }
            QComboBox::down-arrow { width: 10px; height: 10px; }
            QComboBox QAbstractItemView { background-color: #16162A; color: #CCCCEE; border: 1px solid #28283A; selection-background-color: #7B2FBE; outline: none; }

            QTextEdit { background-color: #090912; color: #8A8AAE; border: 1px solid #22223A; border-radius: 6px; padding: 10px; font-family: Consolas, monospace; font-size: 12px; }

            QPushButton { background-color: #1E1E32; color: #CCCCEE; border: 1px solid #2E2E48; border-radius: 6px; padding: 8px 12px; }
            QPushButton.secondaryBtn { background-color: #1E1E32; color: #CCCCEE; border: 1px solid #2E2E48; border-radius: 6px; padding: 10px 14px; font-weight: 600; font-size: 13px; }
            QPushButton.secondaryBtn:hover { background-color: #28283C; color: #FFFFFF; }
            QPushButton#closeBtn { background-color: transparent; color: #6A6A8E; border: none; font-size: 16px; font-weight: bold; border-radius: 15px; }
            QPushButton#closeBtn:hover { background-color: #FF4D6D; color: white; }
            QPushButton#langBtn { font-size: 12px; padding: 5px 8px; background-color: #16162A; color: #C850C0; border: 1px solid #28283A; border-radius: 6px; font-weight: bold; }
            QPushButton#langBtn:hover { background-color: #22223A; }

            QProgressBar { border: none; border-radius: 4px; background-color: #1A1A2A; color: transparent; height: 6px; text-align: center; }
            QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7B2FBE,stop:1 #C850C0); border-radius: 3px; }

            QCheckBox { color: #CCCCEE; font-size: 13px; spacing: 8px; background: transparent; }
            QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #3A3A5A; background: #0E0E18; }
            QCheckBox::indicator:checked { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #7B2FBE,stop:1 #C850C0); border: 1px solid #9D4EDD; }

            QTableWidget { background-color: #0E0E18; color: #CCCCEE; border: 1px solid #22223A; border-radius: 6px; gridline-color: #1A1A2A; font-size: 13px; }
            QTableWidget::item { background-color: #0E0E18; color: #CCCCEE; padding: 4px; border: none; }
            QTableWidget::item:selected { background-color: #22223A; color: #FFFFFF; }
            QTableWidget::item:alternate { background-color: #111122; }
            QTableCornerButton::section { background-color: #16162A; border: none; }
            QHeaderView { background-color: #16162A; }
            QHeaderView::section { background-color: #16162A; color: #9D9DBE; border: none; border-bottom: 1px solid #22223A; padding: 8px; font-weight: 700; font-size: 12px; }

            QScrollArea { border: none; background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollBar:vertical { background: #0E0E18; width: 6px; border-radius: 3px; margin: 0; }
            QScrollBar::handle:vertical { background: #28283A; border-radius: 3px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal { background: #0E0E18; height: 6px; border-radius: 3px; }
            QScrollBar::handle:horizontal { background: #28283A; border-radius: 3px; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

            QSpinBox { background-color: #0E0E18; border: 1px solid #22223A; border-radius: 6px; padding: 8px; color: #E2E8F0; font-size: 14px; }
            QSpinBox::up-button, QSpinBox::down-button { background-color: #1E1E32; border: none; width: 20px; }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover { background-color: #28283C; }
            QSpinBox::up-arrow { width: 8px; height: 8px; }
            QSpinBox::down-arrow { width: 8px; height: 8px; }

            QMenu { background-color: #16162A; border: 1px solid #28283A; color: #CCCCEE; padding: 4px; border-radius: 6px; }
            QMenu::item { padding: 8px 20px; border-radius: 4px; }
            QMenu::item:selected { background-color: #7B2FBE; color: #FFFFFF; }
            QMenu::separator { background: #28283A; height: 1px; margin: 4px 8px; }

            QMessageBox { background-color: #0E0E18; }
            QMessageBox QLabel { color: #CCCCEE; background: transparent; }
            QMessageBox QPushButton { background-color: #1E1E32; color: #CCCCEE; border: 1px solid #2E2E48; border-radius: 6px; padding: 8px 20px; min-width: 80px; }
            QMessageBox QPushButton:hover { background-color: #28283C; }

            QFileDialog { background-color: #0E0E18; color: #CCCCEE; }
        """ + GRADIENT_BTN_QSS)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        self.app_container = QWidget(self)
        self.app_container.setObjectName("appContainer")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30); shadow.setXOffset(0); shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 220))
        self.app_container.setGraphicsEffect(shadow)

        app_layout = QHBoxLayout(self.app_container)
        app_layout.setContentsMargins(0, 0, 0, 0); app_layout.setSpacing(0)

        # SIDEBAR
        sidebar = QWidget(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(220)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 28, 0, 20); sb_layout.setSpacing(0)

        logo_row = QHBoxLayout(); logo_row.setContentsMargins(20, 0, 0, 0)
        logo_ico = QLabel("▶"); logo_ico.setStyleSheet(
            "font-size:18px; background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #7B2FBE,stop:1 #C850C0); -webkit-background-clip:text; color:#C850C0;")
        logo_txt = QLabel("YT-DL")
        logo_txt.setStyleSheet("font-size:15px;font-weight:900;color:#E2E8F0;letter-spacing:2px;")
        logo_row.addWidget(logo_ico); logo_row.addWidget(logo_txt); logo_row.addStretch()
        sb_layout.addLayout(logo_row); sb_layout.addSpacing(24)

        self.btn_single = QPushButton("")
        self.btn_batch = QPushButton("")
        self.btn_history = QPushButton("")
        self.btn_settings = QPushButton("")
        self.menu_buttons = [self.btn_single, self.btn_batch, self.btn_history, self.btn_settings]
        for idx, btn in enumerate(self.menu_buttons):
            btn.setProperty("class", "menuBtn"); btn.setProperty("active", "false")
            btn.clicked.connect(lambda c, i=idx: self.switch_page(i))
            sb_layout.addWidget(btn)

        sb_layout.addStretch()

        # ffmpeg durum göstergesi sidebar'da
        self.lbl_ffmpeg_status = QLabel("")
        self.lbl_ffmpeg_status.setContentsMargins(20, 0, 0, 0)
        self.lbl_ffmpeg_status.setWordWrap(True)
        if FFMPEG_PATH:
            self.lbl_ffmpeg_status.setText("✔ ffmpeg")
            self.lbl_ffmpeg_status.setStyleSheet("color:#4ADE80;font-size:11px;font-weight:600;")
        else:
            self.lbl_ffmpeg_status.setText("✘ ffmpeg yok!")
            self.lbl_ffmpeg_status.setStyleSheet("color:#FF4D6D;font-size:11px;font-weight:600;")
        sb_layout.addWidget(self.lbl_ffmpeg_status)
        sb_layout.addSpacing(4)

        self.lbl_update = QLabel("")
        self.lbl_update.setProperty("class", "subtext")
        self.lbl_update.setContentsMargins(20, 0, 0, 0)
        self.lbl_update.setWordWrap(True)
        sb_layout.addWidget(self.lbl_update)
        sb_layout.addSpacing(8)

        user_row = QHBoxLayout(); user_row.setContentsMargins(20, 0, 20, 0)
        self.user_label = QLabel("◉  YT Downloader")
        self.user_label.setStyleSheet("color:#4A4A6E;font-size:12px;font-weight:600;")
        self.btn_lang = QPushButton(""); self.btn_lang.setObjectName("langBtn")
        self.btn_lang.setFixedSize(60, 28); self.btn_lang.clicked.connect(self.toggle_language)
        user_row.addWidget(self.user_label); user_row.addStretch(); user_row.addWidget(self.btn_lang)
        sb_layout.addLayout(user_row)

        # CONTENT
        content = QWidget()
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(28, 20, 28, 28); c_layout.setSpacing(0)

        topbar = QHBoxLayout()
        self.page_title = QLabel("")
        self.page_title.setProperty("class", "title")
        close_btn = QPushButton("✕"); close_btn.setObjectName("closeBtn"); close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.close)
        topbar.addWidget(self.page_title); topbar.addStretch(); topbar.addWidget(close_btn)
        c_layout.addLayout(topbar); c_layout.addSpacing(16)

        self.stacked = QStackedWidget()
        self.setup_single_page()
        self.setup_batch_page()
        self.setup_history_page()
        self.setup_settings_page()
        c_layout.addWidget(self.stacked)

        app_layout.addWidget(sidebar); app_layout.addWidget(content)
        main_layout.addWidget(self.app_container)
        self.switch_page(0)

    # ── DİL ───────────────────────────────────
    def toggle_language(self):
        self.lang = "EN" if self.lang == "TR" else "TR"
        self.config["language"] = self.lang; save_config(self.config)
        self.update_texts()
        self.set_lang.setCurrentIndex(0 if self.lang == "TR" else 1)

    def update_texts(self):
        t = LANG[self.lang]
        self.btn_single.setText(t["menu_single"])
        self.btn_batch.setText(t["menu_batch"])
        self.btn_history.setText(t["menu_history"])
        self.btn_settings.setText(t["menu_settings"])
        self.btn_lang.setText(t["btn_lang"])

        titles = [t["title_single"], t["title_batch"], t["title_history"], t["title_settings"]]
        self.page_title.setText(titles[self.stacked.currentIndex()])

        self.lbl_url.setText(t["lbl_url"])
        self.s_url.setPlaceholderText(t["ph_url"])
        self.lbl_format_qual.setText(t["lbl_format_qual"])
        self.s_format.setItemText(0, t["mp4_opt"]); self.s_format.setItemText(1, t["mp3_opt"])
        if self.s_status.text() in ["Hazır.", "Ready."]:
            self.s_status.setText(t["status_ready"])
        self.s_btn.setText(t["btn_start"])
        self.lbl_trim.setText(t["lbl_trim"])
        self.lbl_trim_start.setText(t["lbl_trim_start"])
        self.lbl_trim_end.setText(t["lbl_trim_end"])
        self.trim_start.setPlaceholderText(t["ph_trim"])
        self.trim_end.setPlaceholderText(t["ph_trim"])
        self.chk_id3.setText(t["lbl_id3"])
        self.chk_subs.setText(t["lbl_subtitle"])

        self.lbl_batch_desc.setText(t["lbl_batch_desc"])
        self.b_path.setPlaceholderText(t["ph_json"])
        self.b_browse.setText(t["btn_browse"])
        self.lbl_log.setText(t["lbl_log"])
        self.b_btn.setText(t["btn_start_batch"])
        self.lbl_playlist_url.setText(t["lbl_playlist_url"])
        self.playlist_url.setPlaceholderText(t["ph_playlist"])
        self.btn_load_playlist.setText(t["btn_load_playlist"])
        self.btn_select_all.setText(t["btn_select_all"])
        self.btn_deselect.setText(t["btn_deselect"])
        self.chk_concurrent.setText(t["lbl_concurrent_opt"])
        self.chk_batch_id3.setText(t["lbl_id3"])

        self.btn_clear_hist.setText(t["btn_clear_history"])

        self.lbl_def_lang.setText(t["lbl_def_lang"])
        self.lbl_def_type.setText(t["lbl_def_type"])
        self.lbl_def_mp4.setText(t["lbl_def_mp4"])
        self.lbl_def_mp3.setText(t["lbl_def_mp3"])
        self.lbl_def_path.setText(t["lbl_def_path"])
        self.lbl_concurrent_setting.setText(t["lbl_concurrent"])
        self.btn_path_change.setText(t["btn_change"])
        self.btn_save_set.setText(t["btn_save"])

        self.update_estimated_size()

    def switch_page(self, index):
        self.stacked.setCurrentIndex(index)
        t = LANG[self.lang]
        titles = [t["title_single"], t["title_batch"], t["title_history"], t["title_settings"]]
        self.page_title.setText(titles[index])
        for i, btn in enumerate(self.menu_buttons):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn); btn.style().polish(btn)
        if index == 2:
            self.refresh_history()

    # ── DRAG & DROP ───────────────────────────
    def dragEnterEvent(self, event):
        if event.mimeData().hasText() or event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        text = ""
        if event.mimeData().hasUrls():
            text = event.mimeData().urls()[0].toString()
        elif event.mimeData().hasText():
            text = event.mimeData().text().strip()
        if text:
            self.switch_page(0)
            self.s_url.setText(text)
            self.fetch_video_info()

    # ── PENCERE SÜRÜKLEME ─────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.dragPos = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton:
            self.move(e.globalPos() - self.dragPos)

    # ══════════════════════════════════════════
    #  SAYFA 1: TEKLİ İNDİRİCİ
    # ══════════════════════════════════════════
    def setup_single_page(self):
        page = QWidget()
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(page)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        layout = QVBoxLayout(page); layout.setSpacing(14); layout.setContentsMargins(0, 0, 8, 0)

        url_card = QFrame(); url_card.setProperty("class", "card")
        url_c = QVBoxLayout(url_card); url_c.setContentsMargins(20, 18, 20, 18); url_c.setSpacing(10)
        self.lbl_url = QLabel("")
        url_row = QHBoxLayout()
        self.s_url = QLineEdit(); self.s_url.returnPressed.connect(self.fetch_video_info)
        self.btn_fetch = QPushButton("🔍"); self.btn_fetch.setProperty("class", "secondaryBtn")
        self.btn_fetch.setFixedSize(44, 44); self.btn_fetch.clicked.connect(self.fetch_video_info)
        url_row.addWidget(self.s_url); url_row.addWidget(self.btn_fetch)
        url_c.addWidget(self.lbl_url); url_c.addLayout(url_row)

        self.lbl_drop = QLabel("")
        self.lbl_drop.setAlignment(Qt.AlignCenter)
        self.lbl_drop.setStyleSheet("color:#2E2E4A;font-size:12px;font-weight:600;letter-spacing:1px;")
        url_c.addWidget(self.lbl_drop)

        self.preview_card = QFrame(); self.preview_card.setObjectName("previewCard"); self.preview_card.hide()
        prev_lay = QHBoxLayout(self.preview_card); prev_lay.setContentsMargins(14, 14, 14, 14); prev_lay.setSpacing(14)
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedSize(160, 90)
        self.lbl_thumb.setStyleSheet("background-color:#090912;border-radius:6px;")
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        info_v = QVBoxLayout()
        self.lbl_vid_title = QLabel(); self.lbl_vid_title.setWordWrap(True)
        self.lbl_vid_title.setStyleSheet("font-size:14px;font-weight:700;color:#FFFFFF;")
        self.lbl_vid_size = QLabel()
        self.lbl_vid_size.setStyleSheet("font-size:13px;font-weight:700;color:#C850C0;")
        info_v.addWidget(self.lbl_vid_title); info_v.addWidget(self.lbl_vid_size); info_v.addStretch()
        prev_lay.addWidget(self.lbl_thumb); prev_lay.addLayout(info_v)

        fmt_card = QFrame(); fmt_card.setProperty("class", "card")
        fmt_c = QVBoxLayout(fmt_card); fmt_c.setContentsMargins(20, 18, 20, 18); fmt_c.setSpacing(10)
        self.lbl_format_qual = QLabel("")
        opt_row = QHBoxLayout()
        self.s_format = QComboBox(); self.s_format.addItems(['MP4', 'MP3'])
        self.s_quality = QComboBox()
        self.s_format.currentTextChanged.connect(self.update_single_quality)
        self.s_format.currentTextChanged.connect(self.update_estimated_size)
        self.s_quality.currentTextChanged.connect(self.update_estimated_size)
        opt_row.addWidget(self.s_format, 1); opt_row.addWidget(self.s_quality, 1)
        fmt_c.addWidget(self.lbl_format_qual); fmt_c.addLayout(opt_row)

        chk_row = QHBoxLayout()
        self.chk_id3 = QCheckBox(""); self.chk_subs = QCheckBox("")
        chk_row.addWidget(self.chk_id3); chk_row.addWidget(self.chk_subs); chk_row.addStretch()
        fmt_c.addLayout(chk_row)

        trim_card = QFrame(); trim_card.setProperty("class", "card")
        trim_c = QVBoxLayout(trim_card); trim_c.setContentsMargins(20, 18, 20, 18); trim_c.setSpacing(10)
        self.lbl_trim = QLabel("")
        trim_row = QHBoxLayout()
        self.lbl_trim_start = QLabel(""); self.trim_start = QLineEdit(); self.trim_start.setFixedWidth(100)
        self.lbl_trim_end = QLabel(""); self.trim_end = QLineEdit(); self.trim_end.setFixedWidth(100)
        trim_row.addWidget(self.lbl_trim_start); trim_row.addWidget(self.trim_start)
        trim_row.addSpacing(16)
        trim_row.addWidget(self.lbl_trim_end); trim_row.addWidget(self.trim_end); trim_row.addStretch()
        trim_c.addWidget(self.lbl_trim); trim_c.addLayout(trim_row)

        idx = 0 if self.config["default_format"] == "MP4" else 1
        self.s_format.setCurrentIndex(idx)
        self.update_single_quality(self.s_format.currentText())

        self.s_status = QLabel(""); self.s_status.setProperty("class", "subtext")
        self.s_prog = QProgressBar(); self.s_prog.setValue(0)
        self.s_btn = QPushButton(""); self.s_btn.setProperty("class", "primaryBtn")
        self.s_btn.clicked.connect(self.start_single_download)

        layout.addWidget(url_card); layout.addWidget(self.preview_card)
        layout.addWidget(fmt_card); layout.addWidget(trim_card)
        layout.addStretch()
        layout.addWidget(self.s_status); layout.addWidget(self.s_prog); layout.addWidget(self.s_btn)

        self.stacked.addWidget(scroll)

    def fetch_video_info(self):
        url = self.s_url.text().strip(); t = LANG[self.lang]
        if not url: return
        self.btn_fetch.setEnabled(False); self.s_status.setText(t["msg_fetching"])
        self.info_thread = InfoWorker(url)
        self.info_thread.finished.connect(self.on_info_fetched)
        self.info_thread.error.connect(self.on_info_error)
        self.info_thread.start()

    def on_info_fetched(self, info, thumb):
        self.btn_fetch.setEnabled(True); self.current_vid_info = info
        t = LANG[self.lang]; self.s_status.setText(t["status_ready"])
        self.lbl_vid_title.setText(info.get('title', ''))
        if thumb:
            pix = QPixmap(); pix.loadFromData(thumb)
            self.lbl_thumb.setPixmap(pix.scaled(160, 90, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        self.preview_card.show(); self.update_estimated_size()

    def on_info_error(self, err):
        self.btn_fetch.setEnabled(True); t = LANG[self.lang]
        self.s_status.setText(t["msg_error"])
        QMessageBox.warning(self, t["msg_error"], err)

    def update_estimated_size(self):
        if not self.current_vid_info: return
        t = LANG[self.lang]; info = self.current_vid_info
        fmt = self.s_format.currentText(); qual = self.s_quality.currentText()
        duration = info.get('duration', 0) or 0; size_mb = 0
        if 'MP3' in fmt:
            try:
                kbps = int(qual.replace('k', ''))
                size_mb = (kbps * duration) / 8192
            except: pass
        else:
            try:
                h = int(qual.replace('p', '')); v = 0; a = 0
                for f in info.get('formats', []):
                    if f.get('vcodec') != 'none' and f.get('height') == h and f.get('ext') == 'mp4':
                        v = f.get('filesize') or f.get('filesize_approx') or 0; break
                for f in info.get('formats', []):
                    if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('ext') == 'm4a':
                        a = f.get('filesize') or f.get('filesize_approx') or 0; break
                size_mb = (v + a) / (1024 * 1024)
            except: pass
        if size_mb > 0:
            self.lbl_vid_size.setText(f"{t['msg_size']} ~{size_mb:.1f} MB")
        else:
            self.lbl_vid_size.setText(f"{t['msg_size']} {t['msg_unknown']}")

    def update_single_quality(self, text):
        self.s_quality.clear()
        if 'MP3' in text:
            self.s_quality.addItems(['128k', '192k', '256k', '320k'])
            self.s_quality.setCurrentText(self.config["default_mp3_quality"])
        else:
            self.s_quality.addItems(['360p', '480p', '720p', '1080p'])
            self.s_quality.setCurrentText(self.config["default_mp4_quality"])

    def start_single_download(self):
        url = self.s_url.text().strip(); t = LANG[self.lang]
        if not url: return QMessageBox.warning(self, t["msg_warning"], t["msg_enter_link"])
        # ffmpeg kontrolü — indirmeden önce uyar
        if not FFMPEG_PATH:
            return QMessageBox.critical(self, t["msg_error"], t["msg_ffmpeg_missing"])
        fmt = 'MP3' if 'MP3' in self.s_format.currentText() else 'MP4'
        qual = self.s_quality.currentText()
        tasks = [{"url": url, "format": fmt, "quality": qual,
                  "title": self.lbl_vid_title.text() if self.current_vid_info else url}]
        self.s_btn.setEnabled(False); self.s_status.setText(t["status_connecting"]); self.s_prog.setValue(0)
        self.worker = DownloadWorker(tasks, self.config, t,
                                     embed_id3=self.chk_id3.isChecked(),
                                     embed_subs=self.chk_subs.isChecked(),
                                     trim_start=self.trim_start.text(),
                                     trim_end=self.trim_end.text())
        self.worker.progress.connect(lambda v, sp, et: (
            self.s_prog.setValue(v),
            self.s_status.setText(f"{t['msg_downloading']} %{v} | ⚡ {sp} | ⏳ {t['msg_eta']}: {et}")
        ))
        self.worker.finished.connect(self.on_single_done)
        self.worker.error.connect(lambda err: self.download_error(err, self.s_btn, self.s_status))
        self.worker.start()

    def on_single_done(self, title, url, size_mb):
        t = LANG[self.lang]
        fmt = 'MP3' if 'MP3' in self.s_format.currentText() else 'MP4'
        qual = self.s_quality.currentText()
        add_history(title, url, size_mb, fmt, qual, self.config["save_path"])
        self.s_btn.setEnabled(True); self.s_prog.setValue(100)
        self.s_status.setText(t["msg_done"])
        self.tray.showMessage(t["notify_done_title"], title or t["notify_done_msg"],
                              QSystemTrayIcon.Information, 4000)
        QMessageBox.information(self, t["msg_success"], t["msg_single_done"])

    # ══════════════════════════════════════════
    #  SAYFA 2: TOPLU İNDİRİCİ
    # ══════════════════════════════════════════
    def setup_batch_page(self):
        page = QWidget()
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(page)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        layout = QVBoxLayout(page); layout.setSpacing(14); layout.setContentsMargins(0, 0, 8, 0)

        json_card = QFrame(); json_card.setProperty("class", "card")
        jc = QVBoxLayout(json_card); jc.setContentsMargins(20, 18, 20, 18); jc.setSpacing(10)
        self.lbl_batch_desc = QLabel(); self.lbl_batch_desc.setProperty("class", "subtext")
        self.lbl_batch_desc.setWordWrap(True)
        jrow = QHBoxLayout()
        self.b_path = QLineEdit(); self.b_path.setReadOnly(True)
        self.b_browse = QPushButton(); self.b_browse.setProperty("class", "secondaryBtn")
        self.b_browse.clicked.connect(self.load_json)
        jrow.addWidget(self.b_path); jrow.addWidget(self.b_browse)
        jc.addWidget(self.lbl_batch_desc); jc.addLayout(jrow)

        pl_card = QFrame(); pl_card.setProperty("class", "card")
        plc = QVBoxLayout(pl_card); plc.setContentsMargins(20, 18, 20, 18); plc.setSpacing(10)
        self.lbl_playlist_url = QLabel("")
        pl_row = QHBoxLayout()
        self.playlist_url = QLineEdit()
        self.btn_load_playlist = QPushButton(""); self.btn_load_playlist.setProperty("class", "secondaryBtn")
        self.btn_load_playlist.clicked.connect(self.load_playlist)
        pl_row.addWidget(self.playlist_url); pl_row.addWidget(self.btn_load_playlist)

        sel_row = QHBoxLayout()
        self.btn_select_all = QPushButton(""); self.btn_select_all.setProperty("class", "secondaryBtn")
        self.btn_select_all.clicked.connect(lambda: self.toggle_playlist_selection(True))
        self.btn_deselect = QPushButton(""); self.btn_deselect.setProperty("class", "secondaryBtn")
        self.btn_deselect.clicked.connect(lambda: self.toggle_playlist_selection(False))
        sel_row.addWidget(self.btn_select_all); sel_row.addWidget(self.btn_deselect); sel_row.addStretch()

        self.playlist_table = QTableWidget(0, 3)
        self.playlist_table.setMaximumHeight(220)
        self.playlist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.playlist_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.playlist_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.playlist_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.playlist_table.hide()
        plc.addWidget(self.lbl_playlist_url); plc.addLayout(pl_row)
        plc.addLayout(sel_row); plc.addWidget(self.playlist_table)

        opt_card = QFrame(); opt_card.setProperty("class", "card")
        oc = QVBoxLayout(opt_card); oc.setContentsMargins(20, 16, 20, 16); oc.setSpacing(10)
        self.chk_concurrent = QCheckBox("")
        self.chk_batch_id3 = QCheckBox("")
        oc.addWidget(self.chk_concurrent); oc.addWidget(self.chk_batch_id3)

        self.lbl_log = QLabel("")
        self.b_log = QTextEdit(); self.b_log.setReadOnly(True); self.b_log.setMaximumHeight(140)

        self.b_status = QLabel(""); self.b_status.setProperty("class", "subtext")
        self.b_prog = QProgressBar(); self.b_prog.setValue(0)
        self.b_btn = QPushButton(""); self.b_btn.setProperty("class", "primaryBtn")
        self.b_btn.clicked.connect(self.start_batch_download)

        layout.addWidget(json_card); layout.addWidget(pl_card); layout.addWidget(opt_card)
        layout.addWidget(self.lbl_log); layout.addWidget(self.b_log)
        layout.addStretch()
        layout.addWidget(self.b_status); layout.addWidget(self.b_prog); layout.addWidget(self.b_btn)
        self.stacked.addWidget(scroll)

    def load_json(self):
        t = LANG[self.lang]
        file, _ = QFileDialog.getOpenFileName(self, "JSON", "", "JSON Files (*.json)")
        if file:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    self.batch_tasks = json.load(f)
                self.b_path.setText(file)
                self.b_log.append(f"-> {len(self.batch_tasks)} {t['log_queued']}")
            except Exception as e:
                QMessageBox.critical(self, t["msg_error"], f"{t['msg_json_err']}\n{str(e)}")

    def load_playlist(self):
        url = self.playlist_url.text().strip(); t = LANG[self.lang]
        if not url: return
        self.btn_load_playlist.setEnabled(False)
        self.b_log.append(t["msg_fetching"])
        self.pl_worker = PlaylistWorker(url)
        self.pl_worker.finished.connect(self.on_playlist_loaded)
        self.pl_worker.error.connect(lambda e: (QMessageBox.warning(self, t["msg_error"], e),
                                                 self.btn_load_playlist.setEnabled(True)))
        self.pl_worker.start()

    def on_playlist_loaded(self, items):
        t = LANG[self.lang]
        self.playlist_items = items
        self.btn_load_playlist.setEnabled(True)
        self.playlist_table.setRowCount(0)
        self.playlist_table.setHorizontalHeaderLabels([t["col_select"], t["col_title"], t["col_duration"]])
        for item in items:
            r = self.playlist_table.rowCount(); self.playlist_table.insertRow(r)
            chk = QCheckBox(); chk.setChecked(True)
            chk_widget = QWidget(); chk_lay = QHBoxLayout(chk_widget)
            chk_lay.addWidget(chk); chk_lay.setAlignment(Qt.AlignCenter); chk_lay.setContentsMargins(0,0,0,0)
            self.playlist_table.setCellWidget(r, 0, chk_widget)
            self.playlist_table.setItem(r, 1, QTableWidgetItem(item['title']))
            self.playlist_table.setItem(r, 2, QTableWidgetItem(item['duration']))
        self.playlist_table.show()
        self.b_log.append(f"-> {len(items)} {t['log_queued']}")

    def toggle_playlist_selection(self, state):
        for r in range(self.playlist_table.rowCount()):
            w = self.playlist_table.cellWidget(r, 0)
            if w:
                chk = w.findChild(QCheckBox)
                if chk: chk.setChecked(state)

    def start_batch_download(self):
        t = LANG[self.lang]
        # ffmpeg kontrolü
        if not FFMPEG_PATH:
            return QMessageBox.critical(self, t["msg_error"], t["msg_ffmpeg_missing"])
        tasks = list(self.batch_tasks)
        if self.playlist_items:
            fmt = self.config["default_format"]
            qual = self.config["default_mp4_quality"] if fmt == "MP4" else self.config["default_mp3_quality"]
            for r in range(self.playlist_table.rowCount()):
                w = self.playlist_table.cellWidget(r, 0)
                if w:
                    chk = w.findChild(QCheckBox)
                    if chk and chk.isChecked() and r < len(self.playlist_items):
                        tasks.append({"url": self.playlist_items[r]['url'],
                                      "format": fmt, "quality": qual,
                                      "title": self.playlist_items[r]['title']})
        if not tasks:
            return QMessageBox.warning(self, t["msg_warning"], t["msg_invalid_json"])

        concurrent = self.config.get("concurrent_downloads", 2) if self.chk_concurrent.isChecked() else 1
        self.b_btn.setEnabled(False); self.b_prog.setValue(0)
        self.b_status.setText(t["status_connecting"])

        self.worker = DownloadWorker(tasks, self.config, t,
                                     embed_id3=self.chk_batch_id3.isChecked(),
                                     concurrent=concurrent)
        self.worker.progress.connect(lambda v, sp, et: (
            self.b_prog.setValue(v),
            self.b_status.setText(f"{t['msg_downloading']} %{v} | ⚡{sp} | ⏳{t['msg_eta']}: {et}")
        ))
        self.worker.log.connect(self.b_log.append)
        self.worker.finished.connect(self.on_batch_done)
        self.worker.error.connect(lambda err: self.download_error(err, self.b_btn, self.b_status))
        self.worker.start()

    def on_batch_done(self, title, url, size_mb):
        t = LANG[self.lang]
        self.b_btn.setEnabled(True); self.b_prog.setValue(100)
        self.b_status.setText(t["msg_done"])
        self.tray.showMessage(t["notify_done_title"], t["msg_batch_done"], QSystemTrayIcon.Information, 4000)
        QMessageBox.information(self, t["msg_success"], t["msg_batch_done"])

    # ══════════════════════════════════════════
    #  SAYFA 3: GEÇMİŞ
    # ══════════════════════════════════════════
    def setup_history_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.setSpacing(12)

        top_row = QHBoxLayout()
        self.btn_clear_hist = QPushButton(""); self.btn_clear_hist.setProperty("class", "secondaryBtn")
        self.btn_clear_hist.clicked.connect(self.on_clear_history)
        top_row.addStretch(); top_row.addWidget(self.btn_clear_hist)

        self.hist_table = QTableWidget(0, 4)
        self.hist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.hist_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.hist_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.hist_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.hist_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.hist_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.hist_table.verticalHeader().setVisible(False)

        layout.addLayout(top_row); layout.addWidget(self.hist_table)
        self.stacked.addWidget(page)

    def refresh_history(self):
        t = LANG[self.lang]
        self.hist_table.setHorizontalHeaderLabels([
            t["hist_col_title"], t["hist_col_size"], t["hist_col_date"], t["hist_col_actions"]])
        rows = load_history()
        self.hist_table.setRowCount(0)
        for (rid, title, size_mb, date, save_path) in rows:
            r = self.hist_table.rowCount(); self.hist_table.insertRow(r)
            self.hist_table.setItem(r, 0, QTableWidgetItem(title or ""))
            sz = f"{size_mb:.1f} MB" if size_mb else "?"
            self.hist_table.setItem(r, 1, QTableWidgetItem(sz))
            self.hist_table.setItem(r, 2, QTableWidgetItem(date or ""))
            act_w = QWidget(); act_lay = QHBoxLayout(act_w)
            act_lay.setContentsMargins(4, 2, 4, 2); act_lay.setSpacing(6)
            btn_open = QPushButton(t["btn_open_folder"]); btn_open.setProperty("class", "secondaryBtn")
            btn_open.setFixedSize(32, 28)
            btn_del = QPushButton(t["btn_delete_hist"]); btn_del.setProperty("class", "secondaryBtn")
            btn_del.setFixedSize(32, 28)
            _path = save_path
            btn_open.clicked.connect(lambda _, p=_path: self.open_folder(p))
            _rid = rid
            btn_del.clicked.connect(lambda _, i=_rid: self.delete_hist_row(i))
            act_lay.addWidget(btn_open); act_lay.addWidget(btn_del)
            self.hist_table.setCellWidget(r, 3, act_w)

    def open_folder(self, path):
        if os.path.exists(path):
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])

    def delete_hist_row(self, rid):
        delete_history(rid); self.refresh_history()

    def on_clear_history(self):
        t = LANG[self.lang]
        reply = QMessageBox.question(self, t["btn_clear_history"], "Tüm geçmiş silinsin mi?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            clear_history(); self.refresh_history()

    # ══════════════════════════════════════════
    #  SAYFA 4: AYARLAR
    # ══════════════════════════════════════════
    def setup_settings_page(self):
        page = QWidget()
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(page)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout = QVBoxLayout(page); layout.setSpacing(14); layout.setContentsMargins(0, 0, 8, 0)

        self.lbl_def_lang = QLabel(); self.lbl_def_type = QLabel()
        self.lbl_def_mp4 = QLabel(); self.lbl_def_mp3 = QLabel()
        self.lbl_def_path = QLabel(); self.lbl_concurrent_setting = QLabel()

        card0 = QFrame(); card0.setProperty("class", "card")
        c0 = QVBoxLayout(card0); c0.setContentsMargins(20, 18, 20, 18); c0.setSpacing(10)
        self.set_lang = QComboBox(); self.set_lang.addItems(['Türkçe (TR)', 'English (EN)'])
        self.set_lang.setCurrentIndex(0 if self.config.get("language","TR")=="TR" else 1)
        c0.addWidget(self.lbl_def_lang); c0.addWidget(self.set_lang)

        card1 = QFrame(); card1.setProperty("class", "card")
        c1 = QVBoxLayout(card1); c1.setContentsMargins(20, 18, 20, 18); c1.setSpacing(10)
        self.set_format = QComboBox(); self.set_format.addItems(['MP4', 'MP3'])
        self.set_format.setCurrentText(self.config["default_format"])
        self.set_mp4 = QComboBox(); self.set_mp4.addItems(['360p','480p','720p','1080p'])
        self.set_mp4.setCurrentText(self.config["default_mp4_quality"])
        self.set_mp3 = QComboBox(); self.set_mp3.addItems(['128k','192k','256k','320k'])
        self.set_mp3.setCurrentText(self.config["default_mp3_quality"])
        c1.addWidget(self.lbl_def_type); c1.addWidget(self.set_format)
        c1.addWidget(self.lbl_def_mp4); c1.addWidget(self.set_mp4)
        c1.addWidget(self.lbl_def_mp3); c1.addWidget(self.set_mp3)

        card2 = QFrame(); card2.setProperty("class", "card")
        c2 = QVBoxLayout(card2); c2.setContentsMargins(20, 18, 20, 18); c2.setSpacing(10)
        path_row = QHBoxLayout()
        self.set_path = QLineEdit(); self.set_path.setText(self.config["save_path"]); self.set_path.setReadOnly(True)
        self.btn_path_change = QPushButton(); self.btn_path_change.setProperty("class", "secondaryBtn")
        self.btn_path_change.clicked.connect(lambda: (
            self.set_path.setText(f) if (f := QFileDialog.getExistingDirectory(self, "")) else None))
        path_row.addWidget(self.set_path); path_row.addWidget(self.btn_path_change)
        c2.addWidget(self.lbl_def_path); c2.addLayout(path_row)

        card3 = QFrame(); card3.setProperty("class", "card")
        c3 = QVBoxLayout(card3); c3.setContentsMargins(20, 18, 20, 18); c3.setSpacing(10)
        self.spin_concurrent = QSpinBox(); self.spin_concurrent.setRange(1, 8)
        self.spin_concurrent.setValue(self.config.get("concurrent_downloads", 2))
        c3.addWidget(self.lbl_concurrent_setting); c3.addWidget(self.spin_concurrent)

        # ffmpeg yolu bilgi kartı
        card4 = QFrame(); card4.setProperty("class", "card")
        c4 = QVBoxLayout(card4); c4.setContentsMargins(20, 18, 20, 18); c4.setSpacing(6)
        lbl_ffmpeg_hdr = QLabel("ffmpeg")
        lbl_ffmpeg_hdr.setStyleSheet("font-size:13px;font-weight:700;color:#9D9DBE;")
        lbl_ffmpeg_val = QLabel(FFMPEG_PATH if FFMPEG_PATH else "❌ Bulunamadı — https://www.gyan.dev/ffmpeg/builds/")
        lbl_ffmpeg_val.setWordWrap(True)
        lbl_ffmpeg_val.setStyleSheet(
            "font-size:12px;color:#4ADE80;" if FFMPEG_PATH else "font-size:12px;color:#FF4D6D;"
        )
        c4.addWidget(lbl_ffmpeg_hdr); c4.addWidget(lbl_ffmpeg_val)

        self.btn_save_set = QPushButton(); self.btn_save_set.setProperty("class", "primaryBtn")
        self.btn_save_set.clicked.connect(self.save_settings)

        layout.addWidget(card0); layout.addWidget(card1); layout.addWidget(card2)
        layout.addWidget(card3); layout.addWidget(card4)
        layout.addStretch(); layout.addWidget(self.btn_save_set)
        self.stacked.addWidget(scroll)

    def save_settings(self):
        t = LANG[self.lang]
        new_lang = "TR" if "TR" in self.set_lang.currentText() else "EN"
        self.config.update({
            "language": new_lang,
            "default_format": self.set_format.currentText(),
            "default_mp4_quality": self.set_mp4.currentText(),
            "default_mp3_quality": self.set_mp3.currentText(),
            "save_path": self.set_path.text(),
            "concurrent_downloads": self.spin_concurrent.value(),
        })
        save_config(self.config)
        if self.lang != new_lang:
            self.lang = new_lang; self.update_texts()
        QMessageBox.information(self, t["msg_success"], t["msg_settings_saved"])

    # ── ORTAK ─────────────────────────────────
    def download_error(self, err, btn, status_lbl):
        t = LANG[self.lang]
        if status_lbl: status_lbl.setText(t["msg_error"])
        btn.setEnabled(True)
        QMessageBox.critical(self, t["msg_error"], str(err))


# ─────────────────────────────────────────────
if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    ex = MainApp()
    ex.show()
    sys.exit(app.exec_())