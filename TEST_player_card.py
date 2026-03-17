"""
Standalone visual test for player card rendering experiments.

Experiments shown:
  - Foul indicators: filled circles (dots) instead of rectangle bars,
    hollow outlines for unused slots
  - Side labels: "FLS" / "QTR" rotated 90° outside the card border
  - OT bar layout: 4 completed-quarter bars + 1 OT bar with alternating "OT"/"N" label
  - Disappear-style pulse on the current quarter / OT bar during active play

Run with:
    python TEST_player_card.py
"""

from __future__ import annotations

import sys
import os

from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QFontDatabase, QFont, QBrush

FONT_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'fonts', 'pixel.ttf')

GLOBAL_TICK_INTERVAL  = 800   # ms per tick
OT_LABEL_SWITCH_TICKS = 2     # alternate OT label every N ticks

# ── Card / widget dimensions ──────────────────────────────────────────────────
CARD_W    = 64      # card border box width  (matches production)
CARD_H    = 90      # card border box height (matches production)
LABEL_PAD = 13      # px on each side of card reserved for rotated side labels
TOP_PAD   = 14      # extra vertical room so the OT label above the top bar fits
WIDGET_W  = CARD_W + LABEL_PAD * 2   # 90
WIDGET_H  = CARD_H + TOP_PAD  * 2    # 118


def _load_pixel_font(size: int = 6) -> QFont:
    font_id  = QFontDatabase.addApplicationFont(FONT_PATH)
    families = QFontDatabase.applicationFontFamilies(font_id)
    return QFont(families[0], size) if families else QFont("Courier", size)


# ── Card widget ───────────────────────────────────────────────────────────────

