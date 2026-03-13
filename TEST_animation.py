import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QComboBox, QPushButton, QLabel
)
from PyQt6.QtCore import Qt, QTimer

app = QApplication(sys.argv)

from ui.sprite_loader import sprite_loader, NBA_TEAM_JERSEY_MAP
from ui.player_card import PlayerCard

sprite_loader.ensure_loaded()
sprite_loader.ensure_loaded()
sprite_loader._loaded = False  # force reload to pick up block frames
sprite_loader.ensure_loaded()

ALL_TEAMS = list(NBA_TEAM_JERSEY_MAP.keys())

# Build window
window = QMainWindow()
window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

central = QWidget()
central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
vbox = QVBoxLayout(central)
vbox.setContentsMargins(20, 20, 20, 20)
vbox.setSpacing(12)

# Controls bar
controls = QWidget()
controls.setStyleSheet("background-color: rgba(30,30,46,200); border-radius: 8px;")
controls_layout = QHBoxLayout(controls)
controls_layout.setContentsMargins(12, 8, 12, 8)
controls_layout.setSpacing(10)

label = QLabel("Animation:")
label.setStyleSheet("color: white; font-size: 13px;")
controls_layout.addWidget(label)

combo = QComboBox()
combo.addItems(["madeShot", "block", "idle"])
combo.setStyleSheet("""
    QComboBox {
        background-color: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 13px;
        min-width: 120px;
    }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView {
        background-color: #313244;
        color: #cdd6f4;
        selection-background-color: #45475a;
    }
""")
controls_layout.addWidget(combo)

play_btn = QPushButton("▶ Play Once")
play_btn.setStyleSheet("""
    QPushButton {
        background-color: #89b4fa;
        color: #1e1e2e;
        border-radius: 4px;
        padding: 6px 16px;
        font-weight: bold;
        font-size: 13px;
    }
    QPushButton:hover { background-color: #b4d0ff; }
""")
controls_layout.addWidget(play_btn)

close_btn = QPushButton("✕ Close")
close_btn.setStyleSheet("""
    QPushButton {
        background-color: #f38ba8;
        color: #1e1e2e;
        border-radius: 4px;
        padding: 6px 16px;
        font-weight: bold;
        font-size: 13px;
    }
    QPushButton:hover { background-color: #ff8ba8; }
""")
close_btn.clicked.connect(app.quit)
controls_layout.addWidget(close_btn)

controls_layout.addStretch()
vbox.addWidget(controls)

# 3 rows of 10 cards
all_cards = []
for row in range(3):
    row_widget = QWidget()
    row_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    hbox = QHBoxLayout(row_widget)
    hbox.setContentsMargins(0, 0, 0, 0)
    hbox.setSpacing(8)
    for col in range(10):
        idx = row * 10 + col
        team_abbr = ALL_TEAMS[idx]
        card = PlayerCard(player_name=f"Player {idx+1}", position="SF", nba_team=team_abbr)
        hbox.addWidget(card)
        all_cards.append(card)
    vbox.addWidget(row_widget)

window.setCentralWidget(central)
window.adjustSize()
window.show()

def play_selected():
    anim = combo.currentText()
    for card in all_cards:
        if anim == "idle":
            card._start_idle()
        else:
            card.animate(anim)

play_btn.clicked.connect(play_selected)

sys.exit(app.exec())