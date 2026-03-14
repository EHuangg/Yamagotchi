from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

# --- Data Models ---

@dataclass
class PlayerState:
    player_id: int
    name: str
    position: str
    points_this_week: float
    projected_points: float
    is_playing_today: bool
    last_known_points: float = 0.0
    nba_team: str = ""
    lineup_slot: str = ""
    slot_order: int = 10
    injury_status: str = ""  # 'ACTIVE', 'QUESTIONABLE', 'DOUBTFUL', 'OUT', 'IR'
    
@dataclass
class GameEvent:
    player_id: int
    player_name: str
    event_type: str   # "POINTS_SCORED", "BIG_GAME", "ZERO_WEEK", "GAME_STARTED"
    delta: float      # fantasy points gained
    timestamp: datetime = field(default_factory=datetime.now)


# --- Snapshot Builder ---
SEASON_YEAR = 2026

# Lineup slots that count as "starters" in ESPN NBA fantasy
STARTER_SLOTS = {
    'PG', 'SG', 'SF', 'PF', 'C', 'G', 'F', 'UTIL', 'UT'
}

SLOT_ORDER = {
    'PG': 0, 'SG': 1, 'SF': 2, 'PF': 3, 'C': 4,
    'G': 5, 'F': 6, 'UTIL': 7, 'UT': 7,
    'BE': 8, 'BN': 8,
    'IR': 9,
}

def build_snapshot(roster, starters_only: bool = False) -> List[PlayerState]:
    snapshot = []
    for player in roster:
        if starters_only:
            slot = getattr(player, 'lineupSlot', '') or ''
            if slot.upper() not in STARTER_SLOTS:
                continue

        try:
            total_stats = (player.stats or {}).get(f'{SEASON_YEAR}_total', {})
            season_avg = float(total_stats.get('applied_avg', 0.0))
        except Exception as e:
            print(f"[EventParser] Failed to get season avg: {e}")
            season_avg = 0.0

        slot = (getattr(player, 'lineupSlot', '') or '').upper()
        snapshot.append(PlayerState(
            player_id=player.playerId,
            name=player.name,
            position=player.position,
            points_this_week=0.0,
            projected_points=season_avg,
            is_playing_today=season_avg > 0.0,
            last_known_points=0.0,
            nba_team=getattr(player, 'proTeam', '') or '',
            lineup_slot=slot,
            slot_order=SLOT_ORDER.get(slot, 10),
            injury_status=getattr(player, 'injuryStatus', '') or '',
        ))

    snapshot.sort(key=lambda p: p.slot_order)
    return snapshot

# --- Event Comparison ---

# NBA fantasy: a "big game" is roughly a 30+ pt performance
# In most standard leagues, that translates to ~8+ fantasy pts in one poll tick
BIG_PLAY_THRESHOLD = 8.0

def compare_snapshots(
    old: List[PlayerState],
    new_roster
) -> tuple[List[GameEvent], List[PlayerState]]:
    """
    Compare old snapshot to a fresh NBA roster.
    Returns (list of events, updated snapshot).
    """
    new_snapshot = build_snapshot(new_roster)
    old_by_id = {p.player_id: p for p in old}
    events = []

    for new_player in new_snapshot:
        old_player = old_by_id.get(new_player.player_id)

        if old_player is None:
            # New pickup — no event yet, just track going forward
            continue

        delta = new_player.points_this_week - old_player.points_this_week

        if delta > 0:
            event_type = "BIG_GAME" if delta >= BIG_PLAY_THRESHOLD else "POINTS_SCORED"
            events.append(GameEvent(
                player_id=new_player.player_id,
                player_name=new_player.name,
                event_type=event_type,
                delta=round(delta, 2)
            ))

        elif (old_player.is_playing_today
              and new_player.points_this_week == 0.0
              and old_player.points_this_week == 0.0
              and not new_player.is_playing_today):
            # Had a game scheduled, never scored — DNP or no stat line
            events.append(GameEvent(
                player_id=new_player.player_id,
                player_name=new_player.name,
                event_type="ZERO_WEEK",
                delta=0.0
            ))

        elif (old_player.points_this_week == 0.0
              and new_player.points_this_week > 0.0):
            # Player just started accumulating points this period
            events.append(GameEvent(
                player_id=new_player.player_id,
                player_name=new_player.name,
                event_type="GAME_STARTED",
                delta=round(new_player.points_this_week, 2)
            ))

    return events, new_snapshot