from PyQt6.QtWidgets import QWidget, QHBoxLayout
from PyQt6.QtCore import Qt
from ui.player_card import PlayerCard
from typing import List


class RosterView(QWidget):
    def __init__(self, players=None, full_players=None):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._cards: dict[int, PlayerCard] = {}
        self._show_full_roster = False
        self._starter_players = players or []
        self._full_players = full_players or players or []

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(8)

        if players:
            self._build_roster(players)

    def _build_roster(self, players: list):
        for i in reversed(range(self._layout.count())):
            widget = self._layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self._cards.clear()

        for player in players:
            card = PlayerCard(
                player_name=player.name,
                position=player.position,
                points=player.points_this_week,
                nba_team=getattr(player, 'nba_team', '')
            )
            self._cards[player.player_id] = card
            self._layout.addWidget(card)
        
    def get_card(self, player_id: int):
        """Used by AnimationTrigger to find the right card for an event."""
        return self._cards.get(player_id)

    def trigger_animation(self, player_id: int, animation_name: str):
        """Direct animation trigger — will be used once sprites are ready."""
        card = self._cards.get(player_id)
        if card:
            card.animate(animation_name)

    def update_points(self, player_id: int, new_points: float):
        card = self._cards.get(player_id)
        if card:
            card.update_points(new_points)
            
    def refresh_roster(self, players: list):
        self._build_roster(players)

    def toggle_roster_size(self):
        self._show_full_roster = not self._show_full_roster
        if self._show_full_roster:
            self._build_roster(self._full_players)
        else:
            self._build_roster(self._starter_players)