"""Local context manager for Scouts CLI.

Maintains a cached context file at ~/.scouts-cli/context.json that stores
the user's identity, organizations, and scout relationships. This avoids
repeated API calls for data that rarely changes (names, IDs, org mappings).

The context auto-populates on first use and can be force-refreshed with
`scouts context refresh`. Agent consumers can also read the file directly.

Context file structure:

    ID formats:
      orgGuid    — UUID: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX (8-4-4-4-12 hex)
      personGuid — UUID: same format as orgGuid
      userId     — numeric, typically 8 digits (e.g., 10000001)
      memberId   — numeric, typically 9 digits (e.g., 100000001)

{
    "version": 1,
    "lastRefreshed": "2026-02-16T00:10:00Z",
    "user": {
        "userId": 10000001,
        "personGuid": "{person-guid}",
        "memberId": 100000001,
        "firstName": "Jane",
        "lastName": "Smith",
        "fullName": "Jane Smith",
        "email": "..."
    },
    "organizations": [
        {
            "orgGuid": "{org-guid}",
            "name": "Pack 1234",
            "unitType": "Pack",
            "unitNumber": "1234",
            "program": "Cub Scouting",
            "roles": ["Den Leader", "Parent/Guardian"],
            "scouts": [
                {"name": "Alex Smith", "userId": "10000002", "memberId": "100000002"},
                ...
            ]
        },
        ...
    ],
    "scouts": [
        {
            "firstName": "Sam",
            "lastName": "Smith",
            "fullName": "Sam Smith",
            "userId": "10000003",
            "memberId": "100000003",
            "orgGuid": "{org-guid}",
            "unitType": "Troop",
            "unitNumber": "5678",
            "program": "Scouts BSA",
            "positions": ["Scouts BSA", "Scribe"]
        },
        ...
    ]
}
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

from .config import TOKEN_DIR

CONTEXT_FILE = os.path.join(TOKEN_DIR, "context.json")
CONTEXT_VERSION = 1
CONTEXT_MAX_AGE = 7 * 86400  # 7 days before suggesting refresh


class ScoutContext:
    """Manages the local context cache."""

    def __init__(self):
        self._data = None

    def _load(self) -> Optional[dict]:
        """Load context from disk."""
        if self._data is not None:
            return self._data
        if not os.path.exists(CONTEXT_FILE):
            return None
        try:
            with open(CONTEXT_FILE) as f:
                self._data = json.load(f)
            return self._data
        except (json.JSONDecodeError, IOError):
            return None

    def _save(self, data: dict):
        """Save context to disk."""
        os.makedirs(TOKEN_DIR, exist_ok=True)
        data['version'] = CONTEXT_VERSION
        data['lastRefreshed'] = datetime.now(timezone.utc).isoformat()
        with open(CONTEXT_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        self._data = data

    def exists(self) -> bool:
        """Check if context file exists and is valid."""
        data = self._load()
        return data is not None and data.get('version') == CONTEXT_VERSION

    def is_stale(self) -> bool:
        """Check if context is older than CONTEXT_MAX_AGE."""
        data = self._load()
        if not data:
            return True
        refreshed = data.get('lastRefreshed')
        if not refreshed:
            return True
        try:
            dt = datetime.fromisoformat(refreshed)
            age = (datetime.now(timezone.utc) - dt).total_seconds()
            return age > CONTEXT_MAX_AGE
        except (ValueError, TypeError):
            return True

    def get(self) -> Optional[dict]:
        """Get the cached context data, or None if not populated."""
        return self._load()

    def get_scouts(self) -> list:
        """Get cached scout list."""
        data = self._load()
        if not data:
            return []
        return data.get('scouts', [])

    def get_organizations(self) -> list:
        """Get cached organization list."""
        data = self._load()
        if not data:
            return []
        return data.get('organizations', [])

    def get_user(self) -> Optional[dict]:
        """Get cached user info."""
        data = self._load()
        if not data:
            return None
        return data.get('user')

    def resolve_scout(self, query: str) -> list:
        """Search cached scouts by name (case-insensitive substring).

        Args:
            query: Name to search for

        Returns:
            List of matching scout dicts with full context
        """
        scouts = self.get_scouts()
        query_lower = query.lower()
        matches = []
        for scout in scouts:
            full = (scout.get('fullName') or '').lower()
            first = (scout.get('firstName') or '').lower()
            last = (scout.get('lastName') or '').lower()
            if query_lower in full or query_lower in first or query_lower in last:
                matches.append(scout)
        return matches

    def refresh(self, client) -> dict:
        """Refresh context from live API calls.

        Args:
            client: Authenticated ScoutingClient instance

        Returns:
            The refreshed context data
        """
        token_info = client.auth.get_token_info()
        user_id = token_info.get('uid')
        person_guid = token_info.get('pgu')

        # Build user section
        user = {
            'userId': user_id,
            'personGuid': person_guid,
        }

        if user_id:
            try:
                profile = client.get_person_profile(user_id)
                p = profile.get('profile', {})
                user['memberId'] = p.get('memberId')
                user['firstName'] = p.get('firstName')
                user['lastName'] = p.get('lastName')
                user['fullName'] = p.get('fullName')
                user['email'] = (profile.get('emails', [{}]) or [{}])[0].get('email')
            except Exception:
                pass

        # Build organizations from profile positions
        orgs = {}
        if user_id:
            try:
                profile = client.get_person_profile(user_id)
                for org in profile.get('organizationPositions', []):
                    guid = org.get('organizationGuid')
                    if not guid:
                        continue
                    if guid not in orgs:
                        orgs[guid] = {
                            'orgGuid': guid,
                            'name': org.get('organizationName'),
                            'unitType': org.get('unitType'),
                            'unitNumber': org.get('unitNumber'),
                            'roles': [],
                            'scouts': [],
                        }
                    positions = [pos.get('name') or pos.get('position')
                                 for pos in org.get('positions', [])]
                    for pos in positions:
                        if pos and pos not in orgs[guid]['roles']:
                            orgs[guid]['roles'].append(pos)
            except Exception:
                pass

        # Build scouts list and enrich orgs from my-scouts
        scouts = []
        if user_id:
            try:
                raw_scouts = client.get_my_scouts(user_id)
                seen = {}
                for scout in raw_scouts:
                    pg = scout.get('personGuid')
                    guid = scout.get('orgGuid')

                    if pg not in seen:
                        seen[pg] = {
                            'firstName': scout.get('firstName'),
                            'lastName': scout.get('lastName'),
                            'fullName': f"{scout.get('firstName', '')} {scout.get('lastName', '')}".strip(),
                            'userId': scout.get('userId'),
                            'memberId': scout.get('memberId'),
                            'personGuid': pg,
                            'orgGuid': guid,
                            'unitType': scout.get('unitType'),
                            'unitNumber': scout.get('unitNumber'),
                            'program': scout.get('program'),
                            'organization': scout.get('organizationName'),
                            'positions': [scout.get('position')],
                        }
                    else:
                        pos = scout.get('position')
                        if pos and pos not in seen[pg]['positions']:
                            seen[pg]['positions'].append(pos)

                    # Enrich org with scout info and parent role
                    if guid:
                        if guid not in orgs:
                            unit_type = scout.get('unitType', '')
                            unit_number = scout.get('unitNumber', '')
                            orgs[guid] = {
                                'orgGuid': guid,
                                'name': f"{unit_type} {unit_number}".strip() if unit_type else scout.get('organizationName'),
                                'unitType': unit_type,
                                'unitNumber': unit_number,
                                'program': scout.get('program'),
                                'roles': ['Parent/Guardian'],
                                'scouts': [],
                            }
                        elif 'Parent/Guardian' not in orgs[guid]['roles']:
                            orgs[guid]['roles'].append('Parent/Guardian')

                scouts = list(seen.values())

                # Add scout refs to orgs
                for scout in scouts:
                    guid = scout.get('orgGuid')
                    if guid and guid in orgs:
                        # Avoid duplicate scout entries in org
                        existing_ids = [s.get('userId') for s in orgs[guid]['scouts']]
                        if scout.get('userId') not in existing_ids:
                            orgs[guid]['scouts'].append({
                                'name': scout['fullName'],
                                'userId': scout.get('userId'),
                                'memberId': scout.get('memberId'),
                            })
            except Exception:
                pass

        # Add program info from roles endpoint
        if person_guid:
            try:
                roles = client.get_role_types(person_guid)
                for role in roles:
                    guid = role.get('organizationGuid')
                    if guid and guid in orgs:
                        program = role.get('programType')
                        if program and 'program' not in orgs[guid]:
                            orgs[guid]['program'] = program
            except Exception:
                pass

        data = {
            'user': user,
            'organizations': list(orgs.values()),
            'scouts': scouts,
        }

        self._save(data)
        return data

    def show(self) -> dict:
        """Return context summary for display.

        Returns:
            Dict with context info or error if not populated
        """
        data = self._load()
        if not data:
            return {
                'status': 'not_populated',
                'message': 'No context file found. Run "scouts context refresh" to populate.',
                'path': CONTEXT_FILE,
            }

        scout_count = len(data.get('scouts', []))
        org_count = len(data.get('organizations', []))

        return {
            'status': 'stale' if self.is_stale() else 'current',
            'lastRefreshed': data.get('lastRefreshed'),
            'path': CONTEXT_FILE,
            'user': data.get('user', {}),
            'organizationCount': org_count,
            'organizations': data.get('organizations', []),
            'scoutCount': scout_count,
            'scouts': data.get('scouts', []),
        }
