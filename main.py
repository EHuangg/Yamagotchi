import sys
import os
import signal
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtCore import QTimer, qInstallMessageHandler
from PyQt6.QtGui import QIcon, QAction

from ui.desktop_widget import DesktopWidget, BAR_THICKNESS
from ui.setup_dialog import check_and_run_setup
from ui.sprite_loader import sprite_loader
from ui.appbar import AppBar

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
    initial_snapshot = initial_team.get('full_snapshot', [])

    # Collect ALL player names across every team for live polling
    all_roster_names = []
    for team_id in team_cache.all_team_ids:
        team_data = team_cache.get_team(team_id)
        all_roster_names.extend([p.name for p in team_data.get('full_snapshot', [])])
    all_roster_names = list(set(all_roster_names))
    print(f"Tracking {len(all_roster_names)} players across all teams")

    # Live client
    live_client = LiveClient(scoring_settings)

    # Build UI — set_team_cache handles initial matchup emit
    widget = DesktopWidget(players=initial_snapshot)
    widget.show()
    widget.set_team_cache(team_cache)


    # System Tray Menu - for minimizing tray
    tray = QSystemTrayIcon(QIcon(os.path.join(os.path.dirname(__file__), 'assets', 'icon.ico')), app)
    tray_menu = QMenu()
    tray_menu.setStyleSheet("""
        QMenu {
            background-color: #D8E2F0;
            color: #000A14;
            border: 1px solid #929EAF;
            border-radius: 8px;
            padding: 4px;
            font-size: 12px;
        }
        QMenu::item { padding: 6px 20px; border-radius: 4px; }
        QMenu::item:selected { background-color: #A7C2E5; }
    """)

    show_action = QAction("Show", app)
    hide_action = QAction("Hide", app)
    quit_action = QAction("Quit", app)

    def show_widget():
        widget.show()
        show_action.setVisible(False)
        hide_action.setVisible(True)
        QTimer.singleShot(100, _reregister_appbar)

    # on second show after hiding
    def _reregister_appbar():
        screens = QApplication.screens()
        try:
            with open(SETTINGS_PATH) as f:
                idx = json.load(f).get('monitor', 0)
            screen = screens[idx] if idx < len(screens) else screens[0]
        except Exception:
            screen = screens[0]
        widget._appbar = AppBar(int(widget.winId()), BAR_THICKNESS)
        widget._appbar.register(widget._edge, screen=screen.geometry())

    def hide_widget():
        if widget._appbar:
            widget._appbar.unregister()
            widget._appbar = None
        widget.hide()
        show_action.setVisible(True)
        hide_action.setVisible(False)

    # connect AFTER defining hide_widget
    event_bus.widget_hidden.connect(hide_widget)

    show_action.triggered.connect(show_widget)
    hide_action.triggered.connect(hide_widget)
    quit_action.triggered.connect(lambda: (widget._appbar.unregister() if widget._appbar else None, app.quit()))

    show_action.setVisible(False)
    tray_menu.addAction(show_action)
    tray_menu.addAction(hide_action)
    tray_menu.addSeparator()
    tray_menu.addAction(quit_action)

    tray.setContextMenu(tray_menu)
    tray.setToolTip("Yamagotchi")
    tray.activated.connect(lambda reason: show_widget() if reason == QSystemTrayIcon.ActivationReason.DoubleClick and not widget.isVisible() else hide_widget() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
    tray.show()

    widget.tray = tray  # keep reference alive

    # Wire event bus
    trigger = AnimationTrigger(widget.roster_view)

    # Set season averages
    for player in initial_snapshot:
        card = widget.roster_view.get_card(player.player_id)
        if card:
            card.set_season_avg(player.projected_points)

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

    def on_live_stats_updated(stats: dict):
        widget._live_data_cache.update(stats)
        
        # Push live data directly to visible cards
        for name, data in stats.items():
            for player_id, card in widget._cards.items():
                try:
                    if card.player_name == name:
                        card.set_live_data(data)
                        break
                except RuntimeError:
                    pass
        # Update scoreboard scores using live data where available
        current = widget._current_matchup_data
        if current and current.get('my_team_id'):
            my_data  = team_cache.get_team(current['my_team_id'])
            opp_data = team_cache.get_team(current.get('opp_team_id'))
            if my_data and opp_data:
                def _calc_score(matchup_players):
                    if not matchup_players:
                        return None
                    total = 0.0
                    for name, base_pts in matchup_players:
                        live = widget._live_data_cache.get(name, {})
                        total += live.get('fantasy_pts', base_pts) if live else base_pts
                    return total

                my_score  = _calc_score(my_data['matchup'].get('my_players',  []))
                opp_score = _calc_score(opp_data['matchup'].get('my_players', []))
                if my_score  is not None: current['my_score']  = my_score
                if opp_score is not None: current['opp_score'] = opp_score
                event_bus.matchup_updated.emit(current)

    event_bus.live_stats_updated.connect(on_live_stats_updated)
    event_bus.daily_reset.connect(lambda: widget._live_data_cache.clear())

    app.aboutToQuit.connect(poller.stop)
    app.aboutToQuit.connect(live_poller.stop)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()