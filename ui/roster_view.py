import json
import os
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QScrollArea, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QByteArray
from PyQt6.QtGui import QIcon
from ui.player_card import PlayerCard

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.json')
MODES = ['SINGLE', 'STARTERS', 'FULL']
MAX_ROW = 10


class MiniCard(QWidget):
    """Small card used in the SINGLE mode carousel."""
    def __init__(self, player, on_click, opacity=1.0):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(56, 72)
        self.player = player
        self._on_click = on_click

        from ui.sprite_loader import sprite_loader, get_jersey_for_team, _clean_player_name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtGui import QFontDatabase, QFont
        font_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts', 'pixel.ttf')
        font_id = QFontDatabase.addApplicationFont(font_path)
        families = QFontDatabase.applicationFontFamilies(font_id)
        pf = QFont(families[0], 5) if families else QFont("Courier", 5)

        # Background container
        bg = QWidget()
        bg.setStyleSheet("background-color: rgba(50,50,50,150); border-radius: 6px;")
        bg.setFixedSize(52, 68)
        bg_layout = QVBoxLayout(bg)
        bg_layout.setContentsMargins(2, 2, 2, 2)
        bg_layout.setSpacing(1)
        bg_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        sprite_lbl = QLabel()
        sprite_lbl.setFixedSize(48, 48)
        sprite_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sprite_lbl.setStyleSheet("background: transparent;")

        jersey = get_jersey_for_team(getattr(player, 'nba_team', ''))
        clean = _clean_player_name(player.name)
        frames = sprite_loader.get_idle_frames(clean, jersey)
        if frames:
            sprite_lbl.setPixmap(frames[0])

        name_lbl = QLabel(clean.split()[-1])
        name_lbl.setFont(pf)
        name_lbl.setStyleSheet("color: white; background: transparent;")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        bg_layout.addWidget(sprite_lbl)
        bg_layout.addWidget(name_lbl)
        layout.addWidget(bg)

        # Opacity effect
        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(opacity)
        self.setGraphicsEffect(effect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self.player)


class Carousel(QWidget):
    """Horizontal sliding carousel for SINGLE mode."""
    CARD_W = 56
    CARD_SPACING = 6
    VISIBLE_LEFT = 2      # full cards to the left
    PEEK_RIGHT = 28       # px of the card peeking on the right

    def __init__(self, players, current_player, on_select):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._players = players
        self._on_select = on_select
        self._current_idx = next(
            (i for i, p in enumerate(players) if p.player_id == current_player.player_id), 0
        )

        # Width: 2 full cards left + current card + peek
        total_w = (self.VISIBLE_LEFT + 1) * (self.CARD_W + self.CARD_SPACING) + self.PEEK_RIGHT
        self.setFixedWidth(total_w)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(self.CARD_SPACING)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._rebuild()

    def _opacity_for_offset(self, offset: int) -> float:
        """offset=0 is current, negative=left, positive=right (peek)."""
        if offset == 0:
            return 1.0
        elif offset == -1:
            return 0.6
        elif offset == -2:
            return 0.3
        else:
            return 0.15  # peek

    def _rebuild(self):
        # Clear
        for i in reversed(range(self._layout.count())):
            w = self._layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        # Show: [idx-2, idx-1, idx(current), idx+1(peek)]
        slots = [
            self._current_idx - 2,
            self._current_idx - 1,
            self._current_idx,
            self._current_idx + 1,
        ]
        offsets = [-2, -1, 0, 1]

        for slot, offset in zip(slots, offsets):
            if 0 <= slot < len(self._players):
                p = self._players[slot]
                opacity = self._opacity_for_offset(offset)
                mini = MiniCard(p, self._on_mini_click, opacity=opacity)
                # Clip the peek card
                if offset == 1:
                    mini.setFixedWidth(self.PEEK_RIGHT)
                self._layout.addWidget(mini)
            else:
                # Empty spacer
                from PyQt6.QtWidgets import QSpacerItem, QSizePolicy
                w = self.PEEK_RIGHT if offset == 1 else self.CARD_W
                self._layout.addSpacing(w)

    def _on_mini_click(self, player):
        self._current_idx = next(
            (i for i, p in enumerate(self._players) if p.player_id == player.player_id), 0
        )
        self._rebuild()
        self._on_select(player)


