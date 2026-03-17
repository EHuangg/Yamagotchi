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
combo.addItems(["madeShot", "missedShot", "missedShot_stitched", "block", "idle"])
combo.setStyleSheet("""
    QComboBox {
        background-color: #000A14;
        color: #D8E2F0;
        border: 1px solid #929EAF;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 13px;
        min-width: 120px;
    }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView {
        background-color: #000A14;
        color: #D8E2F0;
        selection-background-color: #929EAF;
    }
""")
controls_layout.addWidget(combo)

play_btn = QPushButton("▶ Play Once")
play_btn.setStyleSheet("""
    QPushButton {
        background-color: #A7C2E5;
        color: #000A14;
        border-radius: 4px;
        padding: 6px 16px;
        font-weight: bold;
        font-size: 13px;
    }
    QPushButton:hover { background-color: #D8E2F0; }
""")
controls_layout.addWidget(play_btn)

close_btn = QPushButton("✕ Close")
close_btn.setStyleSheet("""
    QPushButton {
        background-color: #c85977;
        color: #000A14;
        border-radius: 4px;
        padding: 6px 16px;
        font-weight: bold;
        font-size: 13px;
    }
    QPushButton:hover { background-color: #d97a8f; }
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


def _play_stitched_missed_shot(card: PlayerCard):
    made_anim = sprite_loader.get_animation("madeShot")
    missed_anim = sprite_loader.get_animation("missedShot")

    made_pixmaps = sprite_loader.get_made_shot_frames(card.player_name, card._jersey)
    missed_pixmaps = sprite_loader.get_missed_shot_frames()

    made_indices = made_anim.get("frames", [])[:4]
    missed_indices = missed_anim.get("frames", [])

    stitched = []
    for idx in made_indices:
        if 0 <= idx < len(made_pixmaps):
            stitched.append(made_pixmaps[idx])
    for idx in missed_indices:
        if 0 <= idx < len(missed_pixmaps):
            stitched.append(missed_pixmaps[idx])

    if not stitched:
        card.animate("missedShot")
        return

    card._anim_timer.stop()
    card._current_anim = "missedShot"
    card._anim_pixmaps = stitched
    card._frame_list = list(range(len(stitched)))
    card._frame_index = 0

    fps = missed_anim.get("fps", 6)
    card._anim_timer.start(1000 // max(1, fps))

def play_selected():
    anim = combo.currentText()
    for card in all_cards:
        if anim == "idle":
            card._start_idle()
        elif anim == "missedShot_stitched":
            _play_stitched_missed_shot(card)
        else:
            card.animate(anim)

play_btn.clicked.connect(play_selected)

sys.exit(app.exec())