from datetime import datetime
import time
import pytz
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from api.espn_client import ESPNClient
from api.event_parser import build_snapshot, compare_snapshots, PlayerState
from events.event_bus import event_bus
from typing import List

EASTERN = pytz.timezone("America/New_York")
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
GAME_WINDOW_CACHE_SECONDS = 300

POLL_INTERVAL_ACTIVE = 45
POLL_INTERVAL_IDLE   = 1800  # 30 min
MANUAL_LINEUP_CHECK_INTERVAL_SECONDS = 5
LINEUP_REFRESH_INTERVAL_ACTIVE = MANUAL_LINEUP_CHECK_INTERVAL_SECONDS
LINEUP_REFRESH_INTERVAL_IDLE = MANUAL_LINEUP_CHECK_INTERVAL_SECONDS


class Poller(QThread):
    poll_failed = pyqtSignal(str)

    def __init__(self, client: ESPNClient, initial_snapshot: List[PlayerState]):
        super().__init__()
        self.client = client
        self.snapshot = initial_snapshot
        self._running = True
        self._force_refresh = False
        self._last_reset_date = None  # tracks which date we last reset on
        self._last_team_cache_refresh = 0.0
        self._last_game_window_check = 0.0
        self._cached_game_window = True
        event_bus.force_refresh.connect(self._on_force_refresh)

    def _on_force_refresh(self):
        self._force_refresh = True

    def run(self):
        while self._running:
            # Check for daily 3am EST reset before sleeping
            self._check_daily_reset()

            if not self._force_refresh:
                interval = self._get_poll_interval()
                print(f"[Poller] Sleeping {interval}s (live window: {self._is_active_game_window()})")
                self._sleep_interruptible(interval)

            self._force_refresh = False

            if not self._running:
                break

            try:
                fresh_roster = self.client.get_fresh_roster()
                events, new_snapshot = compare_snapshots(self.snapshot, fresh_roster)
                self.snapshot = new_snapshot

                event_bus.snapshot_updated.emit(new_snapshot)

                for e in events:
                    event_bus.game_event.emit(e)

                    if e.event_type == "POINTS_SCORED":
                        event_bus.points_scored.emit(e.player_id, e.delta)
                    elif e.event_type == "BIG_GAME":
                        event_bus.big_game.emit(e.player_id, e.delta)
                    elif e.event_type == "ZERO_WEEK":
                        event_bus.zero_week.emit(e.player_id)
                    elif e.event_type == "GAME_STARTED":
                        event_bus.game_started.emit(e.player_id, e.delta)

                    # print(f"[Event] {e.player_name}: {e.event_type} +{e.delta}pts")

                self._maybe_refresh_team_cache(force=self._force_refresh)

            except Exception as ex:
                print(f"[Poller] Error: {ex}")
                self.poll_failed.emit(str(ex))

    def stop(self):
        self._running = False
        self.requestInterruption()
        self.quit()

    def _sleep_interruptible(self, seconds: int):
        # Sleep in short chunks so stop()/Ctrl+C can break out quickly.
        remaining_ms = max(0, int(seconds * 1000))
        step_ms = 200
        next_manual_lineup_check = time.monotonic()
        while remaining_ms > 0 and self._running and not self.isInterruptionRequested():
            self.msleep(min(step_ms, remaining_ms))
            remaining_ms -= step_ms

            now = time.monotonic()
            if now >= next_manual_lineup_check:
                self._check_daily_reset()
                self._maybe_refresh_team_cache(force=False)
                next_manual_lineup_check = now + MANUAL_LINEUP_CHECK_INTERVAL_SECONDS

    def _now_est(self) -> datetime:
        return datetime.now(EASTERN)

    def _is_active_game_window(self) -> bool:
        now = time.monotonic()
        if (now - self._last_game_window_check) < GAME_WINDOW_CACHE_SECONDS:
            return self._cached_game_window

        try:
            resp = requests.get(SCOREBOARD_URL, timeout=10)
            resp.raise_for_status()
            events = resp.json().get('events', [])
            self._cached_game_window = len(events) > 0
        except Exception as ex:
            print(f"[Poller] Scoreboard window check failed: {ex}")
            # Prefer active cadence if schedule lookup fails so lineup/stat updates are not missed.
            self._cached_game_window = True

        self._last_game_window_check = now
        return self._cached_game_window

    def _get_poll_interval(self) -> int:
        return POLL_INTERVAL_ACTIVE if self._is_active_game_window() else POLL_INTERVAL_IDLE

    def _get_lineup_refresh_interval(self) -> int:
        return (LINEUP_REFRESH_INTERVAL_ACTIVE
                if self._is_active_game_window()
                else LINEUP_REFRESH_INTERVAL_IDLE)

    def _maybe_refresh_team_cache(self, force: bool = False):
        now = time.monotonic()
        if not force and (now - self._last_team_cache_refresh) < self._get_lineup_refresh_interval():
            return

        try:
            all_teams_data = self.client.get_all_teams_data()
            event_bus.team_cache_updated.emit(all_teams_data)
            self._last_team_cache_refresh = now
        except Exception as ex:
            print(f"[Poller] Team cache refresh failed: {ex}")

    def _check_daily_reset(self):
        """
        Reset all player points to 0 once per day at 3am EST.
        This lines up with when ESPN finalizes stats overnight.
        """
        now = self._now_est()

        # Only trigger between 3:00am and 3:30am EST to avoid firing repeatedly
        is_reset_window = now.hour == 3 and now.minute < 30
        today = now.date()

        if is_reset_window and self._last_reset_date != today:
            # Emit empty live cache reset signal at 3am
            event_bus.daily_reset.emit()  # clears display
            # Then clear widget cache via a new signal, or just let next poll repopulate
            print(f"[Poller] Daily reset triggered at {now.strftime('%Y-%m-%d %H:%M EST')}")
            self._last_reset_date = today
            self._do_reset()

    def _do_reset(self):
        """Zero out all player points and fetch a fresh roster."""
        try:
            fresh_roster = self.client.get_fresh_roster()
            new_snapshot = build_snapshot(fresh_roster)

            # Zero out points — ESPN hasn't updated yet at exactly 3am,
            # so we clear locally and let the next poll pick up fresh data
            for player in new_snapshot:
                player.points_this_week = 0.0
                player.last_known_points = 0.0

            self.snapshot = new_snapshot
            event_bus.snapshot_updated.emit(new_snapshot)
            self._maybe_refresh_team_cache(force=True)
            print(f"[Poller] Reset complete — {len(new_snapshot)} players zeroed out")

        except Exception as ex:
            print(f"[Poller] Reset failed: {ex}")