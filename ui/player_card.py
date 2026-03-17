from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QVariantAnimation
from PyQt6.QtGui import QFontDatabase, QFont, QPainter, QColor, QPen, QBrush
from ui.sprite_loader import sprite_loader, get_jersey_for_team, _clean_player_name
import os

FONT_PATH = os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts', 'pixel.ttf')

# ── Timer / animation constants ───────────────────────────────────────────────
NAME_SCROLL_SPEED       = 1    # pixels per tick
NAME_SCROLL_FPS         = 40   # ms per tick (lower = faster)
NAME_SCROLL_PAUSE       = 75   # ticks to pause at each end (~3s at 40ms/tick)
NAME_LABEL_LEFT_PADDING = 12   # marquee start boundary for long names
NAME_LABEL_ROW_OFFSET   = 7    # shifts the whole name track right within the card
GLOBAL_ANIMATION_TICK   = 800  # shared tick for pulse-driven UI
OT_LABEL_SWITCH_TICKS   = 2    # switch OT label every 2 global ticks
IDLE_FRAME_SWITCH_TICKS = 4    # advance idle frame every 4 global ticks
POSITION_FLASH_FADE_IN_MS = 500
POSITION_FLASH_HOLD_MS = 3000
POSITION_FLASH_FADE_OUT_MS = 500
POSITION_FLASH_DURATION_MS = (
    POSITION_FLASH_FADE_IN_MS + POSITION_FLASH_HOLD_MS + POSITION_FLASH_FADE_OUT_MS
)
POSITION_FLASH_COLOR = "#62d26f"


