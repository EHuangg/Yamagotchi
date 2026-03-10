import webbrowser
from PyQt6.QtGui import QIcon, QPainter, QAction, QIcon
from PyQt6.QtWidgets import QMainWindow, QMenu, QWidget
from PyQt6.QtCore import Qt, QPoint, QEvent
from ui.roster_view import RosterView
from api.espn_client import ESPNClient
from api.team_cache import TeamCache
from events.event_bus import event_bus
import json
import os

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.json')

class DesktopWidget(QMainWindow):
    def __init__(self, players=None):
        super().__init__()
        # init icon 
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), '..', 'assets', 'icon.ico')))
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._live_data_cache = {}
        self._drag_start_global = QPoint()
        self._drag_start_pos = QPoint()
        self._dragging = False
        self._current_team_id = self._load_last_team_id()
        self._team_cache = None

        self._load_position()

        self.roster_view = RosterView(players or [])
        self.setCentralWidget(self.roster_view)
        self._resize_to_roster(len(players) if players else 0)
        self._install_filter_recursive(self.roster_view)

        from ui.matchup_panel import MatchupPanel
        self.matchup_panel = MatchupPanel()

    def _install_filter_recursive(self, widget):
        widget.installEventFilter(self)
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_start_global = event.globalPosition().toPoint()
                self._drag_start_pos = self.pos()
                self._dragging = True
                return False

        elif event.type() == QEvent.Type.MouseMove:
            if self._dragging and event.buttons() == Qt.MouseButton.LeftButton:
                delta = event.globalPosition().toPoint() - self._drag_start_global
                if delta.manhattanLength() > 3:
                    self.move(self._drag_start_pos + delta)
                return False

        elif event.type() == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                if self._dragging:
                    self._dragging = False
                    self._save_position()
                return False

        return super().eventFilter(obj, event)

    def _resize_to_roster(self, count: int):
        width = max(400, count * 90 + 20)
        self.setFixedSize(width, 140)

    def _load_position(self):
        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
            self.move(settings["window"]["x"], settings["window"]["y"])
        except Exception:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.x() + 100, screen.bottom() - 180)

    def _save_position(self):
        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
            settings["window"]["x"] = self.x()
            settings["window"]["y"] = self.y()
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Could not save position: {e}")

    def _load_last_team_id(self) -> int:
        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
            return settings["espn"].get("last_viewed_team_id", 1)
        except Exception:
            return 1

    def _save_last_team_id(self, team_id: int):
        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
            settings["espn"]["last_viewed_team_id"] = team_id
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Could not save team id: {e}")

    def set_team_cache(self, cache):
        self._team_cache = cache
        self.matchup_panel.show_panel(self)
        self.matchup_panel._team_cycle_cb = self._cycle_team
        self._switch_to_team(self._current_team_id)

    def _cycle_team(self, direction: str):
        if direction == 'prev':
            self._prev_team()
        else:
            self._next_team()

    def _switch_to_team(self, team_id: int):
        if not self._team_cache:
            return
        data = self._team_cache.get_team(team_id)
        if not data:
            return

        self._current_team_id = team_id
        self.roster_view._starter_players = data['snapshot']
        self.roster_view._full_players = data.get('full_snapshot', data['snapshot'])
        self.roster_view.refresh_roster(data['snapshot'])
        self._resize_to_roster(len(data['snapshot']))
        self._install_filter_recursive(self.roster_view)


        for player in data['snapshot']:
            card = self.roster_view.get_card(player.player_id)
            if card:
                card.set_season_avg(player.projected_points)
                if player.name in self._live_data_cache:
                    card.set_live_data(self._live_data_cache[player.name])

        event_bus.matchup_updated.emit(data['matchup'])
        self._save_last_team_id(team_id)

    def _prev_team(self):
        if self._team_cache:
            self._switch_to_team(self._team_cache.prev_team_id(self._current_team_id))

    def _next_team(self):
        if self._team_cache:
            self._switch_to_team(self._team_cache.next_team_id(self._current_team_id))

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, 'matchup_panel'):
            self.matchup_panel.update_position(self)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.end()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 4px;
                font-size: 12px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #313244;
            }
            QMenu::separator {
                height: 1px;
                background: #45475a;
                margin: 4px 8px;
            }
        """)

        toggle_action = QAction(
            "Show Full Roster" if not self.roster_view._show_full_roster
            else "Show Starters Only",
            self
        )
        toggle_action.triggered.connect(self.roster_view.toggle_roster_size)
        menu.addAction(toggle_action)

        open_action = QAction("Open League in Browser", self)
        open_action.triggered.connect(self._open_league)
        menu.addAction(open_action)

        menu.addSeparator()

        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self._request_refresh)
        menu.addAction(refresh_action)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        menu.exec(event.globalPos())

    def _open_league(self):
        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
            league_id = settings["espn"]["league_id"]
            webbrowser.open(f"https://fantasy.espn.com/basketball/league?leagueId={league_id}")
        except Exception:
            webbrowser.open("https://fantasy.espn.com")

    def _request_refresh(self):
        event_bus.force_refresh.emit()

    def _open_settings(self):
        from ui.setup_dialog import SetupDialog
        dialog = SetupDialog(self)
        if dialog.exec() == SetupDialog.DialogCode.Accepted:
            event_bus.force_refresh.emit()
            self._reload_roster()

    def _reload_roster(self):
        try:
            new_client = ESPNClient()
            new_client.connect()
            all_teams_data = new_client.get_all_teams_data()
            new_team_cache = TeamCache(all_teams_data)

            self.espn_client = new_client
            self.team_cache = new_team_cache
            self._team_cache = new_team_cache
            self.poller.client = new_client

            all_roster_names = []
            for tid in new_team_cache.all_team_ids:
                td = new_team_cache.get_team(tid)
                all_roster_names.extend([p.name for p in td.get('snapshot', [])])
            all_roster_names = list(set(all_roster_names))
            self.live_poller.update_roster_names(all_roster_names)
            self.live_poller.client.scoring = new_client.get_scoring_settings()

            self._switch_to_team(self._current_team_id)
            event_bus.force_refresh.emit()
            print(f"[Settings] Reloaded — {len(all_teams_data)} teams, {len(all_roster_names)} players tracked")

        except Exception as e:
            print(f"[Settings] Reload failed: {e}")

    def _quit(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()