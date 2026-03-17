import json
import os
import re
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

def _clean_player_name(name: str) -> str:
    return re.sub(r'\s+(Jr\.?|Sr\.?|II|III|IV|V)$', '', name.strip(), flags=re.IGNORECASE)

SPRITE_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'sprites')
FRAMES_DIR = os.path.join(SPRITE_DIR, 'frames')
SKIN_TONES_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'skin_tones.json')

FRAME_SIZE   = 16
DISPLAY_SIZE = 64

# Load skin tones from config
_SKIN_TONES: dict[str, str] = {}
try:
    with open(SKIN_TONES_PATH) as f:
        _SKIN_TONES = json.load(f)
except Exception as e:
    print(f"[SpriteLoader] Could not load skin_tones.json: {e}")

NBA_TEAM_JERSEY_MAP = {
    "BOS": "celtics", "BKN": "nets", "NYK": "knicks", "PHL": "76ers", "TOR": "raptors",
    "CHI": "bulls", "CLE": "caveliers", "DET": "pistons", "IND": "pacers", "MIL": "bucks",
    "ATL": "hawks", "CHA": "hornets", "MIA": "heat", "ORL": "magic", "WAS": "wizards",
    "DEN": "nuggets", "MIN": "timberwolves", "OKC": "thunder", "POR": "trailblazers", "UTA": "jazz",
    "GSW": "warriors", "LAC": "clippers", "LAL": "lakers", "PHO": "suns", "SAC": "kings",
    "DAL": "mavericks", "HOU": "rockets", "MEM": "grizzlies", "NOP": "pelicans", "SAS": "spurs",
}

def get_jersey_for_team(nba_team_name: str) -> str:
    return NBA_TEAM_JERSEY_MAP.get(nba_team_name, "lakers")


class SpriteLoader:
    def __init__(self):
        # Single dict to hold all pre-composited frames
        self._frames: dict[str, list[QPixmap]] = {}
        self._animations: dict = {}
        self._loaded = False

    def ensure_loaded(self):
        if self._loaded:
            return

        # Load animations
        anim_path = os.path.join(SPRITE_DIR, 'animations.json')
        try:
            with open(anim_path) as f:
                self._animations = json.load(f)
        except Exception as e:
            print(f"[SpriteLoader] Could not load animations.json: {e}")
            self._animations = {"idle": {"frames": [0,4], "fps": 1}}

        # Load all pre-composited frames from flat structure
        frame_count = 0
        frame_total = 0
        if os.path.exists(FRAMES_DIR):
            for filename in os.listdir(FRAMES_DIR):
                if filename.endswith('.png'):
                    frame_total += 1
                    key = filename.replace('.png', '')
                    frames = self._slice_sheet(os.path.join(FRAMES_DIR, filename))
                    if frames:
                        self._frames[key] = frames
                        frame_count += 1
                    else:
                        print(f"[SpriteLoader] Failed to load frame: {key}")
            print(f"[SpriteLoader] Frames: {frame_count}/{frame_total} loaded")
        else:
            print(f"[SpriteLoader] Frames directory not found: {FRAMES_DIR}")

        ## place all animation loading above this line
        self._loaded = True
        
    def _slice_sheet(self, path: str) -> list[QPixmap]:
        sheet = QPixmap(path)
        if sheet.isNull():
            print(f"[SpriteLoader] Failed to load: {path}")
            return []
        frame_count = sheet.width() // FRAME_SIZE
        frames = []
        for i in range(frame_count):
            frame = sheet.copy(i * FRAME_SIZE, 0, FRAME_SIZE, FRAME_SIZE)
            scaled = frame.scaled(
                DISPLAY_SIZE, DISPLAY_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
            frames.append(scaled)
        return frames

    def get_idle_frames(self, player_name: str, jersey: str) -> list[QPixmap]:
        """Get pre-composited idle frames for player + jersey."""
        clean_name = _clean_player_name(player_name)
        skin = _SKIN_TONES.get(clean_name, 'medium')
        key = f"idle_{skin}_bald_{jersey}"
        
        if key not in self._frames:
            # Fallback to lakers jersey if not found
            key = f"idle_{skin}_bald_lakers"
            if key not in self._frames:
                return []
        
        return self._frames.get(key, [])

    def get_made_shot_frames(self, player_name: str, jersey: str) -> list[QPixmap]:
        """Get pre-composited madeShot frames for player + jersey."""
        clean_name = _clean_player_name(player_name)
        skin = _SKIN_TONES.get(clean_name, 'medium')
        key = f"madeshot_{skin}_bald_{jersey}"
        
        if key not in self._frames:
            # Fallback to lakers jersey if not found
            key = f"madeshot_{skin}_bald_lakers"
            if key not in self._frames:
                return []
        
        return self._frames.get(key, [])
    
    def get_missed_shot_frames(self) -> list[QPixmap]:
        """Get missedShot frames."""
        return self._frames.get("missedshot", [])
    
    def get_block_frames(self, player_name: str) -> list[QPixmap]:
        """Get block frames for player."""
        clean_name = _clean_player_name(player_name)
        skin = _SKIN_TONES.get(clean_name, 'medium')
        key = f"block_{skin}"
        
        # Fallback to medium skin if not found
        if key not in self._frames:
            key = "block_medium"
        
        return self._frames.get(key, [])

    def get_animation(self, name: str) -> dict:
        return self._animations.get(name, {"frames": [0,4], "fps": 1})

    def get_frame(self, frame_index: int):
        return None


# Singleton
sprite_loader = SpriteLoader()