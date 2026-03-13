from PyQt6.QtWidgets import QLabel, QWidget
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QByteArray
from PyQt6.QtGui import QFont, QFontDatabase
from events.event_bus import event_bus
from ui.player_card import PlayerCard
import os

FONT_PATH = os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts', 'pixel.ttf')

# Maps event type → (display text, color)
EVENT_DISPLAY = {
    "POINTS_SCORED": ("📈 +pts",   "#00FF88"),
    "BIG_GAME":      ("🔥 BIG!",   "#FFD700"),
    "ZERO_WEEK":     ("😴 DNP",    "#888888"),
    "GAME_STARTED":  ("🏀 tip off","#88CCFF"),
}


class FloatingText(QWidget):
    """A temporary label that floats up above a player card then disappears."""

    def __init__(self, parent_card: QWidget, text: str, color: str):
        super().__init__(parent_card.window())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.Tool)

        # Load pixel font
        font_id = QFontDatabase.addApplicationFont(FONT_PATH)
        families = QFontDatabase.applicationFontFamilies(font_id)
        font = QFont(families[0], 7) if families else QFont("Courier", 8)

        label = QLabel(text, self)
        label.setFont(font)
        label.setStyleSheet(f"color: {color}; background: transparent;")
        label.adjustSize()
        self.resize(label.size())

        # Position above the player card
        card_pos = parent_card.mapToGlobal(QPoint(0, 0))
        start_y = card_pos.y() - 10
        end_y   = card_pos.y() - 50

        self.move(card_pos.x(), start_y)
        self.show()

        # Animate upward
        self._anim = QPropertyAnimation(self, QByteArray(b"pos"))
        self._anim.setDuration(1000)
        self._anim.setStartValue(QPoint(card_pos.x(), start_y))
        self._anim.setEndValue(QPoint(card_pos.x(), end_y))
        self._anim.start()

        # Destroy after animation
        QTimer.singleShot(1100, self.close)


class AnimationTrigger:
    """
    Subscribes to the event bus and triggers visual feedback per player.
    Holds a reference to the roster_view to find the right PlayerCard.
    """

    def __init__(self, roster_view):
        self.roster_view = roster_view
        self._subscribe()

    def _subscribe(self):
        event_bus.points_scored.connect(
            lambda pid, delta: self._handle("POINTS_SCORED", pid, delta))
        event_bus.big_game.connect(
            lambda pid, delta: self._handle("BIG_GAME", pid, delta))
        event_bus.zero_week.connect(
            lambda pid: self._handle("ZERO_WEEK", pid, 0))
        event_bus.game_started.connect(
            lambda pid, delta: self._handle("GAME_STARTED", pid, delta))
        event_bus.snapshot_updated.connect(self._handle_snapshot)
        event_bus.live_stats_updated.connect(self._handle_live_stats)

    def _handle(self, event_type: str, player_id: int, delta: float):
        card = self.roster_view.get_card(player_id)
        if not card:
            return

        # Show floating text popup
        text, color = EVENT_DISPLAY.get(event_type, ("❓", "white"))
        if delta > 0:
            text = f"{text} {delta:.1f}"
        FloatingText(card, text, color)

        # Update points display
        if delta > 0:
            new_points = card.points + delta
            card.update_points(new_points)

        # TODO: when sprites are ready, add card.animate("scoring") etc. here

    def _handle_snapshot(self, snapshot: list):
        for player in snapshot:
            # Only update points display if NOT in live mode
            # Live mode gets its data exclusively from _handle_live_stats
            if PlayerCard._current_view != 'LIVE':
                self.roster_view.update_points(player.player_id, player.points_this_week)

            card = self.roster_view.get_card(player.player_id)
            if not card:
                continue

            if player.is_playing_today and player.points_this_week > 0:
                card.set_live(True)
            elif not player.is_playing_today and player.points_this_week == 0:
                card.set_inactive("No game")
            elif not player.is_playing_today and player.points_this_week > 0:
                card.set_live(False)
                card.set_game_finished(player.points_this_week)
    
    def _handle_live_stats(self, stats: dict):
        for player_id, card in self.roster_view._cards.items():
            name = card.player_name
            if name not in stats:
                continue

            card.set_live_data(stats[name])
            data = stats[name]

            new_fpts = data.get('fantasy_pts', 0.0)
            old_fpts = getattr(card, '_last_fpts', 0.0)
            delta    = new_fpts - old_fpts

            new_fgm  = data.get('FGM', 0)
            old_fgm  = getattr(card, '_last_fgm', 0)
            new_fga  = data.get('FGA', 0)
            old_fga  = getattr(card, '_last_fga', 0)
            new_blk  = data.get('BLK', 0)
            old_blk  = getattr(card, '_last_blk', 0)

            # Animations — priority: block > madeShot > missedShot
            if new_blk > old_blk:
                card.animate('block')
            elif new_fgm > old_fgm:
                card.animate('madeShot')
            elif new_fga > old_fga:
                card.animate('missedShot')

            # Floating text + points
            if delta > 0:
                self._handle('BIG_GAME' if delta >= 8 else 'POINTS_SCORED', player_id, delta)

            card._last_fpts = new_fpts
            card._last_fgm  = new_fgm
            card._last_fga  = new_fga
            card._last_blk  = new_blk