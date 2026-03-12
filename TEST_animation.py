import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout
)
from PyQt6.QtCore import Qt, QTimer

app = QApplication(sys.argv)

from ui.sprite_loader import sprite_loader, NBA_TEAM_JERSEY_MAP
from ui.player_card import PlayerCard

sprite_loader.ensure_loaded()

# All 30 teams in order
ALL_TEAMS = list(NBA_TEAM_JERSEY_MAP.keys())  # 30 teams

# Build window
window = QMainWindow()
window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

central = QWidget()
central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
vbox = QVBoxLayout(central)
vbox.setContentsMargins(20, 20, 20, 20)
vbox.setSpacing(12)

all_cards = []

# 3 rows of 10
for row in range(3):
    row_widget = QWidget()
    row_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    hbox = QHBoxLayout(row_widget)
    hbox.setContentsMargins(0, 0, 0, 0)
    hbox.setSpacing(8)

    for col in range(10):
        idx = row * 10 + col
        team_abbr = ALL_TEAMS[idx]
        card = PlayerCard(
            player_name=f"Player {idx+1}",
            position="SF",
            nba_team=team_abbr
        )
        hbox.addWidget(card)
        all_cards.append(card)

    vbox.addWidget(row_widget)

window.setCentralWidget(central)
window.adjustSize()
window.show()

# Fire madeShot on all cards at 1s, then loop every 4s
def fire_all():
    for card in all_cards:
        card.animate('madeShot')

QTimer.singleShot(1000, fire_all)

loop_timer = QTimer()
loop_timer.setInterval(4000)
loop_timer.timeout.connect(fire_all)
QTimer.singleShot(1000, loop_timer.start)

sys.exit(app.exec())