from api.event_parser import build_snapshot

class TeamCache:
    """
    Holds all teams' data in memory.
    Switching teams is instant — no API call needed.
    """
    def __init__(self, all_teams_data: dict):
        self._cache = {}
        self._team_order = []
        self._load(all_teams_data)

    def _load(self, all_teams_data: dict):
        self._cache = {}
        self._team_order = sorted(all_teams_data.keys())
        for team_id, data in all_teams_data.items():
            self._cache[team_id] = {
                'team_name':      data['team_name'],
                'team_id':        data['team_id'],
                'snapshot':       build_snapshot(data['roster'], starters_only=True),
                'full_snapshot':  build_snapshot(data['roster'], starters_only=False),
                'matchup':        data['matchup'],
            }

    def refresh(self, all_teams_data: dict):
        self._load(all_teams_data)

    def get_team(self, team_id: int) -> dict:
        return self._cache.get(team_id, {})

    def next_team_id(self, current_id: int) -> int:
        idx = self._team_order.index(current_id)
        return self._team_order[(idx + 1) % len(self._team_order)]

    def prev_team_id(self, current_id: int) -> int:
        idx = self._team_order.index(current_id)
        return self._team_order[(idx - 1) % len(self._team_order)]

    @property
    def all_team_ids(self):
        return self._team_order