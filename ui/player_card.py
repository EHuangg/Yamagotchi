from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFontDatabase, QFont, QPainter, QColor, QPen
from ui.sprite_loader import sprite_loader, get_jersey_for_team, _clean_player_name
import os

FONT_PATH = os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts', 'pixel.ttf')

# ── Timer / animation constants ───────────────────────────────────────────────
NAME_SCROLL_SPEED       = 1    # pixels per tick
NAME_SCROLL_FPS         = 40   # ms per tick (lower = faster)
NAME_SCROLL_PAUSE       = 75   # ticks to pause at each end (~3s at 40ms/tick)
QUARTER_PULSE_INTERVAL  = 800  # ms between quarter bar pulse toggles


class PlayerCard(QWidget):
    VIEWS = ['LIVE', 'AVERAGES', 'STATLINE']
    _current_view = 'LIVE'
    _all_cards: list = []

    def __init__(self, player_name: str, position: str, points: float = 0.0,
                 nba_team: str = "", injury_status: str = ""):
        super().__init__()
        self.player_name = _clean_player_name(player_name)
        self._short_name = self.player_name.split()[-1]

        self.position = position
        self.points   = points

        self._jersey      = get_jersey_for_team(nba_team)
        self._live_data   = {}
        self._season_avg  = 0.0
        self._today_stats = {}

        self._current_anim  = "idle"
        self._frame_list    = []
        self._frame_index   = 0

        self._injury_status = injury_status.upper()

        self._fouls         = 0
        self._quarter       = 0
        self._ot_period     = 0
        self._game_active   = False
        self._game_finished = False

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

        self._quarter_pulse_state = False
        self._quarter_pulse_timer = QTimer()
        self._quarter_pulse_timer.timeout.connect(self._tick_quarter_pulse)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(76, 94)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(100, self._start_name_scroll)

    def _on_destroyed(self):
        for attr in ('_quarter_pulse_timer', '_scroll_timer', '_pulse_timer'):
            try:
                if hasattr(self, attr):
                    getattr(self, attr).stop()
            except RuntimeError:
                pass
        try:
            if self in PlayerCard._all_cards:
                PlayerCard._all_cards.remove(self)
        except Exception:
            pass

    # ── Font ──────────────────────────────────────────────────────────────────

    def _setup_font(self):
        font_id  = QFontDatabase.addApplicationFont(FONT_PATH)
        families = QFontDatabase.applicationFontFamilies(font_id)
        self._pixel_font = QFont(families[0], 5) if families else QFont("Courier", 6)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        inner = QVBoxLayout(self)
        inner.setContentsMargins(5, 5, 5, 5)
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

        self._bg_widget = self  # compatibility reference

    # ── Border ────────────────────────────────────────────────────────────────

    def get_border_color(self) -> str:
        if self._injury_status in ('OUT', 'DOUBTFUL', 'INJURY_RESERVE'):
            return "#cf2354"
        if self._injury_status in ('QUESTIONABLE', 'DAY_TO_DAY', 'PROBABLE'):
            return '#f38ba8'
        status = self._live_data.get('game_status', '')
        if status in ('STATUS_IN_PROGRESS', 'STATUS_HALFTIME'):
            return '#a6e3a1'
        elif status == 'STATUS_FINAL':
            return "#000000"
        return "#868686"

    def paintEvent(self, event):
        super().paintEvent(event)
        from PyQt6.QtCore import QRect

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # ── Outer border ──────────────────────────────────────────────────────
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(self.get_border_color()), 2))
        x = (self.width() - 72) // 2
        y = (self.height() - 90) // 2
        bg_rect = QRect(x, y, 72, 90).adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(bg_rect, 8, 8)

        # Only draw bars if game is actively in progress
        if not self._game_active:
            painter.end()
            return

        # ── Bar layout ────────────────────────────────────────────────────────
        bar_w        = 2
        bar_h        = 9
        bar_gap      = 4
        bar_x_left   = bg_rect.left() + 3
        bar_x_right  = bg_rect.right() - 3 - bar_w
        bar_bottom_y = bg_rect.bottom() - 4

        # ── OT label at top ───────────────────────────────────────────────────
        if self._ot_period > 0:
            ot_text = f"OT{self._ot_period}" if self._ot_period > 1 else "OT"
            painter.setPen(QColor('#000A14'))
            painter.setFont(_load_pixel_font(4))
            painter.drawText(
                QRect(bg_rect.left(), bg_rect.top() + 2, bg_rect.width(), 8),
                Qt.AlignmentFlag.AlignCenter, ot_text
            )

        # ── Left bars — fouls (red), bottom to top ────────────────────────────
        for i in range(6):
            bar_y = bar_bottom_y - i * (bar_h + bar_gap) - bar_h
            rect  = QRect(bar_x_left, bar_y, bar_w, bar_h)
            if i < self._fouls:
                color = '#FF0000' if i >= 4 else '#f38ba8'
                painter.fillRect(rect, QColor(color))

        # ── Right bars — quarters (green), bottom to top ──────────────────────
        for i in range(4):
            bar_y   = bar_bottom_y - i * (bar_h + bar_gap) - bar_h
            rect    = QRect(bar_x_right, bar_y, bar_w, bar_h)
            quarter = i + 1

            if quarter < self._quarter:
                painter.fillRect(rect, QColor('#a6e3a1'))
            elif quarter == self._quarter:
                color = '#a6e3a1' if self._quarter_pulse_state else '#d4f0d4'
                painter.fillRect(rect, QColor(color))

        painter.end()

    # ── Quarter pulse ─────────────────────────────────────────────────────────

    def _tick_quarter_pulse(self):
        self._quarter_pulse_state = not self._quarter_pulse_state
        self.update()

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
        # debug
        print(f"[Card] {self.player_name} status={data.get('game_status')} fpts={data.get('fantasy_pts')} injury={self._injury_status}")
        
        self._live_data   = data
        self._today_stats = data
        self._fouls       = int(data.get('PF', 0))

        status   = data.get('game_status', '')
        headline = data.get('game_headline', '')

        self._game_active   = status in ('STATUS_IN_PROGRESS', 'STATUS_HALFTIME')
        self._game_finished = status == 'STATUS_FINAL'

        if self._game_active:
            self._quarter_pulse_timer.start(QUARTER_PULSE_INTERVAL)
        else:
            self._quarter_pulse_timer.stop()
            self._quarter_pulse_state = False

        self._quarter   = 0
        self._ot_period = 0
        if self._game_active or self._game_finished:
            import re
            h = headline.upper()
            if 'OT' in h:
                m = re.search(r'(\d*)OT', h)
                self._ot_period = int(m.group(1)) if m and m.group(1) else 1
                self._quarter   = 4
            else:
                m = re.search(r'(\d+)(?:ST|ND|RD|TH)', h)
                if m:
                    self._quarter = min(int(m.group(1)), 4)
                elif self._game_finished:
                    self._quarter = 4

        if PlayerCard._current_view in ('LIVE', 'STATLINE'):
            self._refresh_display()

    def set_season_avg(self, avg_pts: float):
        self._season_avg = avg_pts
        if PlayerCard._current_view == 'AVERAGES':
            self._refresh_display()

    def set_inactive(self, reason: str = ""):
        if reason:
            self._points_label.setText(reason)

    def set_game_finished(self, final_points: float):
        self._points_label.setText(f"✓ {final_points:.1f}")
        self._points_label.setStyleSheet("color: #000A14; background: transparent;")

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

        mode   = PlayerCard._current_view
        fpts   = self._live_data.get('fantasy_pts', None)
        status = self._live_data.get('game_status', '')
        ACTIVE_STATUSES = {'STATUS_IN_PROGRESS', 'STATUS_HALFTIME'}

        no_game    = fpts is None or status == ''
        is_injured = self._injury_status in (
            'OUT', 'INJURY_RESERVE', 'QUESTIONABLE', 'DAY_TO_DAY', 'DOUBTFUL', 'PROBABLE'
        )

        # debug
        print(f"[Refresh] {self.player_name} no_game={no_game} injured={is_injured} status={status} fpts={fpts}")

        
        if is_injured:
            text_color = '#f38ba8'
        elif no_game:
            text_color = '#929EAF'
        else:
            text_color = '#000A14'

        self._points_label.setStyleSheet(f"color: {text_color}; background: transparent;")
        self._name_label.setStyleSheet(f"color: {text_color}; background: transparent;")

        if mode == 'LIVE':
            if no_game:
                self._points_label.setText("—")
            elif status in ACTIVE_STATUSES:
                self._points_label.setText(f"{fpts:.1f}")
            elif status == 'STATUS_FINAL':
                self._points_label.setText(f"{fpts:.1f}")
            else:
                self._points_label.setText("—")

        elif mode == 'AVERAGES':
            self._points_label.setText(f"{self._season_avg:.1f} avg")

        elif mode == 'STATLINE':
            pts = self._today_stats.get('PTS', 0)
            reb = self._today_stats.get('REB', 0)
            ast = self._today_stats.get('AST', 0)
            pf  = self._today_stats.get('PF',  0)
            self._points_label.setText(f"{int(pts)}/{int(reb)}/{int(ast)}/{int(pf)}")

        # Name label text
        if is_injured:
            if self._injury_status in ('OUT', 'INJURY_RESERVE'):
                self._name_label.setText(self._short_name + " O")
            else:
                self._name_label.setText(self._short_name + " DTD")
        elif status in ACTIVE_STATUSES:
            self._name_label.setText(
                self._short_name if status == 'STATUS_IN_PROGRESS'
                else self._short_name + " ⏸"
            )
        else:
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


def _load_pixel_font(size: int = 8) -> QFont:
    font_id  = QFontDatabase.addApplicationFont(FONT_PATH)
    families = QFontDatabase.applicationFontFamilies(font_id)
    return QFont(families[0], size) if families else QFont("Courier", size)