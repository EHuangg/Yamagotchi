import requests
from typing import Optional

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
SUMMARY_URL    = "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary"

class LiveClient:
    def __init__(self, scoring_settings: dict):
        """
        scoring_settings: dict of stat abbr → fantasy points value
        e.g. {'PTS': 1.0, 'REB': 1.2, 'AST': 1.5, 'STL': 3.0, 'BLK': 3.0, 'TO': -1.0}
        """
        self.scoring = scoring_settings
        self._player_game_map: dict[str, str] = {}  # player name → game_id

    def get_todays_games(self) -> list[dict]:
        """Returns list of today's NBA games with basic info."""
        try:
            resp = requests.get(SCOREBOARD_URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            games = []
            for event in data.get('events', []):
                comp = event['competitions'][0]
                games.append({
                    'game_id':  event['id'],
                    'status':   event['status']['type']['name'],
                    # e.g. STATUS_IN_PROGRESS, STATUS_FINAL, STATUS_SCHEDULED
                    'headline': event['status']['type']['shortDetail'],
                    'home':     comp['competitors'][0]['team']['displayName'],
                    'away':     comp['competitors'][1]['team']['displayName'],
                })
            return games
        except Exception as e:
            print(f"[LiveClient] Scoreboard fetch failed: {e}")
            return []

    def get_live_stats(self, game_id: str) -> dict[str, dict]:
        try:
            resp = requests.get(SUMMARY_URL, params={'event': game_id}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[LiveClient] Summary fetch failed for game {game_id}: {e}")
            return {}

        player_stats = {}

        for team in data.get('boxscore', {}).get('players', []):
            for stat_group in team.get('statistics', []):
                keys = stat_group.get('keys', [])
                for athlete in stat_group.get('athletes', []):
                    name   = athlete['athlete']['displayName']
                    values = athlete.get('stats', [])

                    if not values or values[0] == '--':
                        continue

                    raw = {}
                    for i, key in enumerate(keys):
                        val = values[i] if i < len(values) else '0'

                        # ESPN returns made-attempted as a combined string e.g. "7-12"
                        # Split them into separate made/attempted keys
                        if '-' in key and 'Made' in key:
                            parts = key.split('-')
                            made_key      = parts[0]  # e.g. fieldGoalsMade
                            attempted_key = parts[1]  # e.g. fieldGoalsAttempted
                            if isinstance(val, str) and '-' in val:
                                try:
                                    made, attempted = val.split('-')
                                    raw[made_key]      = float(made)
                                    raw[attempted_key] = float(attempted)
                                except (ValueError, IndexError):
                                    raw[made_key]      = 0.0
                                    raw[attempted_key] = 0.0
                            else:
                                raw[made_key]      = 0.0
                                raw[attempted_key] = 0.0
                        else:
                            try:
                                raw[key] = float(val)
                            except (ValueError, TypeError):
                                raw[key] = 0.0

                    player_stats[name] = {
                        'PTS': raw.get('points',                         0.0),
                        'REB': raw.get('rebounds',                       0.0),
                        'AST': raw.get('assists',                        0.0),
                        'STL': raw.get('steals',                         0.0),
                        'BLK': raw.get('blocks',                         0.0),
                        'TO':  raw.get('turnovers',                      0.0),
                        '3PM': raw.get('threePointFieldGoalsMade',       0.0),
                        'FGM': raw.get('fieldGoalsMade',                 0.0),
                        'FGA': raw.get('fieldGoalsAttempted',            0.0),
                        'FTM': raw.get('freeThrowsMade',                 0.0),
                        'FTA': raw.get('freeThrowsAttempted',            0.0),
                        'PF':  raw.get('fouls',                          0.0),
                        'MIN': raw.get('minutes',                        0.0),
                        'fantasy_pts': self._calc_fantasy(raw),
                    }

        return player_stats

    def _calc_fantasy(self, raw: dict) -> float:
        stat_map = {
            'PTS': raw.get('points',                         0.0),
            '3PM': raw.get('threePointFieldGoalsMade',       0.0),
            'FGA': raw.get('fieldGoalsAttempted',            0.0),
            'FGM': raw.get('fieldGoalsMade',                 0.0),
            'FTA': raw.get('freeThrowsAttempted',            0.0),
            'FTM': raw.get('freeThrowsMade',                 0.0),
            'REB': raw.get('rebounds',                       0.0),
            'AST': raw.get('assists',                        0.0),
            'STL': raw.get('steals',                         0.0),
            'BLK': raw.get('blocks',                         0.0),
            'TO':  raw.get('turnovers',                      0.0),
        }
        total = 0.0
        for stat, value in stat_map.items():
            multiplier = self.scoring.get(stat, 0.0)
            total += value * multiplier
        return round(total, 2)

    def build_roster_game_map(
        self,
        roster_names: list[str],
        games: list[dict]
    ) -> dict[str, str]:
        """
        Cross-references roster player names against today's games.
        Returns dict of player_name → game_id for players with a game today.
        This is approximate — matches by team name in the game listing.
        We refine it after the first live fetch.
        """
        # We can't know player→game without fetching box scores,
        # so we return all game IDs and filter after first fetch
        return {g['game_id']: g for g in games}

    def get_all_live_stats_for_roster(
        self,
        roster_names: list[str],
        games: list[dict]
    ) -> dict[str, dict]:
        roster_set = set(roster_names)
        all_stats  = {}

        for game in games:
            if game['status'] == 'STATUS_SCHEDULED':
                continue
            stats = self.get_live_stats(game['game_id'])
            for name, data in stats.items():
                if name in roster_set:
                    data['game_status']    = game['status']
                    data['game_headline']  = game['headline']
                    data['has_game_today'] = True
                    all_stats[name] = data

        return all_stats