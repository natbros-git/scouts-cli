# Scouts CLI — Agent Integration Guide

This document is for AI agents consuming the Scouts CLI. It covers setup, the data model, common pitfalls, and correct patterns for advancement workflows.

## Getting Started

**Before using any CLI commands, run the bootstrap script** to verify the system has all prerequisites and install missing dependencies:

```bash
./bootstrap                    # JSON output — check if "ready": true
./bootstrap --install          # Auto-install missing Python packages
```

Bootstrap checks: Python 3.10+, pip, Google Chrome, `requests`, `playwright`, and the `~/.scouts-cli/` data directory. If `"ready": true`, proceed to authentication. If any checks fail, the output includes a `"fix"` field with the remediation command.

After bootstrap passes, authenticate:

```bash
./scouts auth login            # Opens Chrome for Google sign-in (first time)
./scouts auth status           # Verify: should return "status": "authenticated"
```

### Platform Notes

The CLI runs on macOS, Linux, and Windows. The scripts use `#!/usr/bin/env python3` shebangs, which work on macOS and Linux but not natively on Windows.

| | macOS / Linux | Windows |
|---|---|---|
| Bootstrap | `./bootstrap` | `python bootstrap` |
| CLI commands | `./scouts auth login` | `python scouts auth login` |
| Data directory | `~/.scouts-cli/` | `%USERPROFILE%\.scouts-cli\` |
| Confirmation dialogs | macOS: `osascript`, Linux: `zenity`/`kdialog` | PowerShell `InputBox` |

**Agents must detect the platform and use the correct invocation.** On Windows, always prefix commands with `python` (e.g., `python scouts roster list ...`). On macOS/Linux, use `./scouts` or add the CLI directory to `PATH`.

## Core Concepts

### Identity Resolution

Scouts are identified by multiple IDs. The correct ID depends on the operation:

| Operation | ID to use | Field name |
|-----------|-----------|------------|
| Advancement status (read) | `memberId` | `--members` |
| Bulk entry (write) | `userId` | `--users` |
| Messaging (send) | `memberId` | `--bcc`, `--to` |
| Profile lookup | `userId` | positional arg |

**To resolve a scout's name to their IDs**, use:
```bash
scouts roster resolve "James"
```
This searches across ALL organizations the current user has access to and returns `userId`, `memberId`, `orgGuid`, `unitType`, and `program` for each match.

### Organizations

A parent may have scouts in multiple organizations (e.g., Pack 206 for Cub Scouts, Troop 111 for Scouts BSA). Every org-scoped operation requires an `--org` GUID.

```bash
scouts org list    # Lists all orgs from cached context
```

### Local Context Cache

The CLI maintains `~/.scouts-cli/context.json` with the user's identity, organizations, and scout relationships. This avoids repeated API lookups.

- Auto-populates on first authenticated command
- Auto-refreshes after 7 days
- `scouts context show` displays current cache contents
- `scouts context refresh` forces a fresh pull from the API

Use the context cache to avoid re-querying static data like scout names, member IDs, and org GUIDs.

## CLI Command Reference

All commands output JSON by default. Add `--human` for human-readable tables. Add `--verbose` for HTTP request logging.

### Authentication & Session

Authentication is automatic. When any command needs a valid token and none exists (or the token has expired), the CLI acquires one via Playwright browser automation:

1. **Headless attempt** (15s): Chrome launches silently with a persistent profile. If session cookies are warm, the token is captured with no browser window.
2. **Headed fallback** (5min): If headless fails, a visible Chrome window opens for the user to complete Google sign-in.

After the first login, token refreshes happen automatically with no human interaction.

```bash
scouts auth login                            # Browser-based login (opens Chrome if needed)
scouts auth login --token "eyJhbG..."        # Manual fallback (paste JWT from DevTools)
scouts auth status                           # Check auth status (authenticated/expired)
scouts auth logout                           # Remove cached token
```

**Environment variable:** Set `SCOUTS_NO_BROWSER=1` to disable browser auth (useful for CI). In this mode, the CLI requires a manually provided token.

### Context Cache

```bash
scouts context show                          # Display cached scouts, orgs, user info
scouts context refresh                       # Force re-fetch from API
scouts context path                          # Print cache file path
```

### Organization Management

```bash
scouts org list                              # List all your organizations with GUIDs
scouts org profile --org {GUID}              # Detailed org profile (charter, address, key3)
scouts org dens --org {GUID}                 # List dens/patrols (sub-units) with types
scouts org activities --org {GUID}           # Activities dashboard (campouts, service, hikes)
```

### Roster Operations

```bash
scouts roster list --org {GUID}              # Full youth roster (names, IDs, dens, ranks)
scouts roster search --org {GUID} "James"    # Search youth by name (case-insensitive)
scouts roster resolve "James"                # Cross-org name-to-ID lookup (all orgs)
scouts roster adults --org {GUID}            # Adult leader roster
scouts roster parents --org {GUID}           # Parent-youth relationships
```

**Cache behavior:** `roster list`, `roster search`, and `roster resolve` use a local cache (24h TTL). Add `--refresh` to force a fresh API call.

### Reference Data (Ranks, Adventures, Requirements)

```bash
scouts rank list                             # All ranks (optionally --program-id N)
scouts adventure list                        # All adventures (optionally --rank-id N)
scouts adventure requirements {ID} --version-id {VID}  # Requirements for one adventure
scouts merit-badge list                      # All merit badges
scouts award list                            # All awards
scouts ss-elective list                      # All Sea Scout electives
scouts reference dump -o reference-data.json # Full rank/adventure/requirement tree
```

### User Profile & Permissions

```bash
scouts profile me                            # Your profile (name, memberId, orgs, emails)
scouts profile my-scouts                     # Scouts linked to you (parent/guardian)
scouts profile roles                         # Your roles and permissions per org
scouts profile training                      # YPT training status (Active/Expired, dates)
scouts profile registrations                 # Membership registration history
scouts profile registrations --org {GUID}    # Filter registrations to one org
```

### Youth-Specific Profiles

These require the scout's `userId` (not `memberId`):

```bash
scouts profile scout {userId}                # Full scout profile
scouts profile merit-badges {userId}         # Merit badge progress (percent, dates)
scouts profile ranks {userId}                # Rank progression (per program)
scouts profile leadership {userId}           # Leadership position history (dates, days)
scouts profile activity-summary {userId}     # Camping, hiking, service logs
```

### Advancement Status & Bulk Entry

```bash
# Read: check adventure progress (uses memberId)
scouts advancement status --org {GUID} --adventure {ID} --members {memberId1},{memberId2},...

