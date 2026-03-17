from PyQt6.QtCore import QObject, pyqtSignal

class EventBus(QObject):
    # Fantasy polling signals
    points_scored    = pyqtSignal(int, float)
    big_game         = pyqtSignal(int, float)
    zero_week        = pyqtSignal(int)
    game_started     = pyqtSignal(int, float)
    game_event       = pyqtSignal(object)
    snapshot_updated = pyqtSignal(list)
    force_refresh    = pyqtSignal()

    # Live stats signals
    # dict of player_name → {PTS, REB, AST, STL, BLK, TO, PF, fantasy_pts, game_status}
    live_stats_updated = pyqtSignal(dict)

    # Matchup signal
    # dict of {my_team, my_score, opp_team, opp_score, my_players, opp_players}
    matchup_updated = pyqtSignal(dict)

    # Full league cache refresh signal
    # dict of team_id -> {team_name, team_id, roster, matchup}
    team_cache_updated = pyqtSignal(object)

    # reset cache signal
    daily_reset = pyqtSignal()

    # hide/show app bar
    widget_hidden = pyqtSignal()
event_bus = EventBus()