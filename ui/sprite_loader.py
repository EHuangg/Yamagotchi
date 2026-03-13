import json
import os
import re
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtCore import Qt

def _clean_player_name(name: str) -> str:
    return re.sub(r'\s+(Jr\.?|Sr\.?|II|III|IV|V)$', '', name.strip(), flags=re.IGNORECASE)

SPRITE_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'sprites')
MADE_SHOT_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'sprites', 'madeShot')
BLOCK_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'sprites', 'block', 'body')
MISSED_SHOT_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'sprites', 'missedShot')


FRAME_SIZE   = 16
DISPLAY_SIZE = 64

PLAYER_SKIN_MAP: dict[str, tuple[str, str]] = {}

DEFAULT_SKIN = "dark"
DEFAULT_HAIR = "bald"

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
        self._body_frames: dict[str, list[QPixmap]] = {}
        self._jersey_frames: dict[str, list[QPixmap]] = {}
        self._composited: dict[str, list[QPixmap]] = {}

        # madeShot layers
        self._made_body_frames: dict[str, list[QPixmap]] = {}
        self._made_jersey_frames: dict[str, list[QPixmap]] = {}
        self._made_composited: dict[str, list[QPixmap]] = {}
        self._made_ball_frames: list[QPixmap] = []
        
        # missedShot layers
        self._missed_shot_frames: list[QPixmap] = []
        
        # block layers
        self._block_frames: dict[str, list[QPixmap]] = {}
        
        

        self._animations: dict = {}
        self._loaded = False

    def ensure_loaded(self):
        if self._loaded:
            return
        # debugging
        print(f"[SpriteLoader] Block frames loaded: {list(self._block_frames.keys())}")

        anim_path = os.path.join(SPRITE_DIR, 'animations.json')
        try:
            with open(anim_path) as f:
                self._animations = json.load(f)
        except Exception as e:
            print(f"[SpriteLoader] Could not load animations.json: {e}")
            self._animations = {"idle": {"frames": [0,1,2,3,4,5], "fps": 3}}

        # Load idle body sheets
        idle_dir = os.path.join(SPRITE_DIR, 'idle')
        for filename in os.listdir(os.path.join(idle_dir, 'body')):
            if not filename.endswith('.png'):
                continue
            key = filename.replace('.png', '')
            self._body_frames[key] = self._slice_sheet(
                os.path.join(idle_dir, 'body', filename)
            )
            print(f"[SpriteLoader] Loaded idle body: {key} ({len(self._body_frames[key])} frames)")

        # Load idle jersey sheets
        for filename in os.listdir(os.path.join(idle_dir, 'jerseys')):
            if not filename.endswith('.png'):
                continue
            key = filename.replace('.png', '')
            self._jersey_frames[key] = self._slice_sheet(
                os.path.join(idle_dir, 'jerseys', filename)
            )
            print(f"[SpriteLoader] Loaded idle jersey: {key} ({len(self._jersey_frames[key])} frames)")

        # Load madeShot body sheets
        made_body_dir = os.path.join(MADE_SHOT_DIR, 'body')
        if os.path.exists(made_body_dir):
            for filename in os.listdir(made_body_dir):
                if not filename.endswith('.png'):
                    continue
                key = filename.replace('.png', '')
                self._made_body_frames[key] = self._slice_sheet(
                    os.path.join(made_body_dir, filename)
                )
                print(f"[SpriteLoader] Loaded madeShot body: {key} ({len(self._made_body_frames[key])} frames)")

        # Load madeShot jersey sheets
        made_jersey_dir = os.path.join(MADE_SHOT_DIR, 'jerseys')
        if os.path.exists(made_jersey_dir):
            for filename in os.listdir(made_jersey_dir):
                if not filename.endswith('.png'):
                    continue
                key = filename.replace('.png', '')
                self._made_jersey_frames[key] = self._slice_sheet(
                    os.path.join(made_jersey_dir, filename)
                )
                print(f"[SpriteLoader] Loaded madeShot jersey: {key} ({len(self._made_jersey_frames[key])} frames)")

        # Load madeShot ball
        ball_path = os.path.join(MADE_SHOT_DIR, 'ball.png')
        if os.path.exists(ball_path):
            self._made_ball_frames = self._slice_sheet(ball_path)
            print(f"[SpriteLoader] Loaded madeShot ball ({len(self._made_ball_frames)} frames)")

        # Load missedShot frames
        missed_path = os.path.join(MISSED_SHOT_DIR, 'missedShot.png')
        if os.path.exists(missed_path):
            self._missed_shot_frames = self._slice_sheet(missed_path)
            print(f"[SpriteLoader] Loaded missedShot ({len(self._missed_shot_frames)} frames)")
        else:
            print(f"[SpriteLoader] missedShot not found: {missed_path}")


        # Load block
        self._block_frames = {}
        print(f"[SpriteLoader] BLOCK_DIR: {BLOCK_DIR}, exists: {os.path.exists(BLOCK_DIR)}")
        if os.path.exists(BLOCK_DIR):
            for filename in os.listdir(BLOCK_DIR):
                if not filename.endswith('.png'):
                    continue
                key = filename.replace('.png', '')
                self._block_frames[key] = self._slice_sheet(os.path.join(BLOCK_DIR, filename))
                print(f"[SpriteLoader] Loaded block: {key}")
        else:
            print(f"[SpriteLoader] Block dir not found: {BLOCK_DIR}")

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

    def _composite(self, body_frames, jersey_frames, ball_frames=None) -> list[QPixmap]:
        """Composite body + jersey (+ optional ball) per frame."""
        composited = []
        for i, body in enumerate(body_frames):
            result = QPixmap(body.size())
            result.fill(Qt.GlobalColor.transparent)
            painter = QPainter(result)
            painter.drawPixmap(0, 0, body)
            if i < len(jersey_frames):
                painter.drawPixmap(0, 0, jersey_frames[i])
            if ball_frames and i < len(ball_frames):
                painter.drawPixmap(0, 0, ball_frames[i])
            painter.end()
            composited.append(result)
        return composited

    def _composite_key(self, skin: str, hair: str, jersey: str) -> str:
        return f"{skin}_{hair}+{jersey}"

    def get_idle_frames(self, player_name: str, jersey: str) -> list[QPixmap]:
        clean_name = _clean_player_name(player_name)
        skin, hair = PLAYER_SKIN_MAP.get(clean_name, (DEFAULT_SKIN, DEFAULT_HAIR))
        body_key = f"{skin}_{hair}"
        cache_key = self._composite_key(skin, hair, jersey)

        if cache_key in self._composited:
            return self._composited[cache_key]

        body_frames   = self._body_frames.get(body_key, [])
        jersey_frames = self._jersey_frames.get(jersey, [])

        if not body_frames:
            print(f"[SpriteLoader] Missing idle body: {body_key}")
            return []
        if not jersey_frames:
            print(f"[SpriteLoader] Missing idle jersey: {jersey}, falling back to lakers")
            jersey_frames = self._jersey_frames.get("lakers", [])

        self._composited[cache_key] = self._composite(body_frames, jersey_frames)
        return self._composited[cache_key]

    def get_made_shot_frames(self, player_name: str, jersey: str) -> list[QPixmap]:
        clean_name = _clean_player_name(player_name)
        skin, hair = PLAYER_SKIN_MAP.get(clean_name, (DEFAULT_SKIN, DEFAULT_HAIR))
        body_key = f"{skin}_{hair}"
        cache_key = f"made+{skin}_{hair}+{jersey}"

        if cache_key in self._made_composited:
            return self._made_composited[cache_key]

        body_frames   = self._made_body_frames.get(body_key, [])
        jersey_frames = self._made_jersey_frames.get(jersey, [])

        if not body_frames:
            print(f"[SpriteLoader] Missing madeShot body: {body_key}")
            return []
        if not jersey_frames:
            print(f"[SpriteLoader] Missing madeShot jersey: {jersey}, falling back to lakers")
            jersey_frames = self._made_jersey_frames.get("lakers", [])

        self._made_composited[cache_key] = self._composite(
            body_frames, jersey_frames, self._made_ball_frames
        )
        return self._made_composited[cache_key]
    
    def get_missed_shot_frames(self) -> list[QPixmap]:
        return self._missed_shot_frames
    
    def get_block_frames(self, player_name: str) -> list[QPixmap]:
        clean_name = _clean_player_name(player_name)
        skin, hair = PLAYER_SKIN_MAP.get(clean_name, (DEFAULT_SKIN, DEFAULT_HAIR))
        key = f"block_{skin}"
        print(f"[SpriteLoader] Looking for block key: '{key}', available: {list(self._block_frames.keys())}")
        frames = self._block_frames.get(key, [])
        if not frames:
            frames = self._block_frames.get("block_dark", [])
        return frames

    def get_animation(self, name: str) -> dict:
        return self._animations.get(name, {"frames": [0,1,2,3,4,5], "fps": 3})

    def get_frame(self, frame_index: int):
        return None


# Singleton
sprite_loader = SpriteLoader()