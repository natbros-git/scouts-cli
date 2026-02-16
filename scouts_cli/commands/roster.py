"""Roster commands — list and search scouts by name."""

import os
import json
import time

from ..config import TOKEN_DIR
from ..context import ScoutContext


ROSTER_CACHE_MAX_AGE = 86400  # 24 hours


def _simplify_user(user: dict, is_adult: bool = False) -> dict:
    """Extract the most useful fields from a raw roster user record.

    The API returns ~30 fields per user including address, phone, etc.
    We distill to what agents and humans need for advancement workflows.
    """
    # Current rank (highest approved or awarded)
    rank = None
    rank_info = user.get('lastRankApproved') or {}
    if rank_info and rank_info.get('rank'):
        rank = rank_info['rank']
    elif user.get('highestRanksAwarded'):
        rank = user['highestRanksAwarded'][0].get('rank')

    # Position info
    den_number = None
    den_type = None
    positions = []
    for pos in user.get('positions', []):
        positions.append(pos.get('position'))
        if pos.get('denNumber') and not den_number:
            den_number = pos['denNumber']
            den_type = pos.get('denType')

    result = {
        'userId': user.get('userId'),
        'memberId': user.get('memberId'),
        'firstName': user.get('firstName'),
        'lastName': user.get('lastName'),
        'fullName': user.get('personFullName'),
        'rank': rank,
        'age': user.get('age'),
    }

    if is_adult:
        result['positions'] = positions
        result['email'] = user.get('email')
        if den_number:
            result['denNumber'] = den_number
            result['denType'] = den_type
    else:
        result['denNumber'] = den_number
        result['denType'] = den_type
        result['position'] = positions[0] if positions else None

    return result


class RosterCommands:
    """Commands for listing and searching the organization roster."""

    def __init__(self, client):
        self.client = client

    def _get_cache_path(self, org_guid: str) -> str:
        return os.path.join(TOKEN_DIR, f'roster-{org_guid}.json')

    def _read_cache(self, org_guid: str) -> list | None:
        """Return cached roster if fresh enough, else None."""
        path = self._get_cache_path(org_guid)
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                cache = json.load(f)
            if time.time() - cache.get('fetched_at', 0) < ROSTER_CACHE_MAX_AGE:
                return cache['members']
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _write_cache(self, org_guid: str, members: list):
        """Write roster to local cache."""
        os.makedirs(TOKEN_DIR, exist_ok=True)
        path = self._get_cache_path(org_guid)
        with open(path, 'w') as f:
            json.dump({
                'fetched_at': time.time(),
                'org_guid': org_guid,
                'members': members,
            }, f)

    def _fetch_roster(self, org_guid: str, refresh: bool = False) -> list:
        """Fetch roster, using cache unless refresh is requested."""
        if not refresh:
            cached = self._read_cache(org_guid)
            if cached is not None:
                return cached

        raw = self.client.get_roster(org_guid)
        users = raw.get('users', [])
        members = [_simplify_user(u) for u in users]
        self._write_cache(org_guid, members)
        return members

    def list_roster(self, org_guid: str, refresh: bool = False) -> dict:
        """List all youth members in the organization.

        Args:
            org_guid: Organization GUID
            refresh: Force fresh API call (ignore cache)

        Returns:
            Dict with 'members' list and 'count'
        """
        members = self._fetch_roster(org_guid, refresh=refresh)
        return {
            'members': members,
            'count': len(members),
        }

    def search_scouts(self, org_guid: str, query: str,
                      refresh: bool = False) -> dict:
        """Search roster by name (case-insensitive substring match).

        Args:
            org_guid: Organization GUID
            query: Search string (matched against first, last, or full name)
            refresh: Force fresh API call (ignore cache)

        Returns:
            Dict with 'matches' list, 'query', and 'count'
        """
        members = self._fetch_roster(org_guid, refresh=refresh)
        query_lower = query.lower()

        matches = []
        for m in members:
            full = (m.get('fullName') or '').lower()
            first = (m.get('firstName') or '').lower()
            last = (m.get('lastName') or '').lower()
            if query_lower in full or query_lower in first or query_lower in last:
                matches.append(m)

        return {
            'matches': matches,
            'query': query,
            'count': len(matches),
        }

    def resolve(self, query: str, refresh: bool = False) -> dict:
        """Resolve a scout name to their full context across ALL organizations.

        Uses the local context cache for instant lookups. Falls back to
        the API if the context isn't populated yet.

        This is the primary command for agents handling natural-language
        requests that reference scouts by name. It searches across all
        organizations the current user has access to and returns the
        userId, memberId, orgGuid, unit info, and program for each match.

        Args:
            query: Scout name to search for (case-insensitive substring)
            refresh: Force API call instead of using cache

        Returns:
            Dict with 'matches' list (each with full context), 'query', 'count'
        """
        ctx = ScoutContext()

        # Use cached context if available
        if not refresh and ctx.exists():
            matches = ctx.resolve_scout(query)
            return {
                'matches': matches,
                'query': query,
                'count': len(matches),
                'source': 'cache',
            }

        # Fall back to API
        token_info = self.client.auth.get_token_info()
        user_id = token_info.get('uid')
        if not user_id:
            return {"error": "No userId found in token."}

        raw_scouts = self.client.get_my_scouts(user_id)

        seen = {}
        for scout in raw_scouts:
            pg = scout.get('personGuid')
            if pg not in seen:
                seen[pg] = {
                    'userId': scout.get('userId'),
                    'memberId': scout.get('memberId'),
                    'firstName': scout.get('firstName'),
                    'lastName': scout.get('lastName'),
                    'fullName': f"{scout.get('firstName', '')} {scout.get('lastName', '')}".strip(),
                    'orgGuid': scout.get('orgGuid'),
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

        query_lower = query.lower()
        matches = []
        for entry in seen.values():
            full = entry['fullName'].lower()
            first = (entry.get('firstName') or '').lower()
            last = (entry.get('lastName') or '').lower()
            if query_lower in full or query_lower in first or query_lower in last:
                matches.append(entry)

        return {
            'matches': matches,
            'query': query,
            'count': len(matches),
            'source': 'api',
        }

    def list_adults(self, org_guid: str) -> dict:
        """List all adult leaders in the organization.

        Args:
            org_guid: Organization GUID

        Returns:
            Dict with 'adults' list and 'count'
        """
        raw = self.client.get_adults(org_guid)
        users = raw.get('users', [])
        adults = [_simplify_user(u, is_adult=True) for u in users]
        return {
            'adults': adults,
            'count': len(adults),
        }

    def list_parents(self, org_guid: str) -> dict:
        """List parent-youth relationships in the organization.

        Args:
            org_guid: Organization GUID

        Returns:
            Dict with 'relationships' list and 'count'
        """
        raw = self.client.get_parents(org_guid)

        relationships = []
        for entry in raw:
            parent = entry.get('parentInformation', {})
            relationships.append({
                'youthUserId': entry.get('youthUserId'),
                'parentUserId': entry.get('parentUserId'),
                'parentName': parent.get('personFullName'),
                'parentFirstName': parent.get('firstName'),
                'parentLastName': parent.get('lastName'),
                'parentEmail': parent.get('email'),
                'parentMemberId': parent.get('memberId'),
            })

        return {
            'relationships': relationships,
            'count': len(relationships),
        }
