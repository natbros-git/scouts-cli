# Scouts CLI — Architecture

## Overview

The Scouts CLI is a Python command-line tool that wraps the BSA Internet Advancement REST API (`api.scouting.org`). It provides programmatic access to scout advancement, rosters, messaging, and organization management. The CLI is designed for dual use: direct terminal interaction by humans (`--human` flag) and structured JSON consumption by AI agents (default).

## System Context

```
┌──────────────┐     HTTPS/JSON     ┌──────────────────────────┐
│  Scouts CLI  │ ◄────────────────► │  api.scouting.org        │
│  (Python)    │                    │  (BSA REST API)           │
└──────┬───────┘                    └──────────────────────────┘
       │                                        ▲
       │ reads/writes                            │
       ▼                                         │
┌──────────────┐                    ┌──────────────────────────┐
│ ~/.scouts-cli│                    │  auth.scouting.org       │
│  token.json  │                    │  (Session validation)    │
│  context.json│                    └──────────────────────────┘
│  roster-*.json
│  browser-profile/                 ┌──────────────────────────┐
│  audit/      │                    │  advancements.scouting.org│
└──────────────┘  ◄─── Playwright ─►│  (Web UI + Google OAuth)  │
                   (Chrome channel)  └──────────────────────────┘
```

The CLI authenticates via browser automation. When no valid JWT token exists, Playwright opens Chrome (using a persistent profile at `~/.scouts-cli/browser-profile/`) and navigates to `advancements.scouting.org`. If the persistent profile has valid Google OAuth cookies, the page auto-authenticates and the JWT is captured from `localStorage` silently (headless). If no session exists, a visible Chrome window opens for the user to complete Google sign-in. Tokens expire after ~8 hours; the CLI re-acquires them automatically using the stored session cookies.

A manual fallback is available: `scouts auth login --token "eyJ..."` to paste a JWT directly.

## Dependencies

### Python Version

Python **3.10+** is required. The codebase uses:
- Union type syntax (`list | None`) in type hints — requires 3.10+
- `datetime.fromisoformat()` with timezone-aware strings — requires 3.7+
- f-strings, `secrets` module, `typing.Optional` — requires 3.6+

### Third-Party Packages

| Package | Version | Purpose | Used By |
|---------|---------|---------|---------|
| `requests` | >=2.28.0 | HTTP client for all API calls | `client/scouting_client.py` |
| `urllib3` | (transitive via requests) | Retry logic (`urllib3.util.retry.Retry`) | `client/scouting_client.py` |
| `playwright` | >=1.40.0 | Browser automation for JWT token capture | `client/browser_auth.py` |

`requests` and `playwright` are the declared dependencies (`requirements.txt`). `urllib3` is a transitive dependency that ships with `requests` and is imported directly for the `Retry` class. Playwright uses the system Chrome binary (`channel='chrome'`), so no separate Chromium download is needed.

### Python Standard Library Usage

The following stdlib modules are used across the codebase:

| Module | Purpose | Used By |
|--------|---------|---------|
| `argparse` | CLI argument parsing and subcommand routing | `main.py` |
| `base64` | JWT payload decoding (urlsafe_b64decode), `x-esb-url` header encoding | `client/auth.py`, `client/scouting_client.py` |
| `json` | Token/context/cache file I/O, API response parsing | Nearly all modules |
| `os` | File path operations, directory creation, permissions, env vars | `config.py`, `client/auth.py`, `context.py`, `commands/roster.py`, `utils/safety.py` |
| `sys` | stderr output, stdin TTY detection, platform detection, exit codes | `main.py`, `utils/safety.py`, formatters |
| `time` | Cache age calculation (`time.time()`), API rate limiting (`time.sleep()`) | `commands/roster.py`, `commands/reference.py` |
| `datetime` | Token expiration checks, audit timestamps, formatter metadata | `client/auth.py`, `context.py`, `formatters/json_formatter.py`, `utils/safety.py` |
| `secrets` | Cryptographically random confirmation codes | `utils/safety.py` |
| `subprocess` | GUI dialog invocation (osascript/powershell/zenity) | `utils/safety.py` |
| `typing` | Type hints (`Optional`, `Tuple`) | `context.py`, `utils/safety.py` |

