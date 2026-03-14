from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFontDatabase, QFont, QPainter, QColor, QPen
from ui.sprite_loader import sprite_loader, get_jersey_for_team, _clean_player_name
import os

FONT_PATH = os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts', 'pixel.ttf')

# CONSTANTS
NAME_SCROLL_SPEED = 1    # pixels per tick
NAME_SCROLL_FPS   = 40   # ms per tick (lower = faster)
NAME_SCROLL_PAUSE = 75   # ticks to pause at each end (~3s at 40ms/tick)


class PlayerCard(QWidget):
    VIEWS = ['LIVE', 'AVERAGES', 'STATLINE']
    _current_view = 'LIVE'
    _all_cards: list = []

    def __init__(self, player_name: str, position: str, points: float = 0.0, nba_team: str = ""):
        super().__init__()
        self.player_name = _clean_player_name(player_name)
        self._short_name = self.player_name.split()[-1]

        self.position = position
        self.points   = points

        self._jersey      = get_jersey_for_team(nba_team)
        self._live_data   = {}
        self._season_avg  = 0.0
        self._today_stats = {}

        self._current_anim = "idle"
        self._frame_list   = []
        self._frame_index  = 0

        self._setup_font()
        self._build_ui()
        self._setup_name_scroll()

        PlayerCard._all_cards.append(self)
        self.destroyed.connect(self._on_destroyed)

        self._idle_timer = QTimer()
        self._idle_timer.timeout.connect(self._tick_idle)
        self._start_idle()

        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._tick_anim)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(76, 94)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(100, self._start_name_scroll)

    def _on_destroyed(self):
        try:
            if self in PlayerCard._all_cards:
                PlayerCard._all_cards.remove(self)
        except Exception:
            pass
        try:
            if hasattr(self, '_scroll_timer'):
                self._scroll_timer.stop()
        except RuntimeError:
            pass

    # ── Font ──────────────────────────────────────────────────────────────────

    def _setup_font(self):
        font_id  = QFontDatabase.addApplicationFont(FONT_PATH)
        families = QFontDatabase.applicationFontFamilies(font_id)
        self._pixel_font = QFont(families[0], 5) if families else QFont("Courier", 6)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        inner = QVBoxLayout(self)
        inner.setContentsMargins(8, 5, 8, 5)  # (80-64)/2=8 left/right, (100-90)/2=5 top/bottom
        inner.setSpacing(1)
        inner.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._sprite_label = QLabel()
        self._sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sprite_label.setFixedSize(64, 64)
        self._sprite_label.setStyleSheet("background: transparent;")

        self._name_label = QLabel(self._short_name)
        self._name_label.setFont(self._pixel_font)
        self._name_label.setStyleSheet("color: #000A14; background: transparent;")
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setFixedWidth(64)

        self._points_label = QLabel("—")
        self._points_label.setFont(self._pixel_font)
        self._points_label.setStyleSheet("color: #000A14; background: transparent;")
        self._points_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        inner.addWidget(self._sprite_label)
        inner.addWidget(self._name_label)
        inner.addWidget(self._points_label)
        
        # Keep _bg_widget reference for compatibility but don't use it visually
        self._bg_widget = self
    
    # ── Border drawn on top of bg_widget ─────────────────────────────────────

    def get_border_color(self) -> str:
        status = self._live_data.get('game_status', '')
        if status in ('STATUS_IN_PROGRESS', 'STATUS_HALFTIME'):
            return '#a6e3a1'
        elif status == 'STATUS_FINAL':
            return '#FFD700'
        return '#000000'

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setBrush(QColor(216, 226, 240, 180))
        painter.setPen(QPen(QColor(self.get_border_color()), 2))
        # Center a 72x90 rect within the 80x100 widget
        x = (self.width() - 72) // 2
        y = (self.height() - 90) // 2
        from PyQt6.QtCore import QRect
        rect = QRect(x, y, 72, 90).adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(rect, 8, 8)
        painter.end()

    # ── Idle animation ────────────────────────────────────────────────────────

    def _start_idle(self):
        anim = sprite_loader.get_animation("idle")
        self._idle_frame_indices = anim["frames"]
        self._idle_index = 0
        fps = anim.get("fps", 6)
        self._idle_pixmaps = sprite_loader.get_idle_frames(self.player_name, self._jersey)
        self._idle_timer.start(1000 // fps)
        if self._idle_pixmaps:
            self._sprite_label.setPixmap(self._idle_pixmaps[0])

    def _tick_idle(self):
        if not self._idle_pixmaps:
            return
        self._idle_index = (self._idle_index + 1) % len(self._idle_pixmaps)
        self._sprite_label.setPixmap(self._idle_pixmaps[self._idle_index])

    # ── Event animation ───────────────────────────────────────────────────────

    def animate(self, animation_name: str):
        anim = sprite_loader.get_animation(animation_name)
        self._frame_list   = anim["frames"]
        self._frame_index  = 0
        self._current_anim = animation_name
        fps = anim.get("fps", 8)
        self._idle_timer.stop()

        if animation_name == 'madeShot':
            self._anim_pixmaps = sprite_loader.get_made_shot_frames(self.player_name, self._jersey)
        elif animation_name == 'missedShot':
            self._anim_pixmaps = sprite_loader.get_missed_shot_frames()
        elif animation_name == 'block':
            self._anim_pixmaps = sprite_loader.get_block_frames(self.player_name)
        else:
            self._anim_pixmaps = []

        self._anim_timer.start(1000 // fps)

    def _tick_anim(self):
        if self._frame_index >= len(self._frame_list):
            self._anim_timer.stop()
            self._current_anim = "idle"
            self._start_idle()
            return

        idx = self._frame_list[self._frame_index]
        if self._anim_pixmaps and idx < len(self._anim_pixmaps):
            self._sprite_label.setPixmap(self._anim_pixmaps[idx])
        else:
            pixmap = sprite_loader.get_frame(idx)
            if pixmap:
                self._sprite_label.setPixmap(pixmap)

        self._frame_index += 1

    def _show_frame(self, frame_index: int):
        pixmap = sprite_loader.get_frame(frame_index)
        if pixmap:
            self._sprite_label.setPixmap(pixmap)

    # ── Setters ───────────────────────────────────────────────────────────────

    def set_jersey(self, jersey: str):
        self._jersey = jersey
        self._idle_pixmaps = sprite_loader.get_idle_frames(self.player_name, self._jersey)
        self._idle_index = 0

    def update_points(self, new_points: float):
        self.points = new_points
        if PlayerCard._current_view != 'LIVE':
            self._refresh_display()

    def set_live_data(self, data: dict):
        self._live_data   = data
        self._today_stats = data
        if PlayerCard._current_view in ('LIVE', 'STATLINE'):
            self._refresh_display()

    def set_season_avg(self, avg_pts: float):
        self._season_avg = avg_pts
        if PlayerCard._current_view == 'AVERAGES':
            self._refresh_display()

    def set_live(self, is_live: bool):
        self._is_live = is_live
        if is_live:
            self._start_pulse()
        else:
            self._stop_pulse()

    def set_inactive(self, reason: str = ""):
        if reason:
            self._points_label.setText(reason)

    def set_game_finished(self, final_points: float):
        self._points_label.setText(f"✓ {final_points:.1f}")
        self._points_label.setStyleSheet("color: #000A14; background: transparent;")

    # ── Pulse ─────────────────────────────────────────────────────────────────

    def _start_pulse(self):
        if not hasattr(self, '_pulse_timer'):
            self._pulse_timer = QTimer()
            self._pulse_state = False
            self._pulse_timer.timeout.connect(self._tick_pulse)
        self._pulse_timer.start(800)

    def _stop_pulse(self):
        if hasattr(self, '_pulse_timer'):
            self._pulse_timer.stop()
        self._name_label.setStyleSheet("color: #000A14; background: transparent;")

    def _tick_pulse(self):
        self._pulse_state = not self._pulse_state
        color = "#a6e3a1" if self._pulse_state else "#000A14"
        self._name_label.setStyleSheet(f"color: {color}; background: transparent;")

    # ── Click to cycle view ───────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            idx = PlayerCard.VIEWS.index(PlayerCard._current_view)
            PlayerCard._current_view = PlayerCard.VIEWS[(idx + 1) % len(PlayerCard.VIEWS)]
            alive = []
            for card in PlayerCard._all_cards:
                try:
                    card._points_label.objectName()
                    alive.append(card)
                except RuntimeError:
                    pass
            PlayerCard._all_cards = alive
            for card in PlayerCard._all_cards:
                card._refresh_display()

    # ── Display modes ─────────────────────────────────────────────────────────

    def _refresh_display(self):
        try:
            self._points_label.objectName()
        except RuntimeError:
            return

        mode = PlayerCard._current_view

        self._points_label.setStyleSheet("color: #000A14; background: transparent;")
        self._name_label.setStyleSheet("color: #000A14; background: transparent;")

        if mode == 'LIVE':
            fpts   = self._live_data.get('fantasy_pts', None)
            status = self._live_data.get('game_status', '')
            ACTIVE_STATUSES = {'STATUS_IN_PROGRESS', 'STATUS_HALFTIME'}

            if fpts is None or status == '':
                self._points_label.setText("—")
                self._name_label.setText(self._short_name)
            elif status in ACTIVE_STATUSES:
                self._points_label.setText(f"{fpts:.1f}")
                self._name_label.setText(
                    self._short_name if status == 'STATUS_IN_PROGRESS'
                    else self._short_name + " ⏸"
                )
            elif status == 'STATUS_FINAL':
                self._points_label.setText(f"{fpts:.1f}")
                self._name_label.setText(self._short_name)
            else:
                self._points_label.setText("—")
                self._name_label.setText(self._short_name)

        elif mode == 'AVERAGES':
            self._points_label.setText(f"{self._season_avg:.1f} avg")
            self._name_label.setText(self._short_name)

        elif mode == 'STATLINE':
            pts = self._today_stats.get('PTS', 0)
            reb = self._today_stats.get('REB', 0)
            ast = self._today_stats.get('AST', 0)
            pf  = self._today_stats.get('PF',  0)
            self._points_label.setText(f"{int(pts)}/{int(reb)}/{int(ast)}/{int(pf)}")
            self._name_label.setText(self._short_name)

        self._start_name_scroll()
        self.update()

    # ── Name scroll ───────────────────────────────────────────────────────────

    def _setup_name_scroll(self):
        self._scroll_timer       = QTimer()
        self._scroll_timer.timeout.connect(self._tick_name_scroll)
        self._scroll_offset      = 0
        self._scroll_direction   = 1
        self._scroll_pausing     = False
        self._scroll_pause_ticks = 0
        self._name_needs_scroll  = False

    def _start_name_scroll(self):
        fm          = self._name_label.fontMetrics()
        text_width  = fm.horizontalAdvance(self._name_label.text())
        label_width = self._name_label.width()
        if text_width > label_width:
            self._name_needs_scroll  = True
            self._scroll_offset      = 0
            self._scroll_direction   = 1
            self._scroll_pausing     = False
            self._scroll_pause_ticks = 0
            self._scroll_max         = text_width - label_width + 4
            self._scroll_timer.start(NAME_SCROLL_FPS)
        else:
            self._name_needs_scroll = False
            self._scroll_timer.stop()
            self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._name_label.setContentsMargins(0, 0, 0, 0)

    def _tick_name_scroll(self):
        if self._scroll_pausing:
            self._scroll_pause_ticks -= 1
            if self._scroll_pause_ticks <= 0:
                self._scroll_pausing = False
            return

        self._scroll_offset += self._scroll_direction * NAME_SCROLL_SPEED
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._name_label.setContentsMargins(-int(self._scroll_offset), 0, 0, 0)

        if self._scroll_offset >= self._scroll_max:
            self._scroll_offset    = self._scroll_max
            self._scroll_direction = -1
            self._scroll_pausing   = True
            self._scroll_pause_ticks = NAME_SCROLL_PAUSE
        elif self._scroll_offset <= 0:
            self._scroll_offset    = 0
            self._scroll_direction = 1
            self._scroll_pausing   = True
            self._scroll_pause_ticks = NAME_SCROLL_PAUSE