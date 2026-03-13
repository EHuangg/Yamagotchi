class RosterViewShim:
    """Minimal shim so AnimationTrigger works with the new appbar layout."""
    def __init__(self, cards: dict):
        self._cards = cards

    def get_card(self, player_id: int):
        return self._cards.get(player_id)

    def update_points(self, player_id: int, new_points: float):
        card = self._cards.get(player_id)
        if card:
            card.update_points(new_points)

    def trigger_animation(self, player_id: int, animation_name: str):
        card = self._cards.get(player_id)
        if card:
            card.animate(animation_name)