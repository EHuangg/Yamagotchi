from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QPropertyAnimation, QByteArray, QEasingCurve, QRect
from PyQt6.QtGui import QFontDatabase, QFont, QPainter
from events.event_bus import event_bus
import os

FONT_PATH = os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts', 'pixel.ttf')

class MatchupPanel(QWidget):
    PANEL_HEIGHT = 36

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._roster_widget = None
        self._anim = None
        self._slide_anim = None
        self._expanded = False
        self._matchup_data = {}
        self._team_cycle_cb = None  # set by desktop_widget

        self._setup_font()
        self._build_ui()
        self.hide()

        event_bus.matchup_updated.connect(self._on_matchup_updated)

    def _setup_font(self):
        font_id = QFontDatabase.addApplicationFont(FONT_PATH)
        families = QFontDatabase.applicationFontFamilies(font_id)
        self._font_sm = QFont(families[0], 5) if families else QFont("Courier", 6)
        self._font_md = QFont(families[0], 7) if families else QFont("Courier", 8)

    def _build_ui(self):
        # Left arrow
        self._btn_prev = QPushButton("◀")
        self._btn_prev.setFixedSize(22, 22)
        self._btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_prev.setStyleSheet("""
            QPushButton {
                background-color: rgba(20, 20, 35, 220);
                color: #6c7086;
                border: 1px solid #45475a;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: rgba(60, 60, 90, 220);
                color: #cdd6f4;
                border: 1px solid #6c7086;
            }
        """)
        self._btn_prev.clicked.connect(self._on_prev)

        # Right arrow
        self._btn_next = QPushButton("▶")
        self._btn_next.setFixedSize(22, 22)
        self._btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_next.setStyleSheet("""
            QPushButton {
                background-color: rgba(20, 20, 35, 220);
                color: #6c7086;
                border: 1px solid #45475a;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: rgba(60, 60, 90, 220);
                color: #cdd6f4;
                border: 1px solid #6c7086;
            }
        """)
        self._btn_next.clicked.connect(self._on_next)

        # Team name label
        self._team_name_label = QLabel("—")
        self._team_name_label.setFont(self._font_sm)
        self._team_name_label.setStyleSheet("color: #cdd6f4; background: transparent; border: none;")

        # Score labels
        self._my_score_label = QLabel("0.0")
        self._my_score_label.setFont(self._font_md)
        self._my_score_label.setStyleSheet("color: #FFD700; background: transparent; border: none;")
        self._my_score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        vs_label = QLabel("vs")
        vs_label.setFont(self._font_sm)
        vs_label.setStyleSheet("color: #45475a; background: transparent; border: none;")

        self._opp_score_label = QLabel("0.0")
        self._opp_score_label.setFont(self._font_md)
        self._opp_score_label.setStyleSheet("color: #6c7086; background: transparent; border: none;")
        self._opp_score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._opp_name_label = QLabel("—")
        self._opp_name_label.setFont(self._font_sm)
        self._opp_name_label.setStyleSheet("color: #cdd6f4; background: transparent; border: none;")

        # Expandable center widget
        self._expand_widget = QWidget()
        self._expand_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._expand_widget.setMaximumWidth(0)
        self._expand_widget.hide()
        expand_layout = QHBoxLayout(self._expand_widget)
        expand_layout.setContentsMargins(0, 0, 0, 0)
        expand_layout.setSpacing(8)
        expand_layout.addWidget(self._my_score_label)
        expand_layout.addWidget(vs_label)
        expand_layout.addWidget(self._opp_score_label)
        expand_layout.addWidget(self._opp_name_label)

        # Box — team name + expandable scores
        self._box = QWidget()
        self._box.setFixedWidth(340)  # ← now after _box is created
        self._box.setStyleSheet("""
            background-color: rgba(20, 20, 35, 220);
            border-radius: 8px;
            border: 1px solid #45475a;
        """)
        self._box.setCursor(Qt.CursorShape.PointingHandCursor)
        self._box.mousePressEvent = lambda e: self._toggle_expand()
        self._box_layout = QHBoxLayout(self._box)
        self._box_layout.setContentsMargins(12, 4, 12, 4)
        self._box_layout.setSpacing(8)
        self._box_layout.addWidget(self._team_name_label)
        self._box_layout.addWidget(self._expand_widget)

        # Outer layout
        outer = QHBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(6)
        outer.addWidget(self._btn_prev)
        outer.addStretch()
        outer.addWidget(self._box)
        outer.addStretch()
        outer.addWidget(self._btn_next)

    def _toggle_expand(self):
        self._expanded = not self._expanded
        if self._expanded:
            self._animate_expand(True)
        else:
            self._animate_expand(False)

    def _animate_expand(self, expand: bool):
        if self._slide_anim:
            self._slide_anim.stop()
            try:
                self._slide_anim.finished.disconnect()
            except Exception:
                pass

        self._slide_anim = QPropertyAnimation(
            self._expand_widget, QByteArray(b"maximumWidth")
        )
        self._slide_anim.setDuration(200)
        self._slide_anim.setEasingCurve(
            QEasingCurve.Type.OutCubic if expand else QEasingCurve.Type.InCubic
        )

        if expand:
            self._expand_widget.show()
            self._slide_anim.setStartValue(0)
            self._slide_anim.setEndValue(240)
        else:
            self._slide_anim.setStartValue(self._expand_widget.width())
            self._slide_anim.setEndValue(0)
            self._slide_anim.finished.connect(self._expand_widget.hide)

        self._slide_anim.start()

    def _on_matchup_updated(self, data: dict):
        if not data:
            self._team_name_label.setText("—")
            self._my_score_label.setText("—")
            self._opp_score_label.setText("—")
            self._opp_name_label.setText("BYE")
            return

        self._matchup_data = data
        self._team_name_label.setText(data.get('my_team', '—'))

        opp_team = data.get('opp_team', '')
        if not opp_team or opp_team == 'BYE':
            # Bye week — we have the team name but no opponent
            self._my_score_label.setText("—")
            self._opp_score_label.setText("—")
            self._opp_name_label.setText("BYE")
            self._my_score_label.setStyleSheet("color: #6c7086; background: transparent; border: none;")
            self._opp_score_label.setStyleSheet("color: #6c7086; background: transparent; border: none;")
            return

        self._my_score_label.setText(f"{data.get('my_score', 0.0):.1f}")
        self._opp_score_label.setText(f"{data.get('opp_score', 0.0):.1f}")
        self._opp_name_label.setText(opp_team)

        my_score  = data.get('my_score',  0.0)
        opp_score = data.get('opp_score', 0.0)
        if my_score > opp_score:
            self._my_score_label.setStyleSheet("color: #FFD700; background: transparent; border: none;")
            self._opp_score_label.setStyleSheet("color: #6c7086; background: transparent; border: none;")
        elif opp_score > my_score:
            self._opp_score_label.setStyleSheet("color: #FFD700; background: transparent; border: none;")
            self._my_score_label.setStyleSheet("color: #6c7086; background: transparent; border: none;")
        else:
            self._my_score_label.setStyleSheet("color: #cdd6f4; background: transparent; border: none;")
            self._opp_score_label.setStyleSheet("color: #cdd6f4; background: transparent; border: none;")
            
    def _on_prev(self):
        if self._team_cycle_cb:
            self._team_cycle_cb('prev')

    def _on_next(self):
        if self._team_cycle_cb:
            self._team_cycle_cb('next')

    def paintEvent(self, event):
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.end()

    def show_panel(self, roster_widget: QWidget):
        """Call once on startup to position and show permanently."""
        self._roster_widget = roster_widget
        self._reposition(roster_widget)
        self.show()
        self.raise_()

    def _reposition(self, roster_widget: QWidget):
        geo = roster_widget.frameGeometry()
        self.setGeometry(geo.x(), geo.y() - self.PANEL_HEIGHT, geo.width(), self.PANEL_HEIGHT)

    def update_position(self, roster_widget: QWidget):
        """Called by desktop_widget.moveEvent to track movement."""
        self._reposition(roster_widget)