class SlidingNameLabel(QLabel):
    def __init__(self, text: str = ""):
        super().__init__(text)
        self._scroll_enabled = False
        self._scroll_offset = 0
        self._text_color = QColor('#000A14')
        self.setStyleSheet("background: transparent;")

    def set_scroll_enabled(self, enabled: bool):
        self._scroll_enabled = enabled
        self.update()

    def set_scroll_offset(self, offset: int):
        self._scroll_offset = offset
        self.update()

    def set_text_color(self, color):
        self._text_color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)
        painter.setClipRect(self.rect())
        painter.setFont(self.font())
        painter.setPen(self._text_color)

        text = self.text()
        text_width = self.fontMetrics().horizontalAdvance(text)

        if self._scroll_enabled and text_width > self.width():
            text_x = NAME_LABEL_LEFT_PADDING - int(self._scroll_offset)
        else:
            text_x = max(0, (self.width() - text_width) // 2)

        text_rect = QRect(text_x, 0, max(self.width(), text_width), self.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)


class PlayerCard(QWidget):
    VIEWS = ['LIVE', 'AVERAGES', 'STATLINE']
    _current_view = 'LIVE'
    _all_cards: list = []
    _global_animation_timer = None
    _global_tick_count = 0
    _shared_pulse_state = False
    _shared_ot_label_show_text = True
    _shared_idle_phase = 0

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
        self._on_court    = False

        self._current_anim  = "idle"
        self._frame_list    = []
        self._frame_index   = 0

        self._injury_status = injury_status.upper()

        self._fouls         = 0
        self._quarter       = 0
        self._ot_period     = 0
        self._ot_label_show_text = True
        self._game_active   = False
        self._game_break    = False
        self._game_finished = False

        self._setup_font()
        self._build_ui()
        self._setup_name_scroll()

        PlayerCard._all_cards.append(self)
        self.destroyed.connect(self._on_destroyed)

        PlayerCard._ensure_global_animation_timer()
        self._start_idle()

        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._tick_anim)

        self._quarter_pulse_state = PlayerCard._shared_pulse_state
        self._ot_label_show_text = PlayerCard._shared_ot_label_show_text

        self._border_override_color = None
        self._position_flash_anim = None
        self._position_flash_base_color = QColor('#000000')

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(90, 94)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(100, self._start_name_scroll)

    def _on_destroyed(self):
        for attr in ('_anim_timer', '_scroll_timer', '_pulse_timer'):
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
        PlayerCard._stop_global_animation_timer_if_unused()

    @classmethod
    def _alive_cards(cls):
        alive = []
        for card in cls._all_cards:
            try:
                card._points_label.objectName()
                alive.append(card)
            except RuntimeError:
                pass
        cls._all_cards = alive
        return alive

    @classmethod
    def _ensure_global_animation_timer(cls):
        if cls._global_animation_timer is None:
            cls._global_animation_timer = QTimer()
            cls._global_animation_timer.timeout.connect(cls._on_global_animation_tick)
        if not cls._global_animation_timer.isActive():
            cls._global_animation_timer.start(GLOBAL_ANIMATION_TICK)

    @classmethod
    def _stop_global_animation_timer_if_unused(cls):
        if cls._global_animation_timer and not cls._alive_cards():
            cls._global_animation_timer.stop()

    @classmethod
    def _on_global_animation_tick(cls):
        cls._shared_pulse_state = not cls._shared_pulse_state
        cls._global_tick_count += 1

        if cls._global_tick_count % OT_LABEL_SWITCH_TICKS == 0:
            cls._shared_ot_label_show_text = not cls._shared_ot_label_show_text

        if cls._global_tick_count % IDLE_FRAME_SWITCH_TICKS == 0:
            cls._shared_idle_phase += 1

        for card in cls._alive_cards():
            card._apply_global_animation_state()

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

        self._name_label = SlidingNameLabel(self._short_name)
        self._name_label.setFont(self._pixel_font)
        self._name_label.setFixedWidth(50)
        self._name_label.set_text_color('#000A14')

        self._name_row = QWidget()
        self._name_row.setFixedWidth(64)
        self._name_row.setStyleSheet("background: transparent;")
        name_layout = QHBoxLayout(self._name_row)
        name_layout.setContentsMargins(NAME_LABEL_ROW_OFFSET, 0, 0, 0)
        name_layout.setSpacing(0)
        name_layout.addWidget(self._name_label)
        name_layout.addStretch(1)

        self._points_label = QLabel("—")
        self._points_label.setFont(self._pixel_font)
        self._points_label.setStyleSheet("color: #000A14; background: transparent;")
        self._points_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        inner.addWidget(self._sprite_label)
        inner.addWidget(self._name_row)
        inner.addWidget(self._points_label)

        self._bg_widget = self  # compatibility reference

    # ── Border ────────────────────────────────────────────────────────────────

    def get_border_color(self) -> str:
        if self._border_override_color is not None:
            return self._border_override_color.name()

        if self._injury_status in ('OUT', 'DOUBTFUL', 'INJURY_RESERVE'):
            return "#cf2354"
        if self._injury_status in ('QUESTIONABLE', 'DAY_TO_DAY', 'PROBABLE'):
            return '#f38ba8'
        status = self._live_data.get('game_status', '')
        if status in ('STATUS_IN_PROGRESS', 'STATUS_HALFTIME', 'STATUS_END_PERIOD', 'STATUS_INTERMISSION'):
            return '#000000'
        elif status == 'STATUS_FINAL':
            return '#000000'
        return '#868686'

    @staticmethod
    def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
        t = max(0.0, min(1.0, t))
        r = int(c1.red() + (c2.red() - c1.red()) * t)
        g = int(c1.green() + (c2.green() - c1.green()) * t)
        b = int(c1.blue() + (c2.blue() - c1.blue()) * t)
        return QColor(r, g, b)

    def flash_position_change_indicator(self):
        base = QColor(self.get_border_color())
        accent = QColor(POSITION_FLASH_COLOR)
        self._position_flash_base_color = base

        fade_in_end = POSITION_FLASH_FADE_IN_MS / POSITION_FLASH_DURATION_MS
        hold_end = (POSITION_FLASH_FADE_IN_MS + POSITION_FLASH_HOLD_MS) / POSITION_FLASH_DURATION_MS

        if self._position_flash_anim is None:
            self._position_flash_anim = QVariantAnimation(self)
            self._position_flash_anim.setDuration(POSITION_FLASH_DURATION_MS)
            self._position_flash_anim.setStartValue(0.0)
            self._position_flash_anim.setEndValue(1.0)

            def _on_value(value):
                t = float(value)
                if t <= fade_in_end:
                    local_t = t / max(fade_in_end, 1e-9)
                    color = self._lerp_color(self._position_flash_base_color, accent, local_t)
                elif t <= hold_end:
                    color = accent
                else:
                    local_t = (t - hold_end) / max((1.0 - hold_end), 1e-9)
                    color = self._lerp_color(accent, self._position_flash_base_color, local_t)
                self._border_override_color = color
                self.update()

            def _on_finished():
                self._border_override_color = None
                self.update()

            self._position_flash_anim.valueChanged.connect(_on_value)
            self._position_flash_anim.finished.connect(_on_finished)

        if self._position_flash_anim.state() == QVariantAnimation.State.Running:
            self._position_flash_anim.stop()

        self._position_flash_anim.start()

    def _get_injury_side_label(self):
        if self._injury_status in ('OUT', 'INJURY_RESERVE'):
            return 'O', '#cf2354'
        if self._injury_status in ('QUESTIONABLE', 'DAY_TO_DAY', 'DOUBTFUL', 'PROBABLE'):
            return 'DTD', '#f38ba8'
        return None, None

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # ── Outer border ──────────────────────────────────────────────────────
        ox = (self.width() - 64) // 2    # 13px left/right strips for rotated labels
        oy = (self.height() - 90) // 2
        bg_rect = QRect(ox, oy, 64, 90).adjusted(1, 1, -1, -1)

        # Full-card on-court highlight
        if self._on_court and self._live_data.get('game_status', '') == 'STATUS_IN_PROGRESS':
            painter.setBrush(QColor('#FFB347'))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.setPen(QPen(QColor(self.get_border_color()), 2))
        painter.drawRoundedRect(bg_rect, 8, 8)

        # Injury side tag is always shown when present (independent of bar visibility).
        injury_label, injury_color = self._get_injury_side_label()
        if injury_label:
            painter.save()
            painter.setFont(_load_pixel_font(5))
            painter.setPen(QColor(injury_color))
            injury_rect = QRect(bg_rect.left() + 4, bg_rect.top() + 2, 22, 8)
            painter.drawText(injury_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, injury_label)
            painter.restore()

        # Draw indicators only when game is live or in a break between periods
        if not (self._game_active or self._game_break):
            painter.end()
            return

        # ── Layout constants ──────────────────────────────────────────────────
        bar_w      = 2
        bar_h      = 9
        bar_gap    = 4
        row_stride = bar_h + bar_gap        # 13 px

        bar_bottom_y = bg_rect.bottom() - 4
        bar_x_left   = bg_rect.left() + 3
        bar_x_right  = bg_rect.right() - 4 - bar_w   # quarter bar left edge

        # ── Rotated "FLS" label — left padding strip ──────────────────────────
        mid_y    = bg_rect.top() + bg_rect.height() // 2
        left_cx  = ox // 2
        right_cx = bg_rect.right() + (self.width() - bg_rect.right()) // 2

        painter.save()
        painter.setFont(_load_pixel_font(5))
        painter.setPen(QColor('#344d5c'))
        painter.translate(left_cx, mid_y)
        painter.rotate(-90)
        painter.drawText(QRect(-18, -4, 36, 8), Qt.AlignmentFlag.AlignCenter, 'FLS')
        painter.restore()

        # ── Rotated "QTR" label — right padding strip ─────────────────────────
        painter.save()
        painter.setFont(_load_pixel_font(5))
        painter.setPen(QColor('#344d5c'))
        painter.translate(right_cx, mid_y)
        painter.rotate(90)
        painter.drawText(QRect(-18, -4, 36, 8), Qt.AlignmentFlag.AlignCenter, 'QTR')
        painter.restore()

        # ── Left column: foul bars, bottom → top ──────────────────────────────
        for i in range(6):
            bar_y = bar_bottom_y - i * row_stride - bar_h
            rect = QRect(bar_x_left, bar_y, bar_w, bar_h)
            if i < self._fouls:
                painter.fillRect(rect, QColor('#000000'))

        # ── Right column: quarter bars + optional OT bar, bottom → top ────────
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        bar_col = QColor('#000000')

        if self._ot_period > 0:
            for i in range(5):
                bar_y  = bar_bottom_y - i * row_stride - bar_h
                rect   = QRect(bar_x_right, bar_y, bar_w, bar_h)
                is_ot  = (i == 4)

                if is_ot:
                    if not (self._game_active and not self._quarter_pulse_state):
                        painter.fillRect(rect, bar_col)

                    ot_label = 'OT' if self._ot_label_show_text else str(self._ot_period)
                    painter.save()
                    painter.setFont(_load_pixel_font(5))
                    painter.setPen(QColor('#000A14'))
                    lbl_rect = QRect(bar_x_right - 13, bar_y - 11, bar_w + 20, 10)
                    painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, ot_label)
                    painter.restore()
                else:
                    painter.fillRect(rect, bar_col)
        else:
            for i in range(4):
                q     = i + 1
                bar_y = bar_bottom_y - i * row_stride - bar_h
                rect  = QRect(bar_x_right, bar_y, bar_w, bar_h)

                if q < self._quarter:
                    painter.fillRect(rect, bar_col)
                elif q == self._quarter:
                    if not (self._game_active and not self._quarter_pulse_state):
                        painter.fillRect(rect, bar_col)

        painter.end()

    # ── Shared animation clock ────────────────────────────────────────────────

    def _apply_global_animation_state(self):
        if self._game_active:
            self._quarter_pulse_state = PlayerCard._shared_pulse_state
        else:
            self._quarter_pulse_state = False

        if (self._game_active or self._game_break) and self._ot_period > 0:
            self._ot_label_show_text = PlayerCard._shared_ot_label_show_text
        else:
            self._ot_label_show_text = True

        if self._current_anim == 'idle':
            self._apply_idle_frame()

        if self._current_anim == 'idle' or self._game_active or self._ot_period > 0:
            self.update()

    # ── Idle animation ────────────────────────────────────────────────────────

    def _start_idle(self):
        anim = sprite_loader.get_animation("idle")
        self._idle_frame_indices = anim["frames"]
        self._idle_index = 0
        raw_idle_pixmaps = sprite_loader.get_idle_frames(self.player_name, self._jersey)
        self._idle_pixmaps = [
            raw_idle_pixmaps[index]
            for index in self._idle_frame_indices
            if 0 <= index < len(raw_idle_pixmaps)
        ]
        self._current_anim = 'idle'
        if self._idle_pixmaps:
            self._apply_idle_frame(force=True)

    def _apply_idle_frame(self, force: bool = False):
        if not self._idle_pixmaps:
            return
        phase_index = PlayerCard._shared_idle_phase % len(self._idle_pixmaps)
        if force or phase_index != self._idle_index:
            self._idle_index = phase_index
            self._sprite_label.setPixmap(self._idle_pixmaps[self._idle_index])

    # ── Event animation ───────────────────────────────────────────────────────

    def animate(self, animation_name: str):
        anim = sprite_loader.get_animation(animation_name)
        self._frame_list   = anim["frames"]
        self._frame_index  = 0
        self._current_anim = animation_name
        fps = anim.get("fps", 8)

        if animation_name == 'madeShot':
            self._anim_pixmaps = sprite_loader.get_made_shot_frames(self.player_name, self._jersey)
        elif animation_name == 'missedShot':
            made_anim = sprite_loader.get_animation('madeShot')
            made_pixmaps = sprite_loader.get_made_shot_frames(self.player_name, self._jersey)
            missed_pixmaps = sprite_loader.get_missed_shot_frames()

            stitched = []
            for idx in made_anim.get('frames', [])[:4]:
                if 0 <= idx < len(made_pixmaps):
                    stitched.append(made_pixmaps[idx])

            for idx in anim.get('frames', []):
                if 0 <= idx < len(missed_pixmaps):
                    stitched.append(missed_pixmaps[idx])

            self._anim_pixmaps = stitched if stitched else missed_pixmaps
            self._frame_list = list(range(len(self._anim_pixmaps)))
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
        raw_idle_pixmaps = sprite_loader.get_idle_frames(self.player_name, self._jersey)
        self._idle_pixmaps = [
            raw_idle_pixmaps[index]
            for index in getattr(self, '_idle_frame_indices', [0, 4])
            if 0 <= index < len(raw_idle_pixmaps)
        ]
        self._idle_index = 0

    def update_points(self, new_points: float):
        self.points = new_points
        if PlayerCard._current_view != 'LIVE':
            self._refresh_display()

    def set_live_data(self, data: dict):
        self._live_data   = data
        self._today_stats = data
        self._fouls       = int(data.get('PF', 0))
        self._on_court    = bool(data.get('on_court', False))

        status   = data.get('game_status', '')
        headline = data.get('game_headline', '')

        _BREAK_STATUSES     = {'STATUS_HALFTIME', 'STATUS_END_PERIOD', 'STATUS_INTERMISSION'}
        self._game_active   = status == 'STATUS_IN_PROGRESS'
        self._game_break    = status in _BREAK_STATUSES
        self._game_finished = status == 'STATUS_FINAL'

        # debug
        print(f"[Card] {self.player_name} headline='{headline}' quarter={self._quarter} ot={self._ot_period} active={self._game_active} break={self._game_break}")

        self._quarter   = 0
        self._ot_period = 0
        if self._game_active or self._game_finished or self._game_break:
            import re
            h = headline.upper()
            if 'OT' in h:
                m = re.search(r'(\d*)OT', h)
                self._ot_period = int(m.group(1)) if m and m.group(1) else 1
                self._quarter   = 4
            elif status == 'STATUS_HALFTIME':
                self._quarter = 2
            else:
                m = re.search(r'(\d+)(?:ST|ND|RD|TH)', h)
                if m:
                    self._quarter = min(int(m.group(1)), 4)
                elif self._game_finished:
                    self._quarter = 4

        self._quarter_pulse_state = PlayerCard._shared_pulse_state if self._game_active else False
        self._ot_label_show_text = PlayerCard._shared_ot_label_show_text if (self._game_active and self._ot_period > 0) else True

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
        ACTIVE_STATUSES = {
            'STATUS_IN_PROGRESS', 'STATUS_HALFTIME',
            'STATUS_END_PERIOD', 'STATUS_INTERMISSION',
        }

        no_game    = fpts is None or status == ''
        is_injured = self._injury_status in (
            'OUT', 'INJURY_RESERVE', 'QUESTIONABLE', 'DAY_TO_DAY', 'DOUBTFUL', 'PROBABLE'
        )

        # debug
        print(f"[Refresh] {self.player_name} no_game={no_game} injured={is_injured} status={status} fpts={fpts}")

        
        if self._injury_status in ('OUT', 'INJURY_RESERVE'):
            text_color = '#cf2354'
        elif is_injured:
            text_color = '#f38ba8'
        elif no_game:
            text_color = '#929EAF'
        else:
            text_color = '#000A14'

        self._points_label.setStyleSheet(f"color: {text_color}; background: transparent;")

        self._name_label.set_text_color(text_color)

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
            self._points_label.setText(f"{int(pts)}/{int(reb)}/{int(ast)}")

        # Name label text
        if status in ACTIVE_STATUSES:
            self._name_label.setText(self._short_name)
        else:
            self._name_label.setText(self._short_name)

        self._start_name_scroll()
        self.update()

    # ── Name scroll ───────────────────────────────────────────────────────────

    def _setup_name_scroll(self):
        self._scroll_timer       = QTimer()
        self._scroll_timer.timeout.connect(self._tick_name_scroll)
        self._scroll_offset      = 0
        self._scroll_min         = NAME_LABEL_LEFT_PADDING
        self._scroll_direction   = 1
        self._scroll_pausing     = False
        self._scroll_pause_ticks = 0
        self._name_needs_scroll  = False

    def _start_name_scroll(self, force_reset: bool = False):
        fm          = self._name_label.fontMetrics()
        text_width  = fm.horizontalAdvance(self._name_label.text())
        label_width = self._name_label.width()
        if text_width > label_width:
            scroll_max = text_width - label_width + NAME_LABEL_LEFT_PADDING
            if (
                not force_reset
                and self._name_needs_scroll
                and getattr(self, '_scroll_max', None) == scroll_max
                and self._scroll_timer.isActive()
            ):
                return

            self._name_needs_scroll  = True
            self._scroll_offset      = self._scroll_min
            self._scroll_direction   = 1
            self._scroll_pausing     = False
            self._scroll_pause_ticks = 0
            self._scroll_max         = scroll_max
            self._name_label.set_scroll_enabled(True)
            self._name_label.set_scroll_offset(self._scroll_offset)
            self._scroll_timer.start(NAME_SCROLL_FPS)
        else:
            self._name_needs_scroll = False
            self._scroll_timer.stop()
            self._name_label.set_scroll_enabled(False)
            self._name_label.set_scroll_offset(0)

    def _tick_name_scroll(self):
        if self._scroll_pausing:
            self._scroll_pause_ticks -= 1
            if self._scroll_pause_ticks <= 0:
                self._scroll_pausing = False
            return

        self._scroll_offset += self._scroll_direction * NAME_SCROLL_SPEED
        self._name_label.set_scroll_offset(self._scroll_offset)

        if self._scroll_offset >= self._scroll_max:
            self._scroll_offset    = self._scroll_max
            self._scroll_direction = -1
            self._scroll_pausing   = True
            self._scroll_pause_ticks = NAME_SCROLL_PAUSE
        elif self._scroll_offset <= self._scroll_min:
            self._scroll_offset    = self._scroll_min
            self._scroll_direction = 1
            self._scroll_pausing   = True
            self._scroll_pause_ticks = NAME_SCROLL_PAUSE


def _load_pixel_font(size: int = 8) -> QFont:
    font_id  = QFontDatabase.addApplicationFont(FONT_PATH)
    families = QFontDatabase.applicationFontFamilies(font_id)
    return QFont(families[0], size) if families else QFont("Courier", size)