### External Services

| Service | Base URL | Authentication | Purpose |
|---------|----------|----------------|---------|
| BSA API | `https://api.scouting.org` | JWT Bearer token + `x-esb-url` header | All data read/write operations (27 endpoints) |
| BSA Auth | `https://auth.scouting.org` | JWT Bearer token | Session validation/refresh |
| BSA Web UI | `https://advancements.scouting.org` | Google OAuth + localStorage | JWT token source (accessed via Playwright) |
| Google OAuth | `https://accounts.google.com` | SSO provider | User signs in via Google (handled by the web UI) |

All API communication is HTTPS. The CLI does not make any unencrypted HTTP requests.

### Platform Dependencies

| Dependency | Platform | Purpose | Required? |
|------------|----------|---------|-----------|
| Google Chrome | All | Browser for OAuth login and token capture | Yes — used by Playwright with `channel='chrome'` |
| `osascript` | macOS | GUI confirmation dialog for message sending | No — falls back to terminal input |
| `powershell` | Windows | GUI confirmation dialog for message sending | No — falls back to terminal input |
| `zenity` / `kdialog` | Linux | GUI confirmation dialog for message sending | No — falls back to terminal input |

The GUI dialog is used only by `utils/safety.py` for the message send confirmation. When no GUI tool is available or the dialog is cancelled, the system falls back to terminal-based `input()` confirmation. When no TTY is attached (e.g., running under an AI agent), the GUI path is used by default.

### Filesystem Dependencies

All persistent state is stored under `~/.scouts-cli/`:

| File | Created By | TTL | Purpose |
|------|-----------|-----|---------|
| `~/.scouts-cli/token.json` | `auth.py` | ~8 hours (JWT expiry) | JWT token and decoded claims |
| `~/.scouts-cli/browser-profile/` | `browser_auth.py` | Persistent | Chromium user data dir (session cookies, localStorage) |
| `~/.scouts-cli/context.json` | `context.py` | 7 days (auto-refresh) | User identity, organizations, scout relationships |
| `~/.scouts-cli/roster-{orgGuid}.json` | `commands/roster.py` | 24 hours | Cached youth roster per organization |
| `~/.scouts-cli/audit/audit-YYYY-MM.jsonl` | `utils/safety.py` | Permanent | Audit trail of message send attempts |

File permissions: `token.json` is created with `0o600` (owner read/write only). All other files use default permissions.

## Module Architecture

```
scouts                          # Entry point script (shebang: #!/usr/bin/env python3)
scouts_cli/
├── __init__.py                 # Package version
├── __main__.py                 # python -m scouts_cli support
├── main.py                     # CLI parser + command routing
├── config.py                   # Constants (URLs, paths, timeouts, rank reference)
├── context.py                  # Local context cache manager
├── client/
│   ├── __init__.py             # Re-exports ScoutingClient + error classes
│   ├── auth.py                 # JWT token storage, validation, browser auth trigger
│   ├── browser_auth.py         # Playwright browser automation for token capture
│   ├── errors.py               # Exception hierarchy (6 error types)
│   └── scouting_client.py      # HTTP client with 27 API methods
├── commands/
│   ├── __init__.py             # Re-exports all 7 command classes
│   ├── advancement.py          # bulk-entry, status queries
│   ├── lookup.py               # ranks, adventures, requirements, dashboard
│   ├── message.py              # send, recipients, search
│   ├── org.py                  # org profile, dens, activities, list
│   ├── profile.py              # user profile, scouts, roles, training, registrations
│   ├── reference.py            # Full reference data dump
│   └── roster.py               # youth/adult/parent rosters, search, resolve
├── formatters/
│   ├── __init__.py             # Re-exports JsonFormatter + HumanFormatter
│   ├── json_formatter.py       # Structured JSON output (agent-facing)
│   └── human_formatter.py      # Table/text output (human-facing)
└── utils/
    ├── __init__.py             # Re-exports confirm_send_message
    └── safety.py               # GUI/terminal confirmation for message sends
```

