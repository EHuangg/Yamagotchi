from espn_api.basketball import League
import json
from config_utils import SETTINGS_PATH

class ESPNClient:
    def __init__(self):
        self.league = None
        self.my_team = None
        self._settings = self._load_settings()

    def _load_settings(self):
        with open(SETTINGS_PATH) as f:
            return json.load(f)

    def connect(self):
        cfg = self._settings["espn"]
        if not cfg["league_id"] or not cfg["espn_s2"] or not cfg["swid"]:
            raise ValueError("ESPN credentials are missing from settings.json")
        self.league = League(
            league_id=cfg["league_id"],
            year=cfg["year"],
            espn_s2=cfg["espn_s2"],
            swid=cfg["swid"]
        )
        # Default to last viewed team or team_id 1
        last_id = cfg.get("last_viewed_team_id", 1)
        self.my_team = self._get_team_by_id(last_id) or self.league.teams[0]
        print(f"Connected! Found team: {self.my_team.team_name}")
        return self.my_team

    def _get_team_by_id(self, team_id: int):
        for team in self.league.teams:
            if team.team_id == team_id:
                return team
        return None

    def get_all_teams_data(self) -> dict:
        """
        Returns a dict of team_id → team data for all teams in the league.
        {
            team_id: {
                'team_name': str,
                'team_id': int,
                'roster': [...],
                'matchup': {...}
            }
        }
        """
        all_data = {}
        box_scores = None
        try:
            box_scores = self.league.box_scores()
        except Exception as e:
            print(f"[ESPNClient] Could not load box scores: {e}")

        for team in self.league.teams:
            matchup = {}
            if box_scores:
                for m in box_scores:
                    home_is_team = hasattr(m.home_team, 'team_name')
                    away_is_team = hasattr(m.away_team, 'team_name')

                    if home_is_team and m.home_team.team_id == team.team_id:
                        if not away_is_team:
                            matchup = {
                                'my_team':     m.home_team.team_name,
                                'my_score':    m.home_score or 0.0,
                                'opp_team':    'BYE',
                                'opp_score':   0.0,
                                'my_players':  [],
                                'opp_players': [],
                            }
                        else:
                            matchup = self._format_matchup(m, home=True)
                        break
                    elif away_is_team and m.away_team.team_id == team.team_id:
                        if not home_is_team:
                            matchup = {
                                'my_team':     m.away_team.team_name,
                                'my_score':    m.away_score or 0.0,
                                'opp_team':    'BYE',
                                'opp_score':   0.0,
                                'my_players':  [],
                                'opp_players': [],
                            }
                        else:
                            matchup = self._format_matchup(m, home=False)
                        break

            all_data[team.team_id] = {
                'team_name': team.team_name,
                'team_id':   team.team_id,
                'roster':    team.roster,
                'matchup':   matchup,
            }
        return all_data

    def get_fresh_roster(self):
        cfg = self._settings["espn"]
        self.league = League(
            league_id=cfg["league_id"],
            year=cfg["year"],
            espn_s2=cfg["espn_s2"],
            swid=cfg["swid"]
        )
        self.my_team = self._get_team_by_id(
            cfg.get("last_viewed_team_id", 1)
        ) or self.league.teams[0]
        return self.my_team.roster

    def get_scoring_settings(self) -> dict:
        return {
            'PTS': 1.0, '3PM': 1.0, 'FGA': -1.0, 'FGM': 2.0,
            'FTA': -1.0, 'FTM': 1.0, 'REB': 1.0, 'AST': 2.0,
            'STL': 4.0, 'BLK': 4.0, 'TO': -2.0,
        }

    def get_current_matchup(self) -> dict:
        try:
            box_scores = self.league.box_scores()
            for matchup in box_scores:
                home_is_team = hasattr(matchup.home_team, 'team_name')
                away_is_team = hasattr(matchup.away_team, 'team_name')

                if home_is_team and matchup.home_team.team_id == self.my_team.team_id:
                    if not away_is_team:
                        # Bye week
                        return {
                            'my_team':   matchup.home_team.team_name,
                            'my_score':  0.0,
                            'opp_team':  'BYE',
                            'opp_score': 0.0,
                            'my_players':  [],
                            'opp_players': [],
                        }
                    return self._format_matchup(matchup, home=True)

                elif away_is_team and matchup.away_team.team_id == self.my_team.team_id:
                    if not home_is_team:
                        # Bye week
                        return {
                            'my_team':   matchup.away_team.team_name,
                            'my_score':  0.0,
                            'opp_team':  'BYE',
                            'opp_score': 0.0,
                            'my_players':  [],
                            'opp_players': [],
                        }
                    return self._format_matchup(matchup, home=False)

        except Exception as e:
            print(f"[ESPNClient] Could not load matchup: {e}")
        return {}

    def _format_matchup(self, matchup, home: bool) -> dict:
        if home:
            my_team    = matchup.home_team
            opp_team   = matchup.away_team
            my_lineup  = matchup.home_lineup or []
            opp_lineup = matchup.away_lineup or []
            my_score   = matchup.home_score
            opp_score  = matchup.away_score
        else:
            my_team    = matchup.away_team
            opp_team   = matchup.home_team
            my_lineup  = matchup.away_lineup or []
            opp_lineup = matchup.home_lineup or []
            my_score   = matchup.away_score
            opp_score  = matchup.home_score

        my_players  = [(p.name, p.points) for p in my_lineup  if hasattr(p, 'points')]
        opp_players = [(p.name, p.points) for p in opp_lineup if hasattr(p, 'points')]

        return {
            'my_team':     my_team.team_name,
            'my_score':    my_score  or 0.0,
            'opp_team':    opp_team.team_name,
            'opp_score':   opp_score or 0.0,
            'my_players':  my_players,
            'opp_players': opp_players,
        }