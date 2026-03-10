import sys
import os
import signal
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, qInstallMessageHandler
from PyQt6.QtGui import QIcon
from ui.desktop_widget import DesktopWidget
from ui.setup_dialog import check_and_run_setup
from ui.sprite_loader import sprite_loader
from api.espn_client import ESPNClient
from api.live_client import LiveClient
from api.team_cache import TeamCache
from api.poller import Poller
from api.live_poller import LivePoller
from events.animation_trigger import AnimationTrigger
from events.event_bus import event_bus

def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'assets', 'icon.ico')))

    def suppress_qt_warnings(msg_type, context, message):
        if "UpdateLayeredWindowIndirect" in message:
            return
        print(message)
    qInstallMessageHandler(suppress_qt_warnings)

    sprite_loader.ensure_loaded()

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    heartbeat = QTimer()
    heartbeat.start(500)
    heartbeat.timeout.connect(lambda: None)

    if not check_and_run_setup():
        print("Setup cancelled. Exiting.")
        sys.exit(0)

    # ESPN connection
    client = ESPNClient()
    try:
        client.connect()
        all_teams_data = client.get_all_teams_data()
        scoring_settings = client.get_scoring_settings()
        print(f"Loaded {len(all_teams_data)} teams")
    except Exception as e:
        print(f"ESPN connection failed: {e}")
        all_teams_data = {}
        scoring_settings = {}

    # Build team cache
    team_cache = TeamCache(all_teams_data)

    # Get initial team
    last_team_id = client._settings["espn"].get("last_viewed_team_id", 1)
    initial_team = team_cache.get_team(last_team_id) or team_cache.get_team(
        team_cache.all_team_ids[0]
    )
    initial_snapshot = initial_team.get('snapshot', [])

    # Collect ALL player names across every team for live polling
    all_roster_names = []
    for team_id in team_cache.all_team_ids:
        team_data = team_cache.get_team(team_id)
        all_roster_names.extend([p.name for p in team_data.get('snapshot', [])])
    all_roster_names = list(set(all_roster_names))
    print(f"Tracking {len(all_roster_names)} players across all teams")

    # Live client
    live_client = LiveClient(scoring_settings)

    # Build UI
    widget = DesktopWidget(players=initial_snapshot)
    widget.show()
    widget.set_team_cache(team_cache)

    # Wire event bus
    trigger = AnimationTrigger(widget.roster_view)

    # Set season averages
    for player in initial_snapshot:
        card = widget.roster_view.get_card(player.player_id)
        if card:
            card.set_season_avg(player.projected_points)

    # Initial matchup
    event_bus.matchup_updated.emit(initial_team.get('matchup', {}))

    # Pollers
    poller = Poller(client, initial_snapshot)
    poller.poll_failed.connect(lambda err: print(f"POLL FAILED: {err}"))
    poller.start()

    live_poller = LivePoller(live_client, all_roster_names)
    live_poller.poll_failed.connect(lambda err: print(f"LIVE POLL FAILED: {err}"))
    live_poller.start()

    # Store references
    widget.espn_client = client
    widget.live_client = live_client
    widget.poller = poller
    widget.live_poller = live_poller
    widget.team_cache = team_cache

    def refresh_matchup():
        try:
            data = team_cache.get_team(widget._current_team_id)
            if data and data.get('matchup'):
                event_bus.matchup_updated.emit(data['matchup'])
        except Exception as e:
            print(f"Matchup refresh failed: {e}")

    def on_live_stats_updated(stats: dict):
        widget._live_data_cache.update(stats)
        refresh_matchup()

    event_bus.live_stats_updated.connect(on_live_stats_updated)
    event_bus.daily_reset.connect(lambda: widget._live_data_cache.clear())

    app.aboutToQuit.connect(poller.stop)
    app.aboutToQuit.connect(live_poller.stop)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()