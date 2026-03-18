"""Central configuration utilities for the ESPN Fantasy Extension."""

import json
import os
import sys

APP_NAME = "Yamagotchi"

_DEFAULT_SETTINGS = {
	"window": {
		"x": 651,
		"y": 556,
		"width": 800,
		"height": 160,
	},
	"espn": {
		"league_id": 0,
		"year": 2026,
		"espn_s2": "",
		"swid": "",
		"last_viewed_team_id": 1,
	},
	"dock_edge": "right",
	"display_mode": "STARTERS",
	"monitor": 0,
}


def _resource_base_dir() -> str:
	if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
		return sys._MEIPASS
	return os.path.dirname(__file__)


def _user_config_root() -> str:
	if os.name == "nt":
		return (
			os.getenv("APPDATA")
			or os.getenv("LOCALAPPDATA")
			or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
		)
	if sys.platform == "darwin":
		return os.path.join(os.path.expanduser("~"), "Library", "Application Support")
	return os.getenv("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")


def _load_template_settings() -> dict:
	base = _resource_base_dir()
	candidates = [
		os.path.join(base, "config", "settings.example.json"),
		os.path.join(base, "config", "settings.json"),
	]
	for candidate in candidates:
		try:
			with open(candidate, encoding="utf-8") as f:
				data = json.load(f)
			if isinstance(data, dict):
				return data
		except Exception:
			continue
	return dict(_DEFAULT_SETTINGS)


CONFIG_DIR = os.path.join(_user_config_root(), APP_NAME)
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")


def ensure_settings_file() -> str:
	os.makedirs(CONFIG_DIR, exist_ok=True)
	if os.path.exists(SETTINGS_PATH):
		return SETTINGS_PATH

	template = _load_template_settings()
	try:
		with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
			json.dump(template, f, indent=2)
	except Exception:
		# Last-resort write using hardcoded defaults.
		with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
			json.dump(_DEFAULT_SETTINGS, f, indent=2)

	return SETTINGS_PATH


# Create user settings file on first import so all callers can read/write immediately.
ensure_settings_file()
