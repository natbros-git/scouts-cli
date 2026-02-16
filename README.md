# Scouts CLI

Command-line interface for BSA Internet Advancement (Scoutbook Plus). Wraps the `api.scouting.org` REST API for programmatic access to scout advancement, rosters, messaging, and organization management.

## Setup

**macOS / Linux:**
```bash
./bootstrap --human                        # Check prerequisites
./bootstrap --install                      # Install missing Python packages
./scouts auth login                        # Opens Chrome for Google sign-in
```

**Windows:**
```cmd
python bootstrap --human                   # Check prerequisites
python bootstrap --install                 # Install missing Python packages
python scouts auth login                   # Opens Chrome for Google sign-in
```

The `bootstrap` script checks that your system has everything the CLI needs: Python 3.10+, pip, Google Chrome, and the Python packages (`requests`, `playwright`). With `--install`, it automatically installs any missing Python packages. Chrome must be installed manually.

On first run, a Chrome window opens to `advancements.scouting.org` for Google sign-in. After that, token refreshes happen automatically (no browser window). Tokens expire after ~8 hours; the CLI re-acquires them silently using stored session cookies.

**Manual fallback** (if browser auth isn't available):
```bash
./scouts auth login --token "eyJhbG..."    # Paste JWT from browser DevTools
```

**Prerequisites:** Python 3.10+, Google Chrome, `requests`, `playwright`.

### Platform Differences

The CLI runs on macOS, Linux, and Windows. The `scouts` and `bootstrap` scripts use `#!/usr/bin/env python3` shebangs. On macOS and Linux these scripts are directly executable (`./scouts`). On Windows, shebangs are not natively supported — prefix all commands with `python` (e.g., `python scouts auth status`).

| Behavior | macOS / Linux | Windows |
|----------|---------------|---------|
| Run scripts | `./scouts ...` | `python scouts ...` |
| Data directory | `~/.scouts-cli/` | `%USERPROFILE%\.scouts-cli\` |
| Send confirmation dialog | `osascript` (macOS), `zenity` (Linux) | PowerShell `InputBox` |
| Token file permissions | Restricted to owner (`0600`) | Read-only flag only (Windows limitation) |

## Quick Start

ID formats used in examples below:
- `orgGuid`: UUID — `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX` (8-4-4-4-12 hex)
- `userId`: numeric, typically 8 digits
- `memberId`: numeric, typically 9 digits

```bash
# Check auth
scouts auth status

# Your profile and scouts
scouts profile me
scouts profile my-scouts

# List organizations (uses cached context)
scouts org list

# Roster operations
scouts roster list --org {org-guid}
scouts roster search --org {org-guid} "Alex"
scouts roster resolve "Alex"           # Cross-org name lookup

# Advancement status and bulk entry
scouts advancement status --org {org-guid} --adventure 124 --members {member-id}
scouts advancement bulk-entry --org {org-guid} --adventure 124 --version-id 287 \
    --users {user-id} --requirements 2632 --date 2026-02-15 --approve

# Messaging
scouts message send --org {org-guid} --bcc {member-id} \
    --subject "Meeting reminder" --body "Pack meeting Thursday at 6pm"

# Local context cache
scouts context show
scouts context refresh
```

## Local Context Cache

On first use, the CLI auto-populates `~/.scouts-cli/context.json` with the user's identity, organizations, and scout relationships. This avoids repeated API calls for rarely-changing data.

- **TTL:** 7 days (auto-refreshes when stale)
- **Manual refresh:** `scouts context refresh`
- **Used by:** `roster resolve`, `org list`

## Agent Integration Guide

This CLI is designed for both human and AI agent use. JSON output (default) is machine-readable; `--human` flag produces formatted tables.

### Resolving Scout Names to IDs

Use `roster resolve` for natural-language name-to-ID resolution across all organizations:

```bash
scouts roster resolve "Alex"
# Returns: userId, memberId, orgGuid, unitType, program for each match
```

The write endpoint (`bulk-entry`) requires `userId` (NOT `memberId`). Some scouts have `userId: null` and cannot be written to.

### 2024+ Requirements

Always use 2024+ adventure versions when working with current scouts. The reference data (`reference-data.json`) contains both pre-2024 and 2024 versions. When deduplicating, prefer the higher `versionId` for each adventure.

### Adventure Completion Status — Critical Interpretation Rules

**Do NOT determine adventure completion by counting incomplete requirements.** The API has several response patterns that can mislead:

| Scenario | How it looks | Correct interpretation |
|----------|-------------|----------------------|
| Adventure truly complete | `status: "Awarded"`, all reqs `"Completed"` | Done |
| Adventure awarded but not individually tracked | `status: "Leader Approved"`, reqs have `status: null` or `requirements: []` | Done (adventure level), but individual req data missing |
| Adventure not started, no tracking data | `status: null`, `requirements: []` | **NOT done** — no data exists |
| Adventure started, no req-level tracking | `status: "Started"`, `requirements: []` | **NOT done** — activity exists but no individual completion |
| Adventure in progress | `status: "Started"`, mix of completed/null reqs | In progress |

**The reliable completion indicator is the adventure-level `status` field:**
- `"Awarded"` or `"Leader Approved"` = adventure is complete
- `"Started"` = in progress (regardless of requirement count)
- `null` = not started

**Common mistake:** Treating adventures with an empty `requirements` array as "done" because zero requirements are incomplete. An empty array means no tracking data exists, NOT that all requirements are finished.

### Non-Actionable Requirements

Each 2024+ adventure includes system artifact "requirements" that aren't real tasks (links to scouting.org pages, notes about alternative paths). These have `number: null` in the API and contain HTML link tags in the `name` field. Filter them out when calculating completion percentages or generating reports.

### Generating Advancement Reports

When producing advancement reports for a den or group of scouts:

1. Query each required adventure with all scouts' member IDs in a single batch call
2. Use the adventure-level `status` field to determine completion — NOT the requirement array
3. For adventures that are NOT awarded, count individual incomplete requirements (excluding non-actionable ones)
4. Present both the adventure-level summary and the per-requirement detail

Example workflow:
```bash
# Get roster to find Bear scouts
scouts roster list --org {org-guid} | jq '.members[] | select(.denType == "bears")'

# Query advancement status for each required adventure (batch all member IDs)
scouts advancement status --org {org-guid} --adventure 115 --members {member-id-1},{member-id-2},...

# Check adventure-level status field, not just requirement counts
```

### Messaging Safety

The `message send` command requires human confirmation via a platform-native dialog before sending. This prevents accidental mass emails. The confirmation shows recipient count, subject, and a random code the user must type. Use `--dry-run` to preview without sending.

### Key Identifiers

| ID | Used for | Format |
|----|----------|--------|
| `orgGuid` | All org-scoped operations | UUID: `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX` (8-4-4-4-12 hex) |
| `userId` | Write operations (bulk-entry) | Numeric, typically 8 digits |
| `memberId` | Read operations (advancement status), messaging | Numeric, typically 9 digits |
| `adventureId` | Adventure operations | Numeric (e.g., `124` for Paws for Action) |
| `versionId` | Specifying adventure version | Numeric (e.g., `287` for the 2024 version) |
| `requirementId` | Marking individual requirements | Numeric (e.g., `2632`) |

## Authentication

The CLI authenticates automatically using Playwright browser automation with a persistent Chrome profile.

**How it works:**
1. If a valid JWT token exists in `~/.scouts-cli/token.json`, it is used directly (fast path).
2. If no valid token exists, Playwright launches Chrome headlessly with a persistent profile at `~/.scouts-cli/browser-profile/`. If session cookies are warm, the token is captured silently in ~5 seconds.
3. If headless fails (no session cookies), Chrome opens visibly for the user to complete Google sign-in. The token is captured automatically once login completes.

**Token lifecycle:** ~8 hours. After expiration, the CLI re-acquires a fresh token using stored session cookies — no human interaction needed.

**Disable browser auth:** Set `SCOUTS_NO_BROWSER=1` for CI/headless environments. The CLI will require a manually provided token.

**Dependencies:** Google Chrome must be installed. Playwright uses it via `channel='chrome'` (no Chromium download needed).

## Project Structure

```
cli/
  bootstrap                 # Prerequisite checker and dependency installer
  scouts                    # Entry point script
  requirements.txt          # Python dependencies (requests, playwright)
  reference-data.json       # Cached rank/adventure/requirement tree
  scouts_cli/
    main.py                 # CLI argument parsing and routing
    config.py               # API URLs, token paths, timeouts, rank reference
    context.py              # Local context cache manager
    client/
      scouting_client.py    # HTTP client for api.scouting.org
      auth.py               # JWT token management + browser auth trigger
      browser_auth.py       # Playwright browser automation for token capture
      errors.py             # Exception hierarchy (6 error types)
    commands/
      advancement.py        # bulk-entry, status queries
      lookup.py             # Ranks, adventures, requirements, dashboard
      message.py            # Messaging (send, recipients, search)
      org.py                # Organization profile, dens, activities, list
      profile.py            # User/scout profiles, merit badges, ranks
      reference.py          # Reference data dump
      roster.py             # Roster list, search, resolve, adults, parents
    formatters/
      json_formatter.py     # JSON output (default)
      human_formatter.py    # Human-readable table output
    utils/
      safety.py             # Confirmation dialogs for destructive operations
```
