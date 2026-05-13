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
    # Cub Scouts
    8: {"name": "Tiger", "program": "Cub Scouts", "grade": 1},
    9: {"name": "Wolf", "program": "Cub Scouts", "grade": 2},
    10: {"name": "Bear", "program": "Cub Scouts", "grade": 3},
    11: {"name": "Webelos", "program": "Cub Scouts", "grade": 4},
    12: {"name": "Arrow of Light", "program": "Cub Scouts", "grade": 5},
    # Scouts BSA
    1: {"name": "Scout", "program": "Scouts BSA", "level": 1, "versionId": 84},
    2: {"name": "Tenderfoot", "program": "Scouts BSA", "level": 2, "versionId": 83},
    3: {"name": "Second Class", "program": "Scouts BSA", "level": 3, "versionId": 98},
    4: {"name": "First Class", "program": "Scouts BSA", "level": 4, "versionId": 99},
    5: {"name": "Star Scout", "program": "Scouts BSA", "level": 5, "versionId": 40},
    6: {"name": "Life Scout", "program": "Scouts BSA", "level": 6, "versionId": 41},
    7: {"name": "Eagle Scout", "program": "Scouts BSA", "level": 7, "versionId": 108},
}

BSA_RANK_NAMES = {"Scout", "Tenderfoot", "Second Class", "First Class",
                  "Star Scout", "Life Scout", "Eagle Scout"}

CUB_RANK_NAMES = {"Tiger", "Wolf", "Bear", "Webelos", "Arrow of Light"}
