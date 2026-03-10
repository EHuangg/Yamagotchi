import json
import os
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.json')

COOKIE_HELP_URL = "https://github.com/cwendt94/espn-api/discussions/150"

class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fantasy Pet — First Time Setup")
        self.setFixedSize(200, 260)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; }
            QLabel  { color: #cdd6f4; font-size: 14px; }
            QLineEdit {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 1px;
                font-size: 12px;
            }
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                border-radius: 6px;
                padding: 1px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #b4d0ff; }
            QPushButton#help_btn {
                background-color: transparent;
                color: #89b4fa;
                text-decoration: underline;
                padding: 0;
                font-size: 13px;
            }
        """)
        self._build_ui()
        self._load_existing()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4)                     
        layout.setContentsMargins(16, 12, 16, 12) # window border argins

        title = QLabel("SETUP")
        title.setStyleSheet("color: #cdd6f4; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # League ID
        layout.addWidget(QLabel("League ID"))
        self._league_id = QLineEdit()
        self._league_id.setPlaceholderText("000000000")
        layout.addWidget(self._league_id)

        # espn_s2
        layout.addWidget(QLabel("espn_s2 cookie"))
        self._espn_s2 = QLineEdit()
        self._espn_s2.setPlaceholderText("Long string from browser cookies")
        self._espn_s2.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._espn_s2)

        # SWID
        layout.addWidget(QLabel("SWID cookie"))
        self._swid = QLineEdit()
        self._swid.setPlaceholderText("{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}")
        layout.addWidget(self._swid)

        # Help link + Save button
        btn_row = QHBoxLayout()

        help_btn = QPushButton("Help")
        help_btn.setObjectName("help_btn")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.clicked.connect(lambda: webbrowser.open(COOKIE_HELP_URL))
        btn_row.addWidget(help_btn)

        btn_row.addStretch()

        save_btn = QPushButton("SAVE")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

        # Status label
        self._status = QLabel("")
        self._status.setStyleSheet("color: #f38ba8; font-size: 11px;")
        layout.addWidget(self._status)

    def _load_existing(self):
        """Pre-fill fields if partial credentials already exist."""
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
        except Exception:
            pass

    def _save(self):
        league_id = self._league_id.text().strip()
        espn_s2   = self._espn_s2.text().strip()
        swid      = self._swid.text().strip()

        if not all([league_id, espn_s2, swid]):
            self._status.setText("⚠ All fields are required.")
            return

        self._status.setStyleSheet("color: #a6e3a1; font-size: 11px;")
        self._status.setText("Connecting to ESPN...")

        # Test the connection before saving
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
            self._status.setStyleSheet("color: #f38ba8; font-size: 11px;")
            self._status.setText(f"Connection failed: {e}")
            return

        # Save to settings.json
        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
            settings["espn"]["league_id"] = int(league_id)
            settings["espn"]["espn_s2"]   = espn_s2
            settings["espn"]["swid"]      = swid
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            self._status.setStyleSheet("color: #f38ba8; font-size: 11px;")
            self._status.setText(f"Could not save settings: {e}")
            return

        self._status.setText("YIPPEE we Connected frfr")
        self.accept()


def check_and_run_setup():
    """
    Call this at startup. Returns True if credentials are present,
    False if user cancelled setup.
    """
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
    except Exception:
        pass

    # Show setup dialog
    dialog = SetupDialog()
    result = dialog.exec()
    return result == QDialog.DialogCode.Accepted