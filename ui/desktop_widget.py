import os
import json
import webbrowser
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QLabel, QMenu, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QAction, QFontDatabase, QFont

from ui.player_card import PlayerCard
from ui.appbar import AppBar
from config_utils import SETTINGS_PATH
from events.event_bus import event_bus

BAR_THICKNESS = 100


def _load_pixel_font(size: int = 8) -> QFont:
    font_id = QFontDatabase.addApplicationFont(
        os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts', 'pixel.ttf')
    )
    families = QFontDatabase.applicationFontFamilies(font_id)
    return QFont(families[0], size) if families else QFont("Courier", size)


class ClickableLabel(QLabel):
    def __init__(self, text='', on_click=None, hover_color='#A7C2E5',
                 default_color='#929EAF', selected_color='#D8E2F0'):
        super().__init__(text)
        self._on_click = on_click
        self._hover_color = hover_color
        self._default_color = default_color
        self._selected_color = selected_color
        self._selected = False
        self._base_style = ""
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setStyleSheet(self, style: str):
        self._base_style = style
        super().setStyleSheet(style)

    def set_selected(self, selected: bool, base_style: str = ""):
        self._selected = selected
        self._base_style = base_style
        color = self._selected_color if selected else self._default_color
        super().setStyleSheet(f"color: {color}; {base_style}")

    def update_colors(self, hover_color: str, default_color: str, selected_color: str):
        self._hover_color = hover_color
        self._default_color = default_color
        self._selected_color = selected_color
        self.set_selected(self._selected, self._base_style)

    def enterEvent(self, event):
        super().setStyleSheet(f"color: {self._hover_color}; {self._base_style}")

    def leaveEvent(self, event):
        color = self._selected_color if self._selected else self._default_color
        super().setStyleSheet(f"color: {color}; {self._base_style}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._on_click:
            self._on_click()

    def set_siblings(self, siblings: list):
        self._siblings = siblings

    def enterEvent(self, event):
        super().setStyleSheet(f"color: {self._hover_color}; {self._base_style}")
        for s in getattr(self, '_siblings', []):
            super(ClickableLabel, s).setStyleSheet(f"color: {s._hover_color}; {s._base_style}")

    def leaveEvent(self, event):
        color = self._selected_color if self._selected else self._default_color
        super().setStyleSheet(f"color: {color}; {self._base_style}")
        for s in getattr(self, '_siblings', []):
            s_color = s._selected_color if s._selected else s._default_color
            super(ClickableLabel, s).setStyleSheet(f"color: {s_color}; {s._base_style}")

class _RotatedDivider(QWidget):
    def __init__(self, text: str):
        super().__init__()
        self._text = f"——— {text} ———"
        self.setFixedWidth(24)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(-90)
        painter.translate(-self.height() / 2, -self.width() / 2)
        painter.setPen(QColor("#000A14"))
        painter.setFont(_load_pixel_font(5))
        painter.drawText(0, 0, self.height(), self.width(),
                         Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()

class DesktopWidget(QMainWindow):
    def __init__(self, players=None):
        super().__init__()
        self.setWindowIcon(QIcon(
            os.path.join(os.path.dirname(__file__), '..', 'assets', 'icon.ico')
        ))
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._live_data_cache = {}
        self._current_team_id = self._load_last_team_id()
        self._current_matchup_idx = 0
        self._current_matchup_data = {}
        self._team_cache = None
        self._edge = self._load_edge()
        self._players = []

        self._build_ui(players or [])

        self._appbar = None
        QTimer.singleShot(100, self._register_appbar)

        event_bus.matchup_updated.connect(self._on_matchup_updated)

    def _is_horizontal(self) -> bool:
        return self._edge in ('top', 'bottom')

    def _build_ui(self, players: list):
        self._players = players

        central = QWidget()
        central.setStyleSheet("background-color: #D8E2F0;")
        self.setCentralWidget(central)

        if self._is_horizontal():
            self._main_layout = QHBoxLayout(central)
        else:
            self._main_layout = QVBoxLayout(central)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # ── Scoreboard ────────────────────────────────────────────────────────
        self._score_widget = QWidget()
        self._score_widget.setStyleSheet(
            "background-color: #A7C2E5; border: none;"
        )
        if self._is_horizontal():
            self._score_widget.setFixedWidth(110)
        else:
            self._score_widget.setFixedHeight(110)

        score_layout = QVBoxLayout(self._score_widget)
        score_layout.setContentsMargins(8, 8, 8, 8)
        score_layout.setSpacing(2)

        self._team_name_label = ClickableLabel("—", on_click=self._click_my_team,
            hover_color='#A7C2E5', default_color='#000A14', selected_color='#000A14')
        self._team_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._team_name_label.setWordWrap(True)
        self._team_name_label.setFont(_load_pixel_font(6))
        self._team_name_label.setStyleSheet("color: #000A14;")

        self._my_score_label = ClickableLabel("—", on_click=self._click_my_team,
            hover_color='#A7C2E5', default_color='#000A14', selected_color='#000A14')
        self._my_score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._my_score_label.setFont(_load_pixel_font(10))
        self._my_score_label.setStyleSheet("color: #000A14;")

        self._opp_score_label = ClickableLabel("—", on_click=self._click_opp_team,
            hover_color='#A7C2E5', default_color='#000A14', selected_color='#000A14')
        self._opp_score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._opp_score_label.setFont(_load_pixel_font(10))
        self._opp_score_label.setStyleSheet("color: #000A14;")

        self._opp_name_label = ClickableLabel("—", on_click=self._click_opp_team,
            hover_color='#A7C2E5', default_color='#000A14', selected_color='#000A14')
        self._opp_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._opp_name_label.setWordWrap(True)
        self._opp_name_label.setFont(_load_pixel_font(6))
        self._opp_name_label.setStyleSheet("color: #000A14;")
        
        self._team_name_label.set_siblings([self._my_score_label])
        self._my_score_label.set_siblings([self._team_name_label])

        self._opp_name_label.set_siblings([self._opp_score_label])
        self._opp_score_label.set_siblings([self._opp_name_label])

        score_layout.addWidget(self._team_name_label)
        score_layout.addWidget(self._my_score_label)
        score_layout.addWidget(self._opp_score_label)
        score_layout.addWidget(self._opp_name_label)

        self._main_layout.addWidget(self._score_widget)

        # ── Scrollable player list ────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        if self._is_horizontal():
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setStyleSheet("""
                QScrollArea { border: none; background: transparent; }
                QScrollBar:horizontal {
                    background: #A7C2E5;
                    height: 4px;
                    border-radius: 2px;
                }
                QScrollBar::handle:horizontal {
                    background: #A7C2E5;
                    border-radius: 2px;
                    min-width: 20px;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            """)
        else:
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setStyleSheet("""
                QScrollArea { border: none; background: transparent; }
                QScrollBar:vertical {
                    background: #A7C2E5;
                    width: 4px;
                    border-radius: 2px;
                }
                QScrollBar::handle:vertical {
                    background: #A7C2E5;
                    border-radius: 2px;
                    min-height: 20px;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            """)

        self._players_widget = QWidget()
        self._players_widget.setStyleSheet("background: transparent;")

        if self._is_horizontal():
            self._players_layout = QHBoxLayout(self._players_widget)
            self._players_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        else:
            self._players_layout = QVBoxLayout(self._players_widget)
            self._players_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._players_layout.setContentsMargins(0, 0, 0, 0)
        self._players_layout.setSpacing(2)

        scroll.setWidget(self._players_widget)
        self._main_layout.addWidget(scroll)

        # ── Nav buttons ───────────────────────────────────────────────────────
        nav_widget = QWidget()
        nav_widget.setStyleSheet("background: #A7C2E5; border: none;")

        if self._is_horizontal():
            nav_widget.setFixedWidth(28)
            nav_layout = QVBoxLayout(nav_widget)
            nav_layout.setContentsMargins(0, 0, 0, 0)
            nav_layout.setSpacing(0)
            prev_btn = ClickableLabel("▲", on_click=lambda: self._cycle_matchup('prev'))
            next_btn = ClickableLabel("▼", on_click=lambda: self._cycle_matchup('next'))
            prev_btn.setFixedSize(28, 40)
            next_btn.setFixedSize(28, 40)
        else:
            nav_widget.setFixedHeight(28)
            nav_layout = QHBoxLayout(nav_widget)
            nav_layout.setContentsMargins(0, 0, 0, 0)
            nav_layout.setSpacing(0)
            prev_btn = ClickableLabel("◀", on_click=lambda: self._cycle_matchup('prev'))
            next_btn = ClickableLabel("▶", on_click=lambda: self._cycle_matchup('next'))
            prev_btn.setFixedSize(40, 28)
            next_btn.setFixedSize(40, 28)

        for btn in (prev_btn, next_btn):
            btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn.setFont(_load_pixel_font(8))
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet("color: #000A14; font-weight: bold; background: transparent; border: none;")

        self._matchup_counter_label = QLabel("—/—")
        self._matchup_counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._matchup_counter_label.setFont(_load_pixel_font(6))
        self._matchup_counter_label.setStyleSheet("color: #000A14; background: transparent;")

        nav_layout.addWidget(prev_btn)
        nav_layout.addWidget(self._matchup_counter_label)
        nav_layout.addWidget(next_btn)

        self._main_layout.addWidget(nav_widget)

        # ── Cards ─────────────────────────────────────────────────────────────
        self._cards: dict[int, PlayerCard] = {}

        from ui.roster_view_shim import RosterViewShim
        self.roster_view = RosterViewShim(self._cards)

        self._build_player_rows(players)

    def _build_player_rows(self, players: list):
        for i in reversed(range(self._players_layout.count())):
            w = self._players_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        self._cards.clear()

        BENCH_SLOTS = {'BE', 'BN'}
        IR_SLOTS    = {'IR'}

        shown_bench = False
        shown_ir    = False

        for player in players:
            slot = getattr(player, 'lineup_slot', '')

            if not shown_bench and slot in BENCH_SLOTS:
                self._players_layout.addWidget(self._make_divider("Bench"))
                shown_bench = True

            if not shown_ir and slot in IR_SLOTS:
                self._players_layout.addWidget(self._make_divider("IR"))
                shown_ir = True

            row = self._make_player_row(player)
            self._players_layout.addWidget(row)
            
        if hasattr(self, 'roster_view') and hasattr(self.roster_view, '_trigger'):
            self.roster_view._trigger.reset_initialized()
            
    def _make_player_row(self, player) -> QWidget:
        row = QWidget()
        if self._is_horizontal():
            row.setFixedWidth(BAR_THICKNESS)
        else:
            row.setFixedHeight(BAR_THICKNESS)

        if self._is_horizontal():
            layout = QVBoxLayout(row)
        else:
            layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        card = PlayerCard(
            player_name=player.name,
            position=player.position,
            points=player.points_this_week,
            nba_team=getattr(player, 'nba_team', ''),
            injury_status=getattr(player, 'injury_status', ''),
        )
        card.setFixedSize(90, 94)
        card._refresh_display()  # apply injury tag immediately
        layout.addWidget(card)

        self._cards[player.player_id] = card
        return row

    def _make_divider(self, text: str) -> QWidget:
        if self._is_horizontal():
            return _RotatedDivider(text)
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container.setFixedHeight(24)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        left_line  = QLabel("———")
        label      = QLabel(text)
        right_line = QLabel("———")

        for w in (left_line, label, right_line):
            w.setFont(_load_pixel_font(5))
            w.setStyleSheet("color: #000A14; background: transparent;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(left_line)
        layout.addWidget(label)
        layout.addWidget(right_line)
        return container

    # ── AppBar ────────────────────────────────────────────────────────────────

    def _register_appbar(self):
        hwnd = int(self.winId())
        screens = QApplication.screens()
        try:
            with open(SETTINGS_PATH) as f:
                idx = json.load(f).get('monitor', 0)
            screen = screens[idx] if idx < len(screens) else screens[0]
        except Exception as e:
            print(f"[DesktopWidget] Failed to load monitor index: {e}")
            screen = screens[0]
        self._appbar = AppBar(hwnd, BAR_THICKNESS)
        self._appbar.register(self._edge, screen=screen.geometry())

    def _set_edge(self, edge: str):
        old_horizontal = self._is_horizontal()
        self._edge = edge
        self._save_edge(edge)

        if old_horizontal != self._is_horizontal():
            players = list(self._players)
            self._build_ui(players)
            for player in players:
                card = self._cards.get(player.player_id)
                if card and player.name in self._live_data_cache:
                    card.set_live_data(self._live_data_cache[player.name])
            if self._current_matchup_data:
                self._on_matchup_updated(self._current_matchup_data)
            self._update_nav_counter()

        if self._appbar:
            self._appbar.set_edge(edge)

    # ── Scoreboard ────────────────────────────────────────────────────────────

    def _on_matchup_updated(self, data: dict):
        if not data:
            self._team_name_label.setText("—")
            self._my_score_label.setText("—")
            self._opp_score_label.setText("—")
            self._opp_name_label.setText("BYE")
            self._current_matchup_data = {}
            return

        self._current_matchup_data = data
        my_team   = data.get('my_team',   '—')
        my_score  = data.get('my_score',  0.0)
        opp_score = data.get('opp_score', 0.0)
        opp_name  = data.get('opp_team',  '?')
        winning   = my_score >= opp_score

        my_selected  = self._current_team_id == data.get('my_team_id')
        opp_selected = self._current_team_id == data.get('opp_team_id')

        win_color  = '#a6e3a1'
        lose_color = '#c85977'

        self._team_name_label.setText(my_team)
        my_team_color = win_color if winning else lose_color
        self._team_name_label.update_colors(hover_color=my_team_color,
            default_color='#000A14', selected_color=my_team_color)
        self._team_name_label.set_selected(my_selected, "")

        my_score_color = win_color if winning else lose_color
        self._my_score_label.setText(f"{my_score:.1f}")
        if my_selected:
            self._my_score_label.setFont(_load_pixel_font(10))
            self._my_score_label.update_colors(hover_color=my_score_color,
                default_color=my_score_color, selected_color=my_score_color)
            self._my_score_label.set_selected(my_selected, "font-weight: bold;")
        else:
            self._my_score_label.setFont(_load_pixel_font(9))
            self._my_score_label.update_colors(hover_color=my_score_color,
                default_color='#000A14', selected_color='#000A14')
            self._my_score_label.set_selected(my_selected, "")

        opp_score_color = lose_color if winning else win_color
        self._opp_score_label.setText(f"{opp_score:.1f}")
        if opp_selected:
            self._opp_score_label.setFont(_load_pixel_font(10))
            self._opp_score_label.update_colors(hover_color=opp_score_color,
                default_color=opp_score_color, selected_color=opp_score_color)
            self._opp_score_label.set_selected(opp_selected, "font-weight: bold;")
        else:
            self._opp_score_label.setFont(_load_pixel_font(9))
            self._opp_score_label.update_colors(hover_color=opp_score_color,
                default_color='#000A14', selected_color='#000A14')
            self._opp_score_label.set_selected(opp_selected, "")

        self._opp_name_label.setText(opp_name)
        opp_team_color = lose_color if winning else win_color
        self._opp_name_label.update_colors(hover_color=opp_team_color,
            default_color='#000A14', selected_color=opp_team_color)
        self._opp_name_label.set_selected(opp_selected, "")

    def _click_my_team(self):
        team_id = self._current_matchup_data.get('my_team_id')
        if team_id:
            self._switch_to_team(team_id)

    def _click_opp_team(self):
        team_id = self._current_matchup_data.get('opp_team_id')
        if team_id:
            self._switch_to_team(team_id)

    # ── Team / Matchup cycling ────────────────────────────────────────────────

    def set_team_cache(self, cache):
        self._team_cache = cache
        self._current_matchup_idx = 0
        selected_matchup = None

        for i in range(cache.matchup_count()):
            m = cache.get_matchup(i)
            if m.get('my_team_id') == self._current_team_id:
                self._current_matchup_idx = i
                selected_matchup = m
                break
            elif m.get('opp_team_id') == self._current_team_id:
                self._current_matchup_idx = i
                selected_matchup = {
                    'my_team':     m['opp_team'],
                    'my_score':    m['opp_score'],
                    'my_team_id':  m['opp_team_id'],
                    'opp_team':    m['my_team'],
                    'opp_score':   m['my_score'],
                    'opp_team_id': m['my_team_id'],
                }
                break

        self._current_matchup_idx = min(
            self._current_matchup_idx,
            max(0, cache.matchup_count() - 1)
        )

        if selected_matchup is None:
            selected_matchup = cache.get_matchup(0)

        self._current_matchup_data = selected_matchup
        event_bus.matchup_updated.emit(selected_matchup)
        self._switch_to_team(self._current_team_id)
        self._update_nav_counter()

    def _switch_to_team(self, team_id: int, force_rebuild: bool = False):
        if not self._team_cache:
            return
        data = self._team_cache.get_team(team_id)
        if not data:
            return

        old_players = list(self._players)
        self._current_team_id = team_id
        players = data['full_snapshot']
        self._players = players

        old_player_ids = [p.player_id for p in old_players]
        new_player_ids = [p.player_id for p in players]
        old_player_id_set = set(old_player_ids)
        new_player_id_set = set(new_player_ids)

        old_slot_by_id = {p.player_id: getattr(p, 'lineup_slot', '') for p in old_players}
        new_slot_by_id = {p.player_id: getattr(p, 'lineup_slot', '') for p in players}
        old_avg_by_id = {p.player_id: getattr(p, 'projected_points', 0.0) for p in old_players}
        new_avg_by_id = {p.player_id: getattr(p, 'projected_points', 0.0) for p in players}
        old_injury_by_id = {p.player_id: getattr(p, 'injury_status', '') for p in old_players}
        new_injury_by_id = {p.player_id: getattr(p, 'injury_status', '') for p in players}
        moved_player_ids = {
            pid for pid in (old_player_id_set & new_player_id_set)
            if old_slot_by_id.get(pid) != new_slot_by_id.get(pid)
        }

        order_changed = old_player_ids != new_player_ids
        slots_changed = any(old_slot_by_id.get(pid) != new_slot_by_id.get(pid) for pid in new_player_id_set)
        roster_changed = old_player_id_set != new_player_id_set or order_changed or slots_changed

        if force_rebuild or roster_changed:
            self._build_player_rows(players)

        changed_player_ids = {
            pid for pid in (old_player_id_set & new_player_id_set)
            if (
                old_avg_by_id.get(pid) != new_avg_by_id.get(pid)
                or old_injury_by_id.get(pid) != new_injury_by_id.get(pid)
                or pid in moved_player_ids
            )
        }

        for player in players:
            card = self._cards.get(player.player_id)
            if card:
                card.set_season_avg(player.projected_points)
                if player.name in self._live_data_cache:
                    card.set_live_data(self._live_data_cache[player.name])
                elif player.player_id in changed_player_ids:
                    card._refresh_display()  # force display update even without live data

        for pid in moved_player_ids:
            card = self._cards.get(pid)
            if card:
                card.flash_position_change_indicator()

        self._save_last_team_id(team_id)
        if self._current_matchup_data:
            self._on_matchup_updated(self._current_matchup_data)

    def _update_nav_counter(self):
        if self._team_cache:
            total = self._team_cache.matchup_count()
            self._matchup_counter_label.setText(
                f"{self._current_matchup_idx + 1}/{total}"
            )

    def _cycle_matchup(self, direction: str):
        if not self._team_cache:
            return
        count = self._team_cache.matchup_count()
        if count == 0:
            return
        if direction == 'next':
            self._current_matchup_idx = (self._current_matchup_idx + 1) % count
        else:
            self._current_matchup_idx = (self._current_matchup_idx - 1) % count

        matchup = self._team_cache.get_matchup(self._current_matchup_idx)
        self._current_matchup_data = matchup or {}
        event_bus.matchup_updated.emit(matchup)
        my_team_id = matchup.get('my_team_id')
        if my_team_id:
            self._switch_to_team(my_team_id)
        self._update_nav_counter()

    # ── Context menu ──────────────────────────────────────────────────────────

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #D8E2F0;
                color: #000A14;
                border: 1px solid #929EAF;
                border-radius: 8px;
                padding: 4px;
                font-size: 12px;
            }
            QMenu::item { padding: 6px 20px; border-radius: 4px; }
            QMenu::item:selected { background-color: #A7C2E5; }
            QMenu::separator { height: 1px; background: #929EAF; margin: 4px 8px; }
        """)

        collapse_action = QAction("Hide", self)
        collapse_action.triggered.connect(self._hide_and_unregister)
        menu.addAction(collapse_action)

        menu.addSeparator()

        prev_action = QAction("◀ Previous Matchup", self)
        prev_action.triggered.connect(lambda: self._cycle_matchup('prev'))
        menu.addAction(prev_action)

        next_action = QAction("▶ Next Matchup", self)
        next_action.triggered.connect(lambda: self._cycle_matchup('next'))
        menu.addAction(next_action)

        menu.addSeparator()

        edge_menu = menu.addMenu("Dock Edge")
        edge_menu.setStyleSheet(menu.styleSheet())
        # cycling through docking options
        for label, edge in [("Left", "left"), ("Right", "right"), ("Top", "top")]:
            a = QAction(label, self)
            a.setCheckable(True)
            a.setChecked(self._edge == edge)
            a.triggered.connect(lambda checked, e=edge: self._set_edge(e))
            edge_menu.addAction(a)

        self._get_screen_menu(menu)

        menu.addSeparator()

        open_action = QAction("Open League in Browser", self)
        open_action.triggered.connect(self._open_league)
        menu.addAction(open_action)

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

    def _get_screen_menu(self, menu):
        screen_menu = menu.addMenu("Move to Monitor")
        screen_menu.setStyleSheet(menu.styleSheet())
        screens = QApplication.screens()
        current_screen = QApplication.screenAt(self.pos())
        for i, screen in enumerate(screens):
            geo = screen.geometry()
            label = f"Monitor {i+1} ({geo.width()}x{geo.height()})"
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(screen == current_screen)
            action.triggered.connect(lambda checked, s=screen: self._move_to_screen(s))
            screen_menu.addAction(action)

    def _move_to_screen(self, screen):
        if self._appbar:
            self._appbar.unregister()
        screens = QApplication.screens()
        idx = screens.index(screen)
        self._save_setting('monitor', idx)
        QTimer.singleShot(100, lambda: self._register_appbar_on_screen(screen))

    def _register_appbar_on_screen(self, screen):
        hwnd = int(self.winId())
        self._appbar = AppBar(hwnd, BAR_THICKNESS)
        self._appbar.register(self._edge, screen=screen.geometry())

    def _save_setting(self, key, value):
        try:
            with open(SETTINGS_PATH) as f:
                s = json.load(f)
            s[key] = value
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(s, f, indent=2)
        except Exception as e:
            print(f"[DesktopWidget] Failed to save setting {key}: {e}")

    def _hide_and_unregister(self):
        if self._appbar:
            self._appbar.unregister()
            self._appbar = None
        self.hide()
        event_bus.widget_hidden.emit()

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _open_league(self):
        try:
            with open(SETTINGS_PATH) as f:
                s = json.load(f)
            lid = s['espn']['league_id']
            webbrowser.open(f"https://fantasy.espn.com/basketball/league?leagueId={lid}")
        except Exception as e:
            print(f"[DesktopWidget] Failed to open league URL: {e}")
            webbrowser.open("https://fantasy.espn.com")

    def _request_refresh(self):
        event_bus.force_refresh.emit()

    def _open_settings(self):
        from ui.setup_dialog import SetupDialog
        dialog = SetupDialog(self)
        if dialog.exec():
            event_bus.force_refresh.emit()
            self._reload_roster()

    def _quit(self):
        if self._appbar:
            self._appbar.unregister()
        QApplication.quit()

    def closeEvent(self, event):
        if self._appbar:
            self._appbar.unregister()
        super().closeEvent(event)

    def _reload_roster(self):
        from api.espn_client import ESPNClient
        from api.team_cache import TeamCache
        try:
            client = ESPNClient()
            client.connect()
            all_teams_data = client.get_all_teams_data()
            self._team_cache = TeamCache(all_teams_data)
            self._switch_to_team(self._current_team_id)
            if hasattr(self, 'live_poller'):
                names = []
                for tid in self._team_cache.all_team_ids:
                    td = self._team_cache.get_team(tid)
                    names.extend([p.name for p in td.get('full_snapshot', [])])
                self.live_poller.update_roster_names(list(set(names)))
        except Exception as e:
            print(f"[DesktopWidget] Reload failed: {e}")

    # ── Settings persistence ──────────────────────────────────────────────────

    def _load_last_team_id(self) -> int:
        try:
            with open(SETTINGS_PATH) as f:
                return json.load(f)['espn'].get('last_viewed_team_id', 1)
        except Exception as e:
            print(f"[DesktopWidget] Failed to load last team ID: {e}")
            return 1

    def _save_last_team_id(self, team_id: int):
        try:
            with open(SETTINGS_PATH) as f:
                s = json.load(f)
            s['espn']['last_viewed_team_id'] = team_id
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(s, f, indent=2)
        except Exception as e:
            print(f"[DesktopWidget] Failed to save last team ID: {e}")

    def _load_edge(self) -> str:
        try:
            with open(SETTINGS_PATH) as f:
                return json.load(f).get('dock_edge', 'right')
        except Exception as e:
            print(f"[DesktopWidget] Failed to load dock edge: {e}")
            return 'right'

    def _save_edge(self, edge: str):
        try:
            with open(SETTINGS_PATH) as f:
                s = json.load(f)
            s['dock_edge'] = edge
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(s, f, indent=2)
        except Exception as e:
            print(f"[DesktopWidget] Failed to save dock edge: {e}")