class PlayerCardTestCard(QWidget):
    """
    Minimal card that renders the dot + rotated-label visual experiment.

    Parameters
    ----------
    label       : Caption shown below the card in the test window.
    quarter     : Current / last-completed quarter (1–4).
    ot_period   : 0 = no OT;  1 = OT1;  2 = OT2;  etc.
    game_active : True while the clock is running (current bar pulses).
    game_break  : True between periods (bars shown solid, no pulse).
    fouls       : Personal foul count to display (0–6).
    """

    _global_timer: QTimer | None = None
    _tick_count:   int           = 0
    _instances:    list          = []

    def __init__(self, label: str, quarter: int, ot_period: int,
                 game_active: bool, game_break: bool, fouls: int = 2,
                 injury_status: str = ""):
        super().__init__()
        self.setFixedSize(WIDGET_W, WIDGET_H)

        self._quarter     = quarter
        self._ot_period   = ot_period
        self._game_active = game_active
        self._game_break  = game_break
        self._fouls       = fouls
        self._injury_status = injury_status.upper().strip()
        self._border_phase = 0

        # Shared animation state (driven by global tick)
        self._pulse_state        = False
        self._ot_label_show_text = True

        PlayerCardTestCard._instances.append(self)
        PlayerCardTestCard._ensure_timer()

    # ── Global tick ───────────────────────────────────────────────────────────

    @classmethod
    def _ensure_timer(cls) -> None:
        if cls._global_timer is None:
            cls._global_timer = QTimer()
            cls._global_timer.timeout.connect(cls._on_tick)
            cls._global_timer.start(GLOBAL_TICK_INTERVAL)

    @classmethod
    def _on_tick(cls) -> None:
        cls._tick_count += 1
        t = cls._tick_count
        shared_pulse = bool(t % 2)
        shared_ot    = bool((t // OT_LABEL_SWITCH_TICKS) % 2 == 0)
        for card in list(cls._instances):
            card._border_phase = t
            if card._injury_status in {"OUT", "INJURY_RESERVE", "DTD", "DAY_TO_DAY"}:
                card.update()
            if card._game_active:
                card._pulse_state        = shared_pulse
                card._ot_label_show_text = shared_ot
                card.update()
            elif card._game_break and card._ot_period > 0:
                card._ot_label_show_text = shared_ot
                card.update()

    def _injury_border_config(self) -> tuple[str | None, str | None]:
        if self._injury_status in {"OUT", "INJURY_RESERVE"}:
            return "O", "#cf2354"
        if self._injury_status in {"DTD", "DAY_TO_DAY"}:
            return "DTD", "#f38ba8"
        return None, None

    def _draw_rotating_text_border(self, p: QPainter, bg: QRect, text: str, color: str) -> None:
        # Build clockwise anchor points around the rectangle perimeter.
        step = 8
        pts: list[tuple[QPoint, int]] = []

        for x in range(bg.left() + 4, bg.right() - 3, step):
            pts.append((QPoint(x, bg.top() + 1), 0))
        for y in range(bg.top() + 4, bg.bottom() - 3, step):
            pts.append((QPoint(bg.right() - 1, y), 90))
        for x in range(bg.right() - 4, bg.left() + 3, -step):
            pts.append((QPoint(x, bg.bottom() - 1), 180))
        for y in range(bg.bottom() - 4, bg.top() + 3, -step):
            pts.append((QPoint(bg.left() + 1, y), -90))

        if not pts:
            return

        p.save()
        p.setFont(_load_pixel_font(5))
        p.setPen(QColor(color))

        token = text
        token_w = max(10, p.fontMetrics().horizontalAdvance(token) + 1)
        token_h = 8

        # Shift token placement each tick so the border text rotates clockwise.
        offset = self._border_phase % len(pts)
        for i in range(len(pts)):
            pt, angle = pts[(i + offset) % len(pts)]
            p.save()
            p.translate(QPointF(pt))
            p.rotate(angle)
            rect = QRect(-token_w // 2, -token_h // 2, token_w, token_h)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, token)
            p.restore()

        p.restore()

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Card border rect (centred in widget)
        ox = (self.width()  - CARD_W) // 2   # 13
        oy = (self.height() - CARD_H) // 2   # 14
        bg = QRect(ox, oy, CARD_W, CARD_H).adjusted(1, 1, -1, -1)
        # bg: left=14, top=15, right=75, bottom=102  (width=62, height=88)

        # ── Border ────────────────────────────────────────────────────────────
        if self._game_active:
            border_col = '#a6e3a1'
        elif self._game_break:
            border_col = '#000000'
        else:
            border_col = '#868686'

        injury_text, injury_color = self._injury_border_config()
        p.setBrush(Qt.BrushStyle.NoBrush)
        if injury_text:
            # Injury experiment: replace line border with rotating text border.
            self._draw_rotating_text_border(p, bg, injury_text, injury_color)
        else:
            p.setPen(QPen(QColor(border_col), 2))
            p.drawRoundedRect(bg, 8, 8)

        if not (self._game_active or self._game_break):
            p.end()
            return

        # ── Layout constants ──────────────────────────────────────────────────
        bar_w      = 2
        bar_h      = 9
        bar_gap    = 4
        row_stride = bar_h + bar_gap       # 13 px per row

        dot_r      = 3                     # foul circle radius
        dot_stride = row_stride            # keep same vertical rhythm as bars

        bar_bottom_y = bg.bottom() - 4    # shared bottom anchor for all columns

        # x positions: dots flush to left inner edge, bars flush to right inner edge
        dot_cx      = bg.left()  + 4 + dot_r    # circle centre-x  (~20)
        bar_x_right = bg.right() - 4 - bar_w    # quarter bar left edge (~69)

        # ── Rotated "FLS" label — left padding strip ──────────────────────────
        mid_y    = bg.top() + bg.height() // 2
        left_cx  = ox // 2                                      # centre of left strip
        right_cx = bg.right() + (self.width() - bg.right()) // 2  # centre of right strip

        p.save()
        p.setFont(_load_pixel_font(5))
        p.setPen(QColor('#344d5c'))
        p.translate(left_cx, mid_y)
        p.rotate(-90)
        p.drawText(QRect(-18, -4, 36, 8), Qt.AlignmentFlag.AlignCenter, "FLS")
        p.restore()

        # ── Rotated "QTR" label — right padding strip ─────────────────────────
        p.save()
        p.setFont(_load_pixel_font(5))
        p.setPen(QColor('#344d5c'))
        p.translate(right_cx, mid_y)
        p.rotate(-90)
        p.drawText(QRect(-18, -4, 36, 8), Qt.AlignmentFlag.AlignCenter, "QTR")
        p.restore()

        # ── Left column: foul circles, bottom → top ───────────────────────────
        for i in range(6):
            cy = bar_bottom_y - i * dot_stride - dot_r
            if i < self._fouls:
                # Filled dot: pink for fouls 1–4, red for fouls 5–6
                fill = '#FF4444' if i >= 4 else '#f38ba8'
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(fill))
            else:
                # Hollow outline: empty foul slot
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor('#4a4a4a'), 1))
            p.drawEllipse(QPoint(dot_cx, cy), dot_r, dot_r)

        # Reset pen/brush for bar drawing
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # ── Right column: quarter bars + optional OT bar, bottom → top ────────
        bar_col = QColor('#000000')

        if self._ot_period > 0:
            # OT mode: Q1–Q4 all solid black, 5th bar = OT (pulses when active)
            for i in range(5):
                bar_y  = bar_bottom_y - i * row_stride - bar_h
                rect   = QRect(bar_x_right, bar_y, bar_w, bar_h)
                is_ot  = (i == 4)

                if is_ot:
                    # Disappear-style pulse: skip drawing on the "gap" tick
                    if not (self._game_active and not self._pulse_state):
                        p.fillRect(rect, bar_col)

                    # Alternating label above the OT bar
                    ot_text = "OT" if self._ot_label_show_text else str(self._ot_period)
                    p.save()
                    p.setFont(_load_pixel_font(5))
                    p.setPen(QColor('#000A14'))
                    lbl_rect = QRect(bar_x_right - 13, bar_y - 11, bar_w + 20, 10)
                    p.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, ot_text)
                    p.restore()
                else:
                    # Q1–Q4 are all in the past once we're in OT — draw solid
                    p.fillRect(rect, bar_col)

        else:
            # Normal mode: draw bars for quarters 1–4
            for i in range(4):
                q     = i + 1
                bar_y = bar_bottom_y - i * row_stride - bar_h
                rect  = QRect(bar_x_right, bar_y, bar_w, bar_h)

                if q < self._quarter:
                    # Past quarter: always solid
                    p.fillRect(rect, bar_col)
                elif q == self._quarter:
                    # Current quarter: disappear-style pulse during active play
                    if not (self._game_active and not self._pulse_state):
                        p.fillRect(rect, bar_col)
                # q > self._quarter: future quarter, no bar

        p.end()


