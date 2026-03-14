import json
import webbrowser
import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox, QWidget
)
from PyQt6.QtCore import Qt, QTimer
from config_utils import SETTINGS_PATH
ESPN_FANTASY_URL = "https://www.espn.com/fantasy/basketball/"

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fantasy Pet — ESPN Login")
        self.setFixedSize(480, 320)
        self.setStyleSheet("background-color: #D8E2F0;")

        self._espn_s2 = None
        self._swid = None
        self._leagues = []
        self._polling = False

        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_for_cookies)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("ESPN Login")
        title.setStyleSheet("color: #000A14; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        instructions = QLabel(
            "1. Click the button below to open ESPN in your browser\n"
            "2. Log in to your ESPN account\n"
            "3. Return here — we'll detect your login automatically"
        )
        instructions.setStyleSheet("color: #000A14; font-size: 12px; line-height: 1.6;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        open_btn = QPushButton("Open ESPN in Browser →")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #cc0000;
                color: white;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #ee0000; }
        """)
        open_btn.clicked.connect(self._open_browser)
        layout.addWidget(open_btn)

        # DEBUG — remove later
        debug_btn = QPushButton("Debug: Check Cookies Now")
        debug_btn.setStyleSheet("""
            QPushButton {
                background-color: #929EAF;
                color: #000A14;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #A7C2E5; }
        """)
        debug_btn.clicked.connect(self._debug_cookies)
        layout.addWidget(debug_btn)

        self._status_label = QLabel("Waiting for login...")
        self._status_label.setStyleSheet("color: #000A14; font-size: 12px;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        # League picker — hidden until cookies found
        self._league_bar = QWidget()
        league_layout = QHBoxLayout(self._league_bar)
        league_layout.setContentsMargins(0, 0, 0, 0)

        league_label = QLabel("League:")
        league_label.setStyleSheet("color: #000A14; font-size: 12px;")
        league_layout.addWidget(league_label)

        self._league_combo = QComboBox()
        self._league_combo.setStyleSheet("""
            QComboBox {
                background-color: #D8E2F0;
                color: #000A14;
                border: 1px solid #929EAF;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #D8E2F0;
                color: #000A14;
                selection-background-color: #A7C2E5;
            }
        """)
        league_layout.addWidget(self._league_combo, stretch=1)
        self._league_bar.hide()
        layout.addWidget(self._league_bar)

        self._continue_btn = QPushButton("Save & Continue")
        self._continue_btn.setEnabled(False)
        self._continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._continue_btn.setStyleSheet("""
            QPushButton {
                background-color: #A7C2E5;
                color: #000A14;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:disabled {
                background-color: #929EAF;
                color: #D8E2F0;
            }
            QPushButton:hover:enabled { background-color: #D8E2F0; }
        """)
        self._continue_btn.clicked.connect(self._on_continue)
        layout.addWidget(self._continue_btn)

    def _get_chrome_cookies(self) -> tuple[str, str]:
        import sqlite3, shutil, tempfile, os, json, base64
        try:
            from Crypto.Cipher import AES
            import win32crypt
        except ImportError:
            print("[Login] Missing dependencies — run: pip install pywin32 pycryptodome")
            return None, None

        try:
            # Get Chrome encryption key
            local_state_path = os.path.expanduser(
                r'~\AppData\Local\Google\Chrome\User Data\Local State'
            )
            with open(local_state_path, 'r', encoding='utf-8') as f:
                local_state = json.load(f)

            encrypted_key = base64.b64decode(
                local_state['os_crypt']['encrypted_key']
            )
            # Remove DPAPI prefix
            encrypted_key = encrypted_key[5:]
            key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

            # Copy cookie DB using Windows shadow copy to bypass lock
            cookie_path = os.path.expanduser(
                r'~\AppData\Local\Google\Chrome\User Data\Default\Network\Cookies'
            )
            tmp = os.path.join(tempfile.gettempdir(), 'chrome_cookies_tmp')

            # Use subprocess to copy with shadow access
            import subprocess
            subprocess.run(
                ['cmd', '/c', f'copy /Y "{cookie_path}" "{tmp}"'],
                capture_output=True
            )
            shutil.copy2(cookie_path, tmp)

            conn = sqlite3.connect(tmp)
            cur = conn.cursor()
            cur.execute(
                "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%espn%'"
            )

            espn_s2 = None
            swid = None

            for name, encrypted_value in cur.fetchall():
                value = None
                try:
                    # Chrome v80+ AES-256-GCM encryption
                    iv = encrypted_value[3:15]
                    payload = encrypted_value[15:]
                    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
                    value = cipher.decrypt(payload)[:-16].decode('utf-8')
                except Exception as e1:
                    try:
                        value = win32crypt.CryptUnprotectData(
                            encrypted_value, None, None, None, 0
                        )[1].decode('utf-8')
                    except Exception as e2:
                        print(f"[Login] Failed to decrypt: {e1}, {e2}")
                        continue

                if value:
                    if name == 'espn_s2':
                        espn_s2 = value
                    elif name == 'SWID':
                        swid = value

            conn.close()
            os.remove(tmp)
            return espn_s2, swid

        except Exception as e:
            print(f"[Login] Chrome read failed: {e}")
            return None, None

    def _debug_cookies(self):
        espn_s2, swid = self._get_chrome_cookies()
        print(f"[Chrome] espn_s2: {espn_s2[:20] if espn_s2 else 'NOT FOUND'}")
        print(f"[Chrome] SWID: {swid[:20] if swid else 'NOT FOUND'}")

    def _open_browser(self):
        webbrowser.open(ESPN_FANTASY_URL)
        self._status_label.setText("⏳ Waiting for login... (checking every 3 seconds)")
        self._status_label.setStyleSheet("color: #000A14; font-size: 12px;")
        self._poll_timer.start(3000)

    def _poll_for_cookies(self):
        try:
            espn_s2, swid = self._get_chrome_cookies()
            if espn_s2 and swid:
                self._poll_timer.stop()
                self._espn_s2 = espn_s2
                self._swid = swid
                self._status_label.setText("✓ Login detected! Fetching your leagues...")
                self._status_label.setStyleSheet("color: #a6e3a1; font-size: 12px;")
                self._fetch_leagues()
        except Exception as e:
            print(f"[Login] Cookie poll failed: {e}")
        
    def _on_continue(self):
        if not self._espn_s2 or not self._swid:
            self._status_label.setText("⚠ Not logged in yet.")
            self._status_label.setStyleSheet("color: #c85977; font-size: 12px;")
            return

        league_id = self._league_combo.currentData() if self._leagues else None

        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
            settings["espn"]["espn_s2"] = self._espn_s2
            settings["espn"]["swid"]    = self._swid
            if league_id:
                settings["espn"]["league_id"] = int(league_id)
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"[Login] Could not save: {e}")
            return

        self._poll_timer.stop()
        self.accept()

def check_and_run_setup() -> bool:
    try:
        with open(SETTINGS_PATH) as f:
            settings = json.load(f)
        cfg = settings.get("espn", {})
        if all([cfg.get("league_id"), cfg.get("espn_s2"), cfg.get("swid")]):
            return True
    except Exception as e:
        print(f"[Login] Failed to check credentials: {e}")

    dialog = LoginDialog()
    return dialog.exec() == QDialog.DialogCode.Accepted