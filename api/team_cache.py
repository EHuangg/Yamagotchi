from api.event_parser import build_snapshot

class TeamCache:
    def __init__(self, all_teams_data: dict):
        self._cache = {}
        self._team_order = []
        self._matchups = []  # list of unique matchups
        self._load(all_teams_data)

    def _load(self, all_teams_data: dict):
        self._cache = {}
        self._team_order = sorted(all_teams_data.keys())
        seen_pairs = set()
        self._matchups = []

        for team_id, data in all_teams_data.items():
            self._cache[team_id] = {
                'team_name':     data['team_name'],
                'team_id':       data['team_id'],
                'snapshot':      build_snapshot(data['roster'], starters_only=True),
                'full_snapshot': build_snapshot(data['roster'], starters_only=False),
                'matchup':       data['matchup'],
            }

            # Build unique matchup list
            matchup = data['matchup']
            if not matchup:
                continue
            my_team  = matchup.get('my_team', '')
            opp_team = matchup.get('opp_team', '')
            pair = frozenset([my_team, opp_team])
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                # Store both team_ids so we can load either roster
                opp_id = next(
                    (tid for tid, d in all_teams_data.items()
                     if d['team_name'] == opp_team),
                    None
                )
                self._matchups.append({
                    'my_team':    my_team,
                    'my_score':   matchup.get('my_score', 0.0),
                    'my_team_id': team_id,
                    'opp_team':   opp_team,
                    'opp_score':  matchup.get('opp_score', 0.0),
                    'opp_team_id': opp_id,
                })

    def refresh(self, all_teams_data: dict):
        self._load(all_teams_data)

    def get_team(self, team_id: int) -> dict:
        return self._cache.get(team_id, {})

    def get_matchup(self, index: int) -> dict:
        if not self._matchups:
            return {}
        return self._matchups[index % len(self._matchups)]

    def matchup_count(self) -> int:
        return len(self._matchups)

    def next_team_id(self, current_id: int) -> int:
        idx = self._team_order.index(current_id)
        return self._team_order[(idx + 1) % len(self._team_order)]

    def prev_team_id(self, current_id: int) -> int:
        idx = self._team_order.index(current_id)
        return self._team_order[(idx - 1) % len(self._team_order)]

    @property
    def all_team_ids(self):
        return self._team_order