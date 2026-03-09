from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFontDatabase, QFont
from ui.sprite_loader import sprite_loader, get_jersey_for_team
import os

FONT_PATH = os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts', 'pixel.ttf')

class PlayerCard(QWidget):
    VIEWS = ['LIVE', 'AVERAGES', 'STATLINE']
    _current_view = 'LIVE'  # shared across all instances
    _all_cards: list = []   # registry of all active cards

    def __init__(self, player_name: str, position: str, points: float = 0.0, nba_team: str = ""):
        super().__init__()
        self.player_name = player_name
        self.position = position
        self.points = points
        
        self._jersey = get_jersey_for_team(nba_team)
        ############################## DEBUG, delete later ########################################
        #print(f"[Card] {player_name} → team='{nba_team}' → jersey='{self._jersey}'")
    
        self._live_data   = {}
        self._season_avg  = 0.0
        self._today_stats = {}

        self._current_anim = "idle"
        self._frame_list = []
        self._frame_index = 0

        self._setup_font()
        self._build_ui()
        
        PlayerCard._all_cards.append(self)

        self._idle_timer = QTimer()
        self._idle_timer.timeout.connect(self._tick_idle)
        self._start_idle()

        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._tick_anim)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(80, 120)
        
                    
        
    def __del__(self):
        try:
            PlayerCard._all_cards.remove(self)
        except ValueError:
            pass

    def _setup_font(self):
        font_id = QFontDatabase.addApplicationFont(FONT_PATH)
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            self._pixel_font = QFont(families[0], 5)
        else:
            self._pixel_font = QFont("Courier", 6)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Sprite display
        self._sprite_label = QLabel()
        self._sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sprite_label.setFixedSize(64, 64)
        self._sprite_label.setStyleSheet(
            "background-color: rgba(50, 50, 50, 150); border-radius: 8px;"
        )

        # Player name — just last name to save space
        short_name = self.player_name.split(" ")[-1]
        self._name_label = QLabel(short_name)
        self._name_label.setFont(self._pixel_font)
        self._name_label.setStyleSheet("color: white; background: transparent;")
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Points display
        self._points_label = QLabel("—")
        self._points_label.setFont(self._pixel_font)
        self._points_label.setStyleSheet("color: #555555; background: transparent;")
        self._points_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._sprite_label)
        layout.addWidget(self._name_label)
        layout.addWidget(self._points_label)

    def update_points(self, new_points: float):
        self.points = new_points
        # Only refresh display if not in LIVE mode
        # LIVE mode is exclusively driven by set_live_data
        if PlayerCard._current_view != 'LIVE':
            self._refresh_display()

    # --- Idle animation (loops forever) ---
    def _start_idle(self):
        anim = sprite_loader.get_animation("idle")
        self._idle_frame_indices = anim["frames"]  # e.g. [0,1,2,3,4,5]
        self._idle_index = 0
        fps = anim.get("fps", 6)
        # Load composited frames for this player
        self._idle_pixmaps = sprite_loader.get_idle_frames(self.player_name, self._jersey)
        self._idle_timer.start(1000 // fps)
        if self._idle_pixmaps:
            self._sprite_label.setPixmap(self._idle_pixmaps[0])

    def _tick_idle(self):
        if not self._idle_pixmaps:
            return
        self._idle_index = (self._idle_index + 1) % len(self._idle_pixmaps)
        self._sprite_label.setPixmap(self._idle_pixmaps[self._idle_index])
        
    # --- Event animation (plays once, then returns to idle) ---

    def animate(self, animation_name: str):
        anim = sprite_loader.get_animation(animation_name)
        self._frame_list = anim["frames"]
        self._frame_index = 0
        fps = anim.get("fps", 8)
        self._idle_timer.stop()
        self._anim_timer.start(1000 // fps)

    def _tick_anim(self):
        if self._frame_index >= len(self._frame_list):
            self._anim_timer.stop()
            self._start_idle()
            return
        self._show_frame(self._frame_list[self._frame_index])
        self._frame_index += 1

    # --- Shared frame display ---

    def _show_frame(self, frame_index: int):
        # For event animations — still uses old sprite_loader.get_frame
        # Will be updated once event sprites are drawn
        pixmap = sprite_loader.get_frame(frame_index)
        if pixmap:
            self._sprite_label.setPixmap(pixmap)

    def set_jersey(self, jersey: str):
        """Call this to change jersey — reloads composited frames."""
        self._jersey = jersey
        self._idle_pixmaps = sprite_loader.get_idle_frames(self.player_name, self._jersey)
        self._idle_index = 0
        
    def set_live(self, is_live: bool):
        """Show a pulsing green dot when the player's game is active."""
        self._is_live = is_live
        if is_live:
            self._name_label.setStyleSheet("color: white; background: transparent;")
            self._start_pulse()
        else:
            self._stop_pulse()

    def set_inactive(self, reason: str = ""):
        """Grey out the card when player has no game today."""
        self._sprite_label.setStyleSheet(
            "background-color: rgba(30, 30, 30, 80); border-radius: 8px;"
        )
        self._name_label.setStyleSheet("color: #555555; background: transparent;")
        self._points_label.setStyleSheet("color: #555555; background: transparent;")
        if reason:
            self._points_label.setText(reason)

    def set_game_finished(self, final_points: float):
        """Show a final score badge after game ends."""
        self._points_label.setText(f"✓ {final_points:.1f}")
        self._points_label.setStyleSheet("color: #a6e3a1; background: transparent;")

    def _start_pulse(self):
        """Pulse the name label green to indicate live game."""
        if not hasattr(self, '_pulse_timer'):
            self._pulse_timer = QTimer()
            self._pulse_state = False
            self._pulse_timer.timeout.connect(self._tick_pulse)
        self._pulse_timer.start(800)

    def _stop_pulse(self):
        if hasattr(self, '_pulse_timer'):
            self._pulse_timer.stop()
        self._name_label.setStyleSheet("color: white; background: transparent;")

    def _tick_pulse(self):
        self._pulse_state = not self._pulse_state
        color = "#a6e3a1" if self._pulse_state else "white"
        self._name_label.setStyleSheet(f"color: {color}; background: transparent;")
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Advance shared view mode
            idx = PlayerCard.VIEWS.index(PlayerCard._current_view)
            PlayerCard._current_view = PlayerCard.VIEWS[(idx + 1) % len(PlayerCard.VIEWS)]
            # Refresh all cards
            for card in PlayerCard._all_cards:
                card._refresh_display()
            
    def set_live_data(self, data: dict):
        self._live_data = data
        self._today_stats = data
        # Always refresh if in LIVE or STATLINE mode
        if PlayerCard._current_view in ('LIVE', 'STATLINE'):
            self._refresh_display()

    def set_season_avg(self, avg_pts: float):
        self._season_avg = avg_pts
        if PlayerCard._current_view == 'AVERAGES':
            self._refresh_display()
 
################################################ Refresh Display Modes ###########################################################           
    def _refresh_display(self):
        mode = PlayerCard._current_view

        if mode == 'LIVE':
            fpts = self._live_data.get('fantasy_pts', None)
            status = self._live_data.get('game_status', '')

            ACTIVE_STATUSES = {'STATUS_IN_PROGRESS', 'STATUS_HALFTIME'}

            if fpts is None or status == '':
                self._points_label.setStyleSheet("color: #555555; background: transparent;")
                self._points_label.setText("—")
                self._name_label.setText(self.player_name.split()[-1])
            elif status in ACTIVE_STATUSES:
                self._points_label.setStyleSheet("color: #a6e3a1; background: transparent;")
                self._points_label.setText(f"{fpts:.1f}")
                self._name_label.setText(
                    self.player_name.split()[-1] + " 🔴" if status == 'STATUS_IN_PROGRESS'
                    else self.player_name.split()[-1] + " ⏸"
                )
            elif status == 'STATUS_FINAL':
                self._points_label.setStyleSheet("color: #FFD700; background: transparent;")
                self._points_label.setText(f"{fpts:.1f}")
                self._name_label.setText(self.player_name.split()[-1])
            else:
                self._points_label.setStyleSheet("color: #555555; background: transparent;")
                self._points_label.setText("—")
                self._name_label.setText(self.player_name.split()[-1])
                
        elif mode == 'AVERAGES':
            self._points_label.setStyleSheet("color: #89b4fa; background: transparent;")
            self._points_label.setText(f"{self._season_avg:.1f} avg")
            self._name_label.setText(self.player_name.split()[-1])

        elif mode == 'STATLINE':
            pts = self._today_stats.get('PTS', 0)
            reb = self._today_stats.get('REB', 0)
            ast = self._today_stats.get('AST', 0)
            pf  = self._today_stats.get('PF',  0)
            self._points_label.setStyleSheet("color: #cdd6f4; background: transparent;")
            self._points_label.setText(f"{int(pts)}/{int(reb)}/{int(ast)}/{int(pf)}")
            self._name_label.setText(self.player_name.split()[-1])