# Write: mark requirements complete (uses userId)
scouts advancement bulk-entry --org {GUID} --adventure {ID} --version-id {VID} \
    --users {userId1},{userId2} --requirements {reqId1},{reqId2} --date 2026-02-15 \
    --approve --dry-run

# Dashboard: org-level advancement stats
scouts dashboard {GUID}
```

### Messaging

```bash
scouts message recipients --org {GUID}       # List available recipients (leaders, youth, parents)
scouts message search --org {GUID} "John"    # Search recipients by name
scouts message send --org {GUID} --bcc {memberIds} \
    --subject "Subject" --body "Body text" --dry-run
```

**Safety:** `message send` requires a confirmation dialog before sending (shows recipient count, subject, random code). Uses platform-native dialogs: `osascript` on macOS, PowerShell `InputBox` on Windows, `zenity`/`kdialog` on Linux. Falls back to terminal input if no GUI is available. Use `--dry-run` to preview without sending.

## Adventure Completion — How to Interpret API Responses

### The Rules

**Adventure completion is determined by the adventure-level `status` field, NEVER by counting requirements.**

When you query advancement status:
```bash
scouts advancement status --org {GUID} --adventure {ID} --members {memberIds}
```

Each record in the response has:
- An adventure-level `status` field (the authoritative indicator)
- A `requirements` array (may be incomplete, empty, or misleading)

### Adventure-Level Status Values

| `status` value | Meaning | Is the adventure done? |
|----------------|---------|----------------------|
| `"Awarded"` | Fully complete, officially awarded | **Yes** |
| `"Leader Approved"` | Complete, leader has approved | **Yes** |
| `"Completed"` | Requirements done, pending approval | **Yes** |
| `"Started"` | In progress | **No** |
| `null` | Not started — no activity recorded | **No** |

### Requirement-Level Status Hierarchy

Individual requirements progress through these states:

```
null → "Started" → "Completed" → "Leader Approved"
```

| Req `status` | Meaning | Count as done for progress reports? |
|--------------|---------|-------------------------------------|
| `null` | Not started | No |
| `"Started"` | Begun but not finished | No |
| `"Completed"` | Scout did the work, **pending leader approval** | **Yes** |
| `"Leader Approved"` | Leader verified and approved | **Yes** |

**Key distinction — `"Completed"` vs `"Leader Approved"`:**
- Both mean the scout has finished the requirement. For **progress reporting**, treat both as done.
- For **approval workflows** ("what still needs leader sign-off?"), only `"Leader Approved"` is fully signed off. `"Completed"` requirements are finished but awaiting individual leader verification.
- An adventure can be `"Leader Approved"` at the adventure level even if some individual requirements only show `"Completed"`. The leader approved the adventure as a whole without individually approving every requirement.

**Note on `"Started"` at the requirement level:** In observed data (Feb 2026), this status appears only on non-actionable system artifact requirements, never on real requirements. However, agents should still handle it defensively.

### The Empty Requirements Trap

**This is the most common mistake an agent can make with this API.**

The `requirements` array in the response does NOT always reflect the true state of individual requirements. There are three scenarios where it can mislead:

#### Scenario 1: Empty array, adventure not started
```json
{
  "status": null,
  "requirements": []
}
```
**Interpretation:** Not started. Zero tracking data exists. **This is NOT "done."**

#### Scenario 2: Empty array, adventure marked "Started"
```json
{
  "status": "Started",
  "requirements": []
}
```
**Interpretation:** Some activity exists but no individual requirements have been tracked. **This is NOT "done."** The adventure may have been started through the web UI without recording individual completions.

#### Scenario 3: Adventure awarded, but requirements not individually tracked
```json
{
  "status": "Leader Approved",
  "requirements": [
    {"id": 2289, "status": null},
    {"id": 2290, "status": null}
  ]
}
```
**Interpretation:** The adventure IS complete (leader approved it at the adventure level), but individual requirements were not recorded. This can happen when a leader awards an adventure without going through individual requirement check-offs.

### Correct Completion Checks (Pseudocode)

```python
# Adventure completion — use the adventure-level status
def is_adventure_complete(record):
    """Check if a scout has completed an adventure."""
    status = record.get('status')
    return status in ('Awarded', 'Leader Approved', 'Completed')

