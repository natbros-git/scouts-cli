"""Configuration constants for Scouts CLI."""

import os

# API endpoints
API_BASE_URL = "https://api.scouting.org"
AUTH_BASE_URL = "https://auth.scouting.org"
WEB_BASE_URL = "https://advancements.scouting.org"
LOGIN_URL = "https://my.scouting.org/api/users"

# Token storage
TOKEN_DIR = os.path.expanduser("~/.scouts-cli")
TOKEN_FILE = os.path.join(TOKEN_DIR, "token.json")

# HTTP configuration
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
BACKOFF_FACTOR = 2
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

# Browser auth configuration
BROWSER_PROFILE_DIR = os.path.join(TOKEN_DIR, "browser-profile")
BROWSER_HEADLESS_TIMEOUT = 15     # seconds for headless auto-refresh attempt
BROWSER_HEADED_TIMEOUT = 300      # seconds (5 min) for user to complete login
BROWSER_POLL_INTERVAL = 2.0       # seconds between localStorage polls

# Rank reference data (rankId -> program info)
RANKS = {
    8: {"name": "Tiger", "program": "Cub Scouts", "grade": 1},
    9: {"name": "Wolf", "program": "Cub Scouts", "grade": 2},
    10: {"name": "Bear", "program": "Cub Scouts", "grade": 3},
    11: {"name": "Webelos", "program": "Cub Scouts", "grade": 4},
    12: {"name": "Arrow of Light", "program": "Cub Scouts", "grade": 5},
}
