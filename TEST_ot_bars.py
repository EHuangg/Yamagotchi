"""
Standalone visual test for OT bar rendering on player cards.

Demonstrates the proposed OT bar layout before integration into player_card.py:
  - 4 regular quarter bars (all solid green when in OT)
  - 5th bar for the OT period
  - Small label above the 5th bar showing which OT ("OT" for OT1, "2" for OT2, etc.)
  - 5th bar pulses when the game is actively in OT, solid during a break

Also shows normal in-quarter and between-quarter states for comparison.

Run with:
    python TEST_ot_bars.py
"""

import sys
import os

from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QFontDatabase, QFont

FONT_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'fonts', 'pixel.ttf')
QUARTER_PULSE_INTERVAL = 1600  # ms
OT_LABEL_SWITCH_INTERVAL = 3200  # ms


def _load_pixel_font(size: int = 6) -> QFont:
    font_id  = QFontDatabase.addApplicationFont(FONT_PATH)
    families = QFontDatabase.applicationFontFamilies(font_id)
    return QFont(families[0], size) if families else QFont("Courier", size)


class OTBarTestCard(QWidget):
    """
    Minimal self-contained widget that draws the proposed OT bar layout.
    Tweak the paintEvent here, then port the logic back to player_card.py.

    Parameters
    ----------
    label       : Caption shown below the card.
    quarter     : Current / most-recently-completed quarter (1-4).
    ot_period   : 0 = no OT; 1 = OT1; 2 = OT2; etc.
    game_active : True while the clock is running (pulses the current bar).
    game_break  : True during a break between periods (bars shown solid, no pulse).
    fouls       : Number of personal fouls (left red bars), for visual context.
    """

    def __init__(self, label: str, quarter: int, ot_period: int,
                 game_active: bool, game_break: bool, fouls: int = 2):
        super().__init__()
        self.setFixedSize(76, 94)

        self._quarter     = quarter
        self._ot_period   = ot_period
        self._game_active = game_active
        self._game_break  = game_break
        self._fouls       = fouls
        self._pulse_state = False
        self._ot_label_show_text = True

        if game_active:
            self._pulse_timer = QTimer(self)
            self._pulse_timer.timeout.connect(self._tick_pulse)
            self._pulse_timer.start(QUARTER_PULSE_INTERVAL)

            if ot_period > 0:
                self._ot_label_timer = QTimer(self)
                self._ot_label_timer.timeout.connect(self._tick_ot_label)
                self._ot_label_timer.start(OT_LABEL_SWITCH_INTERVAL)

    # ── Pulse ─────────────────────────────────────────────────────────────────

    def _tick_pulse(self):
        self._pulse_state = not self._pulse_state
        self.update()

    def _tick_ot_label(self):
        self._ot_label_show_text = not self._ot_label_show_text
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # ── Border ────────────────────────────────────────────────────────────
        if self._game_active:
            border_color = '#a6e3a1'   # green: clock running
        elif self._game_break:
            border_color = '#000000'   # black: between periods
        else:
            border_color = '#868686'   # grey:  no game

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(border_color), 2))
        x = (self.width() - 72) // 2
        y = (self.height() - 90) // 2
        bg_rect = QRect(x, y, 72, 90).adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(bg_rect, 8, 8)

        if not (self._game_active or self._game_break):
            painter.end()
            return

        # ── Bar constants ─────────────────────────────────────────────────────
        bar_w        = 2
        bar_h        = 9
        bar_gap      = 4
        bar_x_left   = bg_rect.left() + 3
        bar_x_right  = bg_rect.right() - 3 - bar_w
        bar_bottom_y = bg_rect.bottom() - 4

        # ── Left bars: personal fouls (red), bottom→top ───────────────────────
        for i in range(6):
            bar_y = bar_bottom_y - i * (bar_h + bar_gap) - bar_h
            rect  = QRect(bar_x_left, bar_y, bar_w, bar_h)
            if i < self._fouls:
                color = '#FF0000' if i >= 4 else '#f38ba8'
                painter.fillRect(rect, QColor(color))

        # ── Right bars: quarters + optional OT, bottom→top ───────────────────
        if self._ot_period > 0:
            # ── OT mode: 4 solid quarter bars + 1 OT bar ─────────────────────
            total_bars = 5
            for i in range(total_bars):
                bar_y    = bar_bottom_y - i * (bar_h + bar_gap) - bar_h
                rect     = QRect(bar_x_right, bar_y, bar_w, bar_h)
                is_ot_bar = (i == total_bars - 1)  # topmost bar is OT

                if is_ot_bar:
                    # Pulse during active OT; solid during break
                    if self._game_active:
                        color = '#a6e3a1' if self._pulse_state else '#d4f0d4'
                    else:
                        color = '#a6e3a1'
                    painter.fillRect(rect, QColor(color))

                    # Alternate between "OT" and the overtime count to keep it readable.
                    ot_label = "OT" if self._ot_label_show_text else str(self._ot_period)
                    painter.setPen(QColor('#000A14'))
                    painter.setFont(_load_pixel_font(5))
                    label_rect = QRect(bar_x_right - 13, bar_y - 11, bar_w + 20, 10)
                    painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, ot_label)
                else:
                    # All 4 regular quarter bars are fully completed → solid green
                    painter.fillRect(rect, QColor('#a6e3a1'))

        else:
            # ── Normal mode: up to 4 quarter bars ────────────────────────────
            for i in range(4):
                quarter = i + 1
                bar_y   = bar_bottom_y - i * (bar_h + bar_gap) - bar_h
                rect    = QRect(bar_x_right, bar_y, bar_w, bar_h)

                if quarter < self._quarter:
                    painter.fillRect(rect, QColor('#a6e3a1'))
                elif quarter == self._quarter:
                    if self._game_active:
                        color = '#a6e3a1' if self._pulse_state else '#d4f0d4'
                    else:
                        color = '#a6e3a1'  # solid during break
                    painter.fillRect(rect, QColor(color))

        painter.end()


# ── Test window ───────────────────────────────────────────────────────────────

class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OT Bar Test  —  TEST_ot_bars.py")
        self.setStyleSheet("background-color: #A7C2E5;")

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        cases = [
            dict(label="Q2 Active\n(normal)",     quarter=2, ot_period=0, game_active=True,  game_break=False),
            dict(label="End of Q3\n(break)",       quarter=3, ot_period=0, game_active=False, game_break=True),
            dict(label="OT1\nActive",              quarter=4, ot_period=1, game_active=True,  game_break=False),
            dict(label="OT1\nBreak",               quarter=4, ot_period=1, game_active=False, game_break=True),
            dict(label="OT2\nActive",              quarter=4, ot_period=2, game_active=True,  game_break=False),
            dict(label="OT3\nBreak",               quarter=4, ot_period=3, game_active=False, game_break=True),
        ]

        for case in cases:
            col = QVBoxLayout()
            col.setSpacing(4)
            col.setAlignment(Qt.AlignmentFlag.AlignTop)

            card = OTBarTestCard(**case)
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