# ── Test window ───────────────────────────────────────────────────────────────

class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Player Card Visual Test  —  TEST_player_card.py")
        self.setStyleSheet("background-color: #D8E2F0;")

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(24, 24, 24, 24)

        cases = [
            dict(label="Q2 Active\n(normal)",  quarter=2, ot_period=0, game_active=True,  game_break=False, fouls=2),
            dict(label="End of Q3\n(break)",   quarter=3, ot_period=0, game_active=False, game_break=True,  fouls=4),
            dict(label="OT1\nActive",          quarter=4, ot_period=1, game_active=True,  game_break=False, fouls=5),
            dict(label="OT1\nBreak",           quarter=4, ot_period=1, game_active=False, game_break=True,  fouls=1),
            dict(label="OT2\nActive",          quarter=4, ot_period=2, game_active=True,  game_break=False, fouls=3),
            dict(label="OT3\nBreak",           quarter=4, ot_period=3, game_active=False, game_break=True,  fouls=0),
            dict(label="OUT Border\nClockwise", quarter=2, ot_period=0, game_active=True,  game_break=False, fouls=2, injury_status="OUT"),
            dict(label="DTD Border\nClockwise", quarter=2, ot_period=0, game_active=True,  game_break=False, fouls=2, injury_status="DTD"),
        ]

        for case in cases:
            col = QVBoxLayout()
            col.setSpacing(4)
            col.setAlignment(Qt.AlignmentFlag.AlignTop)

            card = PlayerCardTestCard(**case)
            col.addWidget(card)

            lbl = QLabel(case['label'])
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(_load_pixel_font(5))
            lbl.setStyleSheet("color: #000A14;")
            col.addWidget(lbl)

            main_layout.addLayout(col)

        self.adjustSize()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = TestWindow()
    win.show()
    sys.exit(app.exec())
