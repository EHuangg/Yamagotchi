from PyQt6.QtCore import QThread, pyqtSignal
from api.live_client import LiveClient
from events.event_bus import event_bus
from typing import List

POLL_INTERVAL_LIVE = 15    # seconds during active games
POLL_INTERVAL_IDLE = 300   # 5 min outside game window


class LivePoller(QThread):
    poll_failed = pyqtSignal(str)

    def __init__(self, live_client: LiveClient, roster_names: List[str]):
        super().__init__()
        self.client       = live_client
        self.roster_names = roster_names
        self._running     = True
        self._force       = False
        self._last_stats  = {}   # tracks previous poll for delta detection
        self._has_games_today = True
        event_bus.force_refresh.connect(self._on_force)

    def _on_force(self):
        self._force = True

    def update_roster_names(self, names: List[str]):
        self.roster_names = names

    def run(self):
        self._fetch_and_emit()
        while self._running:
            if not self._force:
                interval = self._get_interval()
                self._sleep_interruptible(interval)
            self._force = False
            if not self._running:
                break
            self._fetch_and_emit()

    def _fetch_and_emit(self):
        try:
            games = self.client.get_todays_games()
            self._has_games_today = bool(games)
            if not games:
                return

            stats = self.client.get_all_live_stats_for_roster(
                self.roster_names, games
            )

            if stats:
                changed = self._get_changed(stats)
                if changed:
                    event_bus.live_stats_updated.emit(changed)
                self._last_stats = stats

        except Exception as ex:
            print(f"[LivePoller] Error: {ex}")
            self.poll_failed.emit(str(ex))

    def _get_changed(self, new_stats: dict) -> dict:
        """Return only players whose fantasy_pts or game_status changed."""
        changed = {}
        for name, data in new_stats.items():
            old = self._last_stats.get(name, {})
            if (data.get('fantasy_pts') != old.get('fantasy_pts') or
                data.get('game_status') != old.get('game_status')):
                changed[name] = data
        return changed

    def stop(self):
        self._running = False
        self.requestInterruption()
        self.quit()

    def _sleep_interruptible(self, seconds: int):
        # Sleep in short chunks so stop()/Ctrl+C can break out quickly.
        remaining_ms = max(0, int(seconds * 1000))
        step_ms = 200
        while remaining_ms > 0 and self._running and not self.isInterruptionRequested():
            self.msleep(min(step_ms, remaining_ms))
            remaining_ms -= step_ms

    def _get_interval(self) -> int:
        return POLL_INTERVAL_LIVE if self._has_games_today else POLL_INTERVAL_IDLE