# Requirement completion — both "Completed" and "Leader Approved" count as done
def is_requirement_done(req):
    """Check if a single requirement is finished (for progress reporting)."""
    return req.get('status') in ('Completed', 'Leader Approved')

# Requirement needs leader approval — only "Completed" (not yet approved)
def needs_leader_approval(req):
    """Check if a requirement is done but awaiting leader sign-off."""
    return req.get('status') == 'Completed'

# WRONG — do not do this:
def is_adventure_complete_WRONG(record):
    reqs = record.get('requirements', [])
    incomplete = [r for r in reqs if r.get('status') != 'Completed']
    return len(incomplete) == 0  # Bug: returns True when requirements is empty

# ALSO WRONG — only checking for "Completed", missing "Leader Approved":
def is_req_done_WRONG(req):
    return req.get('status') == 'Completed'  # Misses "Leader Approved" reqs
```

### Non-Actionable Requirements

Each 2024+ adventure includes system artifact "requirements" that are not real tasks. These should be excluded from all calculations.

**How to identify them:**
- `number` field is `null` or `"None"`
- `name` field contains `<a href=` (link to scouting.org) or starts with `<strong>Note:`

**Known IDs (Bear rank, as of Feb 2026):** 2790, 2863, 2864, 2865, 2866, 2867, 2868

When iterating requirements, filter these out:
```python
real_reqs = [r for r in requirements if r.get('number') is not None]
```

## Generating Advancement Reports

### Correct Pattern

1. **Get the roster** to identify scouts by den type:
   ```bash
   scouts roster list --org {GUID}
   ```
   Filter by `denType` (e.g., `"bears"` for Bear den).

2. **Batch-query each required adventure** with all scouts' member IDs:
   ```bash
   scouts advancement status --org {GUID} --adventure {ID} --members {id1},{id2},...
   ```
   The API supports batching all member IDs in a single call per adventure.

3. **For each scout, check the adventure-level `status`** to determine completion:
   - `"Awarded"` / `"Leader Approved"` / `"Completed"` = adventure is done
   - Anything else = adventure has remaining work

4. **For incomplete adventures**, examine the `requirements` array to identify specific remaining items. Exclude non-actionable requirements.

5. **Handle the empty-requirements case**: If `requirements` is empty but `status` is not an awarded state, report the adventure as having ALL requirements remaining (look up the full list from `reference-data.json` or the adventure requirements API).

### Version Selection — ALWAYS Use Newest Versions

**When reading advancement status or writing requirement completions, always use the newest (highest) `versionId` for each adventure.** This applies to ALL operations — querying status, marking requirements complete, and generating reports.

The reference data file and API both contain multiple versions of the same adventure (pre-2024 and 2024+ editions). The 2024+ versions reflect the current BSA requirements. Using an older version will query or write against outdated requirement sets that do not match what scouts are actually working on.

**Rules:**
1. When the API returns adventures, prefer the record with the highest `versionId` for each adventure
2. When `reference-data.json` lists multiple versions of the same adventure, use the one with the higher `versionId`
3. When constructing `bulk-entry` commands, the `--version-id` parameter MUST specify the newest version
4. When querying `advancement status`, the API returns the version the scout is tracked under — but if a scout has no data yet, use the newest version when starting new entries

**How to determine the newest version:** Query `scouts adventure list --rank-id {rankId}` and for adventures that appear multiple times, select the one with the higher `versionId`. Or consult `reference-data.json` and sort by `versionId` descending.

**2024+ required Bear adventures:**

| Adventure | ID | Version ID | Reqs |
|-----------|----|-----------|------|
| Bear Habitat | 115 | 286 | 9 |
| Bear Strong | 116 | 212 | 5 |
| Bobcat (Bear) | 119 | 211 | 8 |
| Fellowship | 122 | 288 | 4 |
| Paws for Action | 124 | 287 | 4 |
| Standing Tall | 127 | 213 | 4 |

## Bulk Entry (Writing Advancement Data)

### Prerequisites
- Use `userId` (NOT `memberId`) for the `--users` parameter
- Scouts with `userId: null` cannot be written to
- The system accepts writes to already-awarded adventures (tested Feb 2026)

### Safety
- Human confirmation is required before sending messages (`message send`)
- `--dry-run` previews what would be submitted without writing
- Bulk entry does NOT have a confirmation dialog — use `--dry-run` to verify before submitting

### Example Workflow

```bash
# 1. Resolve scout name
scouts roster resolve "James"
# Returns: userId=12474560, memberId=14257739, orgGuid=F4C19DEB-...

# 2. Check current status
scouts advancement status --org F4C19DEB-... --adventure 124 --members 14257739

# 3. Preview the write
scouts advancement bulk-entry --org F4C19DEB-... --adventure 124 --version-id 287 \
    --users 12474560 --requirements 2632,2633 --date 2026-02-15 --approve --dry-run

# 4. Submit
scouts advancement bulk-entry --org F4C19DEB-... --adventure 124 --version-id 287 \
    --users 12474560 --requirements 2632,2633 --date 2026-02-15 --approve
```

## Reference Data

The file `reference-data.json` contains the complete rank/adventure/requirement tree dumped from the API. It includes:

- All ranks (Lion through Arrow of Light for Cub Scouts)
- All adventures per rank (both required and elective, both pre-2024 and 2024 versions)
- All requirements per adventure (with IDs, numbers, and descriptions)

To refresh:
```bash
scouts reference dump -o reference-data.json
```

## Key Organization GUIDs

These are specific to the current user's account and stored in context:

```bash
scouts context show   # Displays all cached orgs with GUIDs
```