class RosterView(QWidget):
    def __init__(self, players=None, full_players=None):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._cards: dict[int, PlayerCard] = {}
        self._starter_players = players or []
        self._full_players = full_players or players or []
        self._mode = self._load_mode()
        self._single_player_id = self._load_single_player_id()
        self._carousel: Carousel | None = None
        self._carousel_open = False
        
        self._live_data_applier = None  # set by desktop_widget

        self._outer = QHBoxLayout(self)
        self._outer.setContentsMargins(10, 10, 10, 10)
        self._outer.setSpacing(0)

        # Carousel container (slides in from left)
        self._carousel_container = QWidget()
        self._carousel_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._carousel_container.setFixedWidth(0)
        self._carousel_anim = QPropertyAnimation(
            self._carousel_container, QByteArray(b"maximumWidth")
        )
        self._carousel_anim.setDuration(200)
        self._carousel_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._carousel_inner = QHBoxLayout(self._carousel_container)
        self._carousel_inner.setContentsMargins(0, 0, 6, 0)
        self._carousel_inner.setSpacing(0)

        # Main cards area
        self._cards_widget = QWidget()
        self._cards_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._cards_layout = QHBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)

        self._outer.addWidget(self._carousel_container)
        self._outer.addWidget(self._cards_widget)

        if players:
            self._build_roster(players)

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load_mode(self) -> str:
        try:
            with open(SETTINGS_PATH) as f:
                return json.load(f).get('display_mode', 'STARTERS')
        except Exception:
            return 'STARTERS'

    def _save_mode(self, mode: str):
        try:
            with open(SETTINGS_PATH) as f:
                s = json.load(f)
            s['display_mode'] = mode
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(s, f, indent=2)
        except Exception:
            pass

    def _load_single_player_id(self):
        try:
            with open(SETTINGS_PATH) as f:
                return json.load(f).get('single_player_id')
        except Exception:
            return None

    def _save_single_player_id(self, pid):
        try:
            with open(SETTINGS_PATH) as f:
                s = json.load(f)
            s['single_player_id'] = pid
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(s, f, indent=2)
        except Exception:
            pass

    # ── Build ─────────────────────────────────────────────────────────────────

    def _clear_cards(self):
        for i in reversed(range(self._cards_layout.count())):
            w = self._cards_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        self._cards.clear()

    def _make_card(self, player) -> PlayerCard:
        card = PlayerCard(
            player_name=player.name,
            position=player.position,
            points=player.points_this_week,
            nba_team=getattr(player, 'nba_team', '')
        )
        self._cards[player.player_id] = card
        return card

    def _build_roster(self, players: list):
        self._close_carousel(animate=False)
        self._clear_cards()

        if self._mode == 'SINGLE':
            self._build_single(players)
        elif self._mode == 'FULL':
            self._build_full(players)
        else:
            self._build_starters(players)

    def _build_starters(self, players: list):
        self._cards_layout.setSpacing(8)
        for player in players:
            self._cards_layout.addWidget(self._make_card(player))

    def _build_full(self, players: list):
        # Wrap into rows of MAX_ROW
        from PyQt6.QtWidgets import QVBoxLayout
        self._cards_layout.setSpacing(0)
        wrapper = QWidget()
        wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        vbox = QVBoxLayout(wrapper)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)

        row_widget = None
        row_layout = None
        for i, player in enumerate(players):
            if i % MAX_ROW == 0:
                row_widget = QWidget()
                row_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)
                vbox.addWidget(row_widget)
            card = self._make_card(player)
            row_layout.addWidget(card)

        self._cards_layout.addWidget(wrapper)

    def _build_single(self, players: list):
        if not players:
            return

        # Find the saved player or default to first
        single = next(
            (p for p in players if p.player_id == self._single_player_id),
            players[0]
        )
        self._single_player_id = single.player_id

        # Arrow button
        arrow_btn = QPushButton("◀")
        arrow_btn.setFixedSize(20, 80)
        arrow_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(50,50,50,150);
                color: white;
                border-radius: 4px;
                font-size: 10px;
                border: none;
            }
            QPushButton:hover { background-color: rgba(80,80,80,180); }
        """)
        arrow_btn.clicked.connect(self._toggle_carousel)
        self._cards_layout.addWidget(arrow_btn)
        self._arrow_btn = arrow_btn

        card = self._make_card(single)
        self._cards_layout.addWidget(card)

        # Build carousel (hidden)
        self._build_carousel(players, single)

    def _build_carousel(self, players, current_player):
        # Clear old carousel
        for i in reversed(range(self._carousel_inner.count())):
            w = self._carousel_inner.itemAt(i).widget()
            if w:
                w.setParent(None)

        self._carousel = Carousel(
            players=players,
            current_player=current_player,
            on_select=self._on_carousel_select
        )
        self._carousel_inner.addWidget(self._carousel)

    def _on_carousel_select(self, player):
        self._single_player_id = player.player_id
        self._save_single_player_id(player.player_id)

        # Swap main card
        self._clear_cards()
        # Re-add arrow + new card
        self._cards_layout.addWidget(self._arrow_btn)
        card = self._make_card(player)
        self._cards_layout.addWidget(card)

        # Reapply live data if available
        if self._live_data_applier:
            self._live_data_applier(card, player.name)

        self._close_carousel(animate=True)

    # ── Carousel animation ────────────────────────────────────────────────────

    def _toggle_carousel(self):
        if self._carousel_open:
            self._close_carousel(animate=True)
        else:
            self._open_carousel()

    def _open_carousel(self):
        if not self._carousel:
            return
        self._carousel_open = True
        target_w = self._carousel.width() + 6
        self._carousel_anim.stop()
        self._carousel_anim.setStartValue(0)
        self._carousel_anim.setEndValue(target_w)
        self._carousel_container.setMaximumWidth(0)
        self._carousel_container.show()
        self._carousel_anim.start()

    def _close_carousel(self, animate=True):
        self._carousel_open = False
        if not animate:
            self._carousel_container.setMaximumWidth(0)
            return
        self._carousel_anim.stop()
        self._carousel_anim.setStartValue(self._carousel_container.maximumWidth())
        self._carousel_anim.setEndValue(0)
        self._carousel_anim.start()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_mode(self, mode: str):
        """Called from context menu. mode = 'SINGLE' | 'STARTERS' | 'FULL'"""
        if mode not in MODES:
            return
        self._mode = mode
        self._save_mode(mode)
        players = self._starter_players if mode != 'FULL' else self._full_players
        self._build_roster(players)

    def get_card(self, player_id: int):
        return self._cards.get(player_id)

    def trigger_animation(self, player_id: int, animation_name: str):
        card = self._cards.get(player_id)
        if card:
            card.animate(animation_name)

    def update_points(self, player_id: int, new_points: float):
        card = self._cards.get(player_id)
        if card:
            card.update_points(new_points)

    def refresh_roster(self, players: list):
        self._starter_players = players
        self._build_roster(
            players if self._mode != 'FULL' else self._full_players
        )

    def toggle_roster_size(self):
        """Legacy toggle — cycles STARTERS → FULL → STARTERS."""
        if self._mode == 'STARTERS':
            self.set_mode('FULL')
        else:
            self.set_mode('STARTERS')