import json
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont, QFontDatabase
from config_utils import SETTINGS_PATH
import os

FONT_PATH    = os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts', 'pixel.ttf')
COOKIE_HELP_URL = "https://github.com/cwendt94/espn-api/discussions/150"


def _load_pixel_font(size: int = 8) -> QFont:
    font_id  = QFontDatabase.addApplicationFont(FONT_PATH)
    families = QFontDatabase.applicationFontFamilies(font_id)
    return QFont(families[0], size) if families else QFont("Courier", size)


class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fantasy Pet — Setup")
        self.setFixedSize(220, 290)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("""
            QDialog { background-color: #D8E2F0; border-radius: 8px; }
            QLabel  { color: #000A14; }
            QLineEdit {
                background-color: #C5D5E8;
                color: #000A14;
                border: 1px solid #929EAF;
                border-radius: 4px;
                padding: 2px 4px;
            }
            QPushButton {
                background-color: #A7C2E5;
                color: #000A14;
                border-radius: 4px;
                padding: 2px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #929EAF; }
            QPushButton#help_btn {
                background-color: transparent;
                color: #000A14;
                text-decoration: underline;
                padding: 0;
            }
            QPushButton#close_btn, QPushButton#min_btn {
                background-color: transparent;
                color: #000A14;
                border: none;
                padding: 0 4px;
                font-weight: bold;
            }
            QPushButton#close_btn:hover { color: #c85977; }
            QPushButton#min_btn:hover   { color: #929EAF; }
        """)
        self._drag_pos = None
        self._build_ui()
        self._load_existing()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Custom title bar ──────────────────────────────────────────────────
        title_bar = QWidget()
        title_bar.setFixedHeight(28)
        title_bar.setStyleSheet(
            "background-color: #A7C2E5;"
            "border-top-left-radius: 8px;"
            "border-top-right-radius: 8px;"
            "border-bottom-left-radius: 0px;"
            "border-bottom-right-radius: 0px;"
        )
        title_bar.mousePressEvent   = self._title_mouse_press
        title_bar.mouseMoveEvent    = self._title_mouse_move

        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(8, 0, 4, 0)
        tb_layout.setSpacing(2)

        tb_layout.addStretch()

        min_btn = QPushButton("—")
        min_btn.setObjectName("min_btn")
        min_btn.setFixedSize(20, 20)
        min_btn.setFont(_load_pixel_font(7))
        min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        min_btn.clicked.connect(self.showMinimized)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(20, 20)
        close_btn.setFont(_load_pixel_font(7))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)

        tb_layout.addWidget(min_btn)
        tb_layout.addWidget(close_btn)

        root.addWidget(title_bar)

        # ── Content ───────────────────────────────────────────────────────────
        content = QWidget()
        content.setStyleSheet(
            "background-color: #D8E2F0;"
            "border-bottom-left-radius: 8px;"
            "border-bottom-right-radius: 8px;"
            "border-top-left-radius: 0px;"
            "border-top-right-radius: 0px;"
        )
        layout = QVBoxLayout(content)
        layout.setSpacing(4)
        layout.setContentsMargins(16, 10, 16, 12)

        title = QLabel("SETUP")
        title.setFont(_load_pixel_font(10))
        title.setStyleSheet("color: #000A14;")
        layout.addWidget(title)

        # League ID
        lbl1 = QLabel("League ID")
        lbl1.setFont(_load_pixel_font(6))
        layout.addWidget(lbl1)
        self._league_id = QLineEdit()
        self._league_id.setFont(_load_pixel_font(6))
        self._league_id.setPlaceholderText("000000000")
        layout.addWidget(self._league_id)

        # espn_s2
        lbl2 = QLabel("espn_s2 cookie")
        lbl2.setFont(_load_pixel_font(6))
        layout.addWidget(lbl2)
        self._espn_s2 = QLineEdit()
        self._espn_s2.setFont(_load_pixel_font(6))
        self._espn_s2.setPlaceholderText("Long string from browser")
        self._espn_s2.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._espn_s2)

        # SWID
        lbl3 = QLabel("SWID cookie")
        lbl3.setFont(_load_pixel_font(6))
        layout.addWidget(lbl3)
        self._swid = QLineEdit()
        self._swid.setFont(_load_pixel_font(6))
        self._swid.setPlaceholderText("{XXXX-XXXX-XXXX}")
        layout.addWidget(self._swid)

        # Help + Save row
        btn_row = QHBoxLayout()

        help_btn = QPushButton("Help")
        help_btn.setObjectName("help_btn")
        help_btn.setFont(_load_pixel_font(6))
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(lambda: webbrowser.open(COOKIE_HELP_URL))
        btn_row.addWidget(help_btn)

        btn_row.addStretch()

        save_btn = QPushButton("SAVE")
        save_btn.setFont(_load_pixel_font(7))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

        # Status label
        self._status = QLabel("")
        self._status.setFont(_load_pixel_font(5))
        self._status.setStyleSheet("color: #c85977;")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        root.addWidget(content)

    # ── Drag to move ──────────────────────────────────────────────────────────

    def _title_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _title_mouse_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    # ── Load / Save ───────────────────────────────────────────────────────────

    def _load_existing(self):
        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
            cfg = settings.get("espn", {})
            if cfg.get("league_id"):
                self._league_id.setText(str(cfg["league_id"]))
            if cfg.get("espn_s2"):
                self._espn_s2.setText(cfg["espn_s2"])
            if cfg.get("swid"):
                self._swid.setText(cfg["swid"])
        except Exception as e:
            print(f"[SetupDialog] Failed to load existing settings: {e}")

    def _save(self):
        league_id = self._league_id.text().strip()
        espn_s2   = self._espn_s2.text().strip()
        swid      = self._swid.text().strip()

        if not all([league_id, espn_s2, swid]):
            self._status.setStyleSheet("color: #c85977;")
            self._status.setText("All fields are required.")
            return

        self._status.setStyleSheet("color: #a6e3a1;")
        self._status.setText("Connecting to ESPN...")

        try:
            from espn_api.basketball import League
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
            League(
                league_id=int(league_id),
                year=settings["espn"]["year"],
                espn_s2=espn_s2,
                swid=swid
            )
        except Exception as e:
            self._status.setStyleSheet("color: #c85977;")
            self._status.setText(f"Connection failed: {e}")
            return

        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
            settings["espn"]["league_id"] = int(league_id)
            settings["espn"]["espn_s2"]   = espn_s2
            settings["espn"]["swid"]      = swid
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            self._status.setStyleSheet("color: #c85977;")
            self._status.setText(f"Could not save: {e}")
            return

        self._status.setStyleSheet("color: #a6e3a1;")
        self._status.setText("Connected!")
        self.accept()


# ── Startup check ─────────────────────────────────────────────────────────────

def check_and_run_setup():
    try:
        with open(SETTINGS_PATH) as f:
            settings = json.load(f)
        cfg = settings.get("espn", {})
        has_creds = all([
            cfg.get("league_id"),
            cfg.get("espn_s2"),
            cfg.get("swid"),
            cfg.get("my_team_id")
        ])
        if has_creds:
            return True
    except Exception as e:
        print(f"[Setup] Failed to check credentials: {e}")

    dialog = SetupDialog()
    result = dialog.exec()
    return result == QDialog.DialogCode.Accepted


# needed so QWidget reference works in title bar
from PyQt6.QtWidgets import QWidget