## Component Interaction

### Request Flow

```
User runs command
    │
    ▼
main.py: parse args, select formatter (JSON or Human)
    │
    ▼
main.py: create ScoutingClient(verbose=flag)
    │
    ├── ScoutingAuth.get_token()     ← reads ~/.scouts-cli/token.json
    │       │
    │       ├── if valid → return token (fast path)
    │       ├── if missing/expired → acquire_token_via_browser()
    │       │       ├── Phase 1: headless Chrome (15s) — silent auto-refresh
    │       │       └── Phase 2: headed Chrome (5min) — user signs in
    │       └── if browser fails → raises AuthenticationError
    │
    ├── creates requests.Session with:
    │       ├── Retry strategy (3 retries, exponential backoff)
    │       ├── Authorization: Bearer {JWT}
    │       ├── Accept: application/json
    │       └── x-esb-url: base64(referrer URL)
    │
    ▼
main.py: auto-populate or refresh context if stale
    │
    ▼
main.py: route to CommandClass.method()
    │
    ▼
CommandClass: calls self.client.api_method()
    │
    ▼
ScoutingClient._make_request(method, path, **kwargs)
    │
    ├── Constructs full URL: {base_url}{path}
    ├── Adds timeout (30s default)
    ├── Verbose logging to stderr if enabled
    │
    ▼
ScoutingClient._handle_response(response)
    │
    ├── 2xx → parse JSON (or return {} for empty body)
    ├── 4xx/5xx → map status to error class via ERROR_MAP
    │       400 → ValidationError
    │       401 → AuthenticationError
    │       403 → AuthorizationError
    │       404 → NotFoundError
    │       429 → RateLimitError
    │       other → ScoutingError
    │
    ▼
CommandClass: processes/simplifies raw API response
    │
    ▼
Formatter.output_result(result) → stdout (JSON or table)
```

### Caching Architecture

Four independent caches reduce API calls and store persistent state:

1. **Token cache** (`token.json`): Written on `auth login` or after browser-based token capture. Expires with the JWT (~8 hours). When expired, the CLI automatically re-acquires a token via Playwright browser automation using session cookies from the browser profile.

2. **Browser profile** (`browser-profile/`): Playwright persistent context directory. Stores Chrome session cookies (Google OAuth) and localStorage data. Survives across CLI invocations. After the user completes Google sign-in once, subsequent token refreshes use these cookies automatically without human interaction.

3. **Context cache** (`context.json`): Aggregates data from 3 API calls (`get_person_profile`, `get_my_scouts`, `get_role_types`) into a single local file. Auto-populates on first use. Auto-refreshes when older than 7 days. Used by `org list`, `roster resolve`, and any command that needs the user's identity without an explicit API call.

4. **Roster cache** (`roster-{orgGuid}.json`): One file per organization. Written by `roster list` and `roster search`. TTL of 24 hours. All roster commands (`list`, `search`) check cache first. `--refresh` flag bypasses cache.

None of these caches share state. Each is read and written independently.

## Error Handling

### Exception Hierarchy

```
Exception
└── ScoutingError                 # Base — catch-all for API errors
    ├── AuthenticationError       # 401 or missing/expired token
    ├── AuthorizationError        # 403 — wrong role for this unit
    ├── BrowserAuthError          # Browser-based login failed or timed out
    ├── NotFoundError             # 404 — invalid ID
    ├── ValidationError           # 400 — bad request data
    └── RateLimitError            # 429 — too many requests
```

Every error class includes a `suggestion` field with human-readable remediation advice. Errors are serialized to JSON (via `to_dict()`) by the `JsonFormatter` or printed as text by the `HumanFormatter`.

### Retry Strategy

The HTTP client retries automatically for transient failures:
- **Max retries:** 3
- **Backoff factor:** 2 (exponential: 0s, 2s, 4s)
- **Retried status codes:** 429, 500, 502, 503, 504
- Retries are handled by `urllib3.util.retry.Retry` via `requests.adapters.HTTPAdapter`

Non-retryable errors (400, 401, 403, 404) are raised immediately.

## Safety Controls

### Message Send Confirmation

The `message send` command has a mandatory human confirmation gate that cannot be bypassed programmatically:

1. A random confirmation code is generated (e.g., `SEND-7X3K`)
2. The user sees recipient count, subject, and body preview
3. The user must type the exact code to proceed
4. All attempts (confirmed and cancelled) are logged to the audit file

In non-TTY environments (e.g., AI agent sessions), a macOS system dialog (`osascript`) is displayed. This ensures a human must physically interact with a dialog box before any email is sent to scout families.

### Bulk Entry (No Confirmation)

The `advancement bulk-entry` command does NOT have a confirmation gate. Use `--dry-run` to preview what would be submitted before running the actual write. The `--dry-run` flag returns the full request payload without making any API call.

## Output Formats

### JSON (Default)

All commands produce structured JSON to stdout:
```json
{
  "result": { ... },
  "metadata": {
    "timestamp": "2026-02-16T00:00:00+00:00"
  }
}
```

Errors go to stderr in the same JSON structure with an `error` field, `message`, and `suggestion`.

### Human (`--human`)

The `HumanFormatter` renders dicts as key-value pairs and lists-of-dicts as aligned tables. Nested objects are indented. Lists longer than 5 items are truncated with "... and N more".

## Data Flow Summary

| Operation | Cache Read | API Calls | Cache Write | Side Effects |
|-----------|-----------|-----------|-------------|--------------|
| `auth login` (browser) | browser-profile/ | Playwright → web UI | token.json, browser-profile/ | Opens Chrome if needed |
| `auth login --token` | — | — | token.json | — |
| `auth status` | token.json | — | — | — |
| `context show` | context.json | — | — | — |
| `context refresh` | — | 3 calls | context.json | — |
| `roster list` | roster-{org}.json | 1 call (on miss) | roster-{org}.json | — |
| `roster resolve` | context.json | 1 call (on miss) | — | — |
| `advancement status` | — | 1 call | — | — |
| `advancement bulk-entry` | — | 1 call | — | Writes advancement data |
| `message send` | — | 1 call | audit log | Sends email, requires confirmation |
| `reference dump` | — | 1 + N calls | optional file | Rate-limited (100ms between calls) |

## Configuration Constants

Defined in `config.py`:

| Constant | Value | Purpose |
|----------|-------|---------|
| `API_BASE_URL` | `https://api.scouting.org` | Base URL for all data API calls |
| `AUTH_BASE_URL` | `https://auth.scouting.org` | Base URL for session validation |
| `WEB_BASE_URL` | `https://advancements.scouting.org` | `x-esb-url` header + browser auth navigation target |
| `TOKEN_DIR` | `~/.scouts-cli` | Directory for all persistent state |
| `REQUEST_TIMEOUT` | 30 seconds | HTTP request timeout |
| `MAX_RETRIES` | 3 | Retry count for transient failures |
| `BACKOFF_FACTOR` | 2 | Exponential backoff multiplier |
| `RETRY_STATUS_CODES` | [429, 500, 502, 503, 504] | HTTP codes that trigger retry |
| `BROWSER_PROFILE_DIR` | `~/.scouts-cli/browser-profile` | Playwright persistent context (Chrome session cookies) |
| `BROWSER_HEADLESS_TIMEOUT` | 15 seconds | Max wait for headless auto-refresh |
| `BROWSER_HEADED_TIMEOUT` | 300 seconds (5 min) | Max wait for user to complete login |
| `BROWSER_POLL_INTERVAL` | 2.0 seconds | Interval between localStorage polls |
| `CONTEXT_MAX_AGE` | 7 days (604800s) | Context cache TTL |
| `ROSTER_CACHE_MAX_AGE` | 24 hours (86400s) | Roster cache TTL |
