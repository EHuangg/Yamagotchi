import json
import os
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtCore import Qt

SPRITE_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'sprites')
FRAME_SIZE   = 16
DISPLAY_SIZE = 64

# Player name → (skin_tone, hair_style)
# Unmapped players default to ('dark', 'bald')
PLAYER_SKIN_MAP: dict[str, tuple[str, str]] = {
    # e.g. "Shai Gilgeous-Alexander": ("dark", "bald"),
}

DEFAULT_SKIN = "dark"
DEFAULT_HAIR = "bald"

# Maps ESPN NBA team name → jersey filename
NBA_TEAM_JERSEY_MAP = {
    # Atlantic
    "BOS": "celtics",
    "BKN": "nets",
    "NYK": "knicks",
    "PHI": "76ers",
    "PHL": "76ers",
    "TOR": "raptors",
    # Central
    "CHI": "bulls",
    "CLE": "caveliers",
    "DET": "pistons",
    "IND": "pacers",
    "MIL": "bucks",
    # Southeast
    "ATL": "hawks",
    "CHA": "hornets",
    "MIA": "heat",
    "ORL": "magic",
    "WAS": "wizards",
    # Northwest
    "DEN": "nuggets",
    "MIN": "timberwolves",
    "OKC": "thunder",
    "POR": "trailblazers",
    "UTA": "jazz",
    # Pacific
    "GSW": "warriors",
    "LAC": "clippers",
    "LAL": "lakers",
    "PHX": "suns",
    "SAC": "kings",
    # Southwest
    "DAL": "mavericks",
    "HOU": "rockets",
    "MEM": "grizzlies",
    "NOP": "pelicans",
    "SAS": "spurs",
}

def get_jersey_for_team(nba_team_name: str) -> str:
    return NBA_TEAM_JERSEY_MAP.get(nba_team_name, "lakers")


class SpriteLoader:
    def __init__(self):
        self._body_frames: dict[str, list[QPixmap]] = {}
        self._jersey_frames: dict[str, list[QPixmap]] = {}
        self._composited: dict[str, list[QPixmap]] = {}
        self._animations: dict = {}
        self._loaded = False

    def ensure_loaded(self):
        if self._loaded:
            return

        anim_path = os.path.join(SPRITE_DIR, 'animations.json')
        try:
            with open(anim_path) as f:
                self._animations = json.load(f)
        except Exception as e:
            print(f"[SpriteLoader] Could not load animations.json: {e}")
            self._animations = {"idle": {"frames": [0,1,2,3,4,5], "fps": 3}}

        idle_dir = os.path.join(SPRITE_DIR, 'idle')

        for filename in os.listdir(os.path.join(idle_dir, 'body')):
            if not filename.endswith('.png'):
                continue
            key = filename.replace('.png', '')
            path = os.path.join(idle_dir, 'body', filename)
            self._body_frames[key] = self._slice_sheet(path)
            print(f"[SpriteLoader] Loaded body: {key} ({len(self._body_frames[key])} frames)")

        for filename in os.listdir(os.path.join(idle_dir, 'jerseys')):
            if not filename.endswith('.png'):
                continue
            key = filename.replace('.png', '')
            path = os.path.join(idle_dir, 'jerseys', filename)
            self._jersey_frames[key] = self._slice_sheet(path)
            print(f"[SpriteLoader] Loaded jersey: {key} ({len(self._jersey_frames[key])} frames)")

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

    def _composite_key(self, skin: str, hair: str, jersey: str) -> str:
        return f"{skin}_{hair}+{jersey}"

    def get_idle_frames(self, player_name: str, jersey: str) -> list[QPixmap]:
        skin, hair = PLAYER_SKIN_MAP.get(player_name, (DEFAULT_SKIN, DEFAULT_HAIR))
        body_key = f"{skin}_{hair}"
        cache_key = self._composite_key(skin, hair, jersey)

        if cache_key in self._composited:
            return self._composited[cache_key]

        body_frames   = self._body_frames.get(body_key, [])
        jersey_frames = self._jersey_frames.get(jersey, [])

        if not body_frames:
            print(f"[SpriteLoader] Missing body: {body_key}")
            return []

        if not jersey_frames:
            print(f"[SpriteLoader] Missing jersey: {jersey}, falling back to lakers")
            jersey_frames = self._jersey_frames.get("lakers", [])

        composited = []
        for i, body in enumerate(body_frames):
            result = QPixmap(body.size())
            result.fill(Qt.GlobalColor.transparent)
            painter = QPainter(result)
            painter.drawPixmap(0, 0, body)
            if i < len(jersey_frames):
                painter.drawPixmap(0, 0, jersey_frames[i])
            painter.end()
            composited.append(result)

        self._composited[cache_key] = composited
        return composited

    def get_animation(self, name: str) -> dict:
        return self._animations.get(name, {"frames": [0,1,2,3,4,5], "fps": 3})

    def get_frame(self, frame_index: int):
        return None


# Singleton
sprite_loader = SpriteLoader()