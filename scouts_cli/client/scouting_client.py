"""HTTP client for the BSA Scouting API."""

import sys
import base64
import json

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import (
    API_BASE_URL,
    AUTH_BASE_URL,
    WEB_BASE_URL,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    BACKOFF_FACTOR,
    RETRY_STATUS_CODES,
)
from .auth import ScoutingAuth
from .errors import (
    ScoutingError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
)


ERROR_MAP = {
    400: ValidationError,
    401: AuthenticationError,
    403: AuthorizationError,
    404: NotFoundError,
    429: RateLimitError,
}


class ScoutingClient:
    """HTTP client for api.scouting.org with JWT bearer auth."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.base_url = API_BASE_URL
        self.auth = ScoutingAuth()
        self.session = self._create_authenticated_session()

    def _create_authenticated_session(self) -> requests.Session:
        """Create a requests session with retry logic and auth headers."""
        session = requests.Session()

        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=RETRY_STATUS_CODES,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)

        token = self.auth.get_token()
        session.headers.update({
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}',
            'x-esb-url': base64.b64encode(
                f'{WEB_BASE_URL}/roster'.encode()
            ).decode(),
        })

        return session

    def _make_request(self, method: str, path: str, base_url: str = None, **kwargs) -> dict:
        """Make an HTTP request and handle response/errors.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: URL path (appended to base_url)
            base_url: Override base URL (default: API_BASE_URL)
            **kwargs: Passed to requests

        Returns:
            Parsed JSON response
        """
        url = f"{base_url or self.base_url}{path}"

        if 'timeout' not in kwargs:
            kwargs['timeout'] = REQUEST_TIMEOUT

        if self.verbose:
            print(f">> {method} {url}", file=sys.stderr)
            if 'json' in kwargs:
                print(f"   Body: {json.dumps(kwargs['json'])[:200]}", file=sys.stderr)

        response = self.session.request(method, url, **kwargs)

        if self.verbose:
            print(f"<< {response.status_code} {response.reason}", file=sys.stderr)

        return self._handle_response(response)

    def _handle_response(self, response: requests.Response) -> dict:
        """Parse response, raising appropriate errors for non-2xx."""
        if response.ok:
            if not response.content:
                return {}
            try:
                return response.json()
            except ValueError:
                return {"raw": response.text}

        # Map HTTP status to error class
        error_class = ERROR_MAP.get(response.status_code, ScoutingError)

        try:
            body = response.json()
            message = body.get('message', body.get('error', response.text[:200]))
        except ValueError:
            message = response.text[:200] if response.text else response.reason

        raise error_class(message=f"{response.status_code}: {message}")

    # ── Read Endpoints ──────────────────────────────────────────────

    def get_ranks(self, program_id: int = None) -> list:
        """Get all ranks, optionally filtered by program."""
        params = {}
        if program_id:
            params['programId'] = program_id
        return self._make_request('GET', '/advancements/ranks', params=params)

    def get_adventure_requirements(self, adventure_id: int, version_id: int) -> dict:
        """Get requirements for a specific adventure and version."""
        return self._make_request(
            'GET',
            f'/advancements/adventures/{adventure_id}/requirements',
            params={'versionId': version_id}
        )

    def get_user_requirements(self, org_guid: str, adventure_id: int,
                              member_ids: list) -> list:
        """Get scouts' current status for an adventure.

        Args:
            org_guid: Organization GUID
            adventure_id: Adventure ID
            member_ids: List of member ID integers

        Returns:
            List of scout advancement records
        """
        member_str = ','.join(str(m) for m in member_ids)
        return self._make_request(
            'GET',
            f'/advancements/v2/organization/{org_guid}/adventures/{adventure_id}/userRequirements',
            params={'memberId': member_str}
        )

    def get_advancement_dashboard(self, org_guid: str) -> dict:
        """Get organization advancement dashboard stats."""
        return self._make_request(
            'GET',
            f'/organizations/v2/{org_guid}/advancementDashboard'
        )

    def validate_session(self, person_guid: str) -> dict:
        """Validate current session and refresh token data."""
        return self._make_request(
            'GET',
            f'/api/users/self_{person_guid}/sessions/current',
            base_url=AUTH_BASE_URL
        )

    def get_person_profile(self, user_id: int) -> dict:
        """Get a person's full profile by userId.

        Args:
            user_id: User ID (numeric)

        Returns:
            Dict with: profile, currentProgramsAndRanks, currentCouncils,
            advancementInfo, organizationPositions, addresses, emails, etc.
        """
        return self._make_request(
            'GET',
            f'/persons/v2/{user_id}/personprofile'
        )

    def get_my_scouts(self, user_id: int) -> list:
        """Get scouts associated with a parent/guardian.

        Args:
            user_id: Parent's user ID

        Returns:
            List of scout records with: userId, memberId, firstName,
            lastName, relationship, orgGuid, unitType, program, position.
        """
        return self._make_request(
            'GET',
            f'/persons/{user_id}/myScout'
        )

    def get_roster(self, org_guid: str) -> dict:
        """Get organization youth roster with names and IDs.

        Args:
            org_guid: Organization GUID

        Returns:
            Dict with org info and 'users' array of youth members.
            Each user has: userId, memberId, firstName, lastName,
            personFullName, positions (den info), rank info, etc.
        """
        return self._make_request(
            'GET',
            f'/organizations/v2/units/{org_guid}/youths'
        )

    def get_adults(self, org_guid: str) -> dict:
        """Get organization adult leader roster.

        Args:
            org_guid: Organization GUID

        Returns:
            Dict with org info and 'users' array of adult members.
            Same structure as youth roster but with adult leaders.
        """
        return self._make_request(
            'GET',
            f'/organizations/v2/units/{org_guid}/adults'
        )

    def get_parents(self, org_guid: str) -> list:
        """Get parent-youth relationships for an organization.

        Args:
            org_guid: Organization GUID

        Returns:
            List of dicts with youthUserId, parentUserId, and
            parentInformation (name, contact, memberId, etc.)
        """
        return self._make_request(
            'GET',
            f'/organizations/v2/units/{org_guid}/parents'
        )

    def get_org_profile(self, org_guid: str) -> dict:
        """Get organization profile details.

        Args:
            org_guid: Organization GUID

        Returns:
            Dict with: name, number, program, type, charter info,
            district, council, territory, address, meeting info,
            key3 leaders, advancementEligibility, etc.
        """
        return self._make_request(
            'GET',
            f'/organizations/v2/{org_guid}/profile'
        )

    def get_sub_units(self, org_guid: str) -> list:
        """Get sub-units (dens/patrols) for an organization.

        Args:
            org_guid: Organization GUID

        Returns:
            List of dicts with: subUnitId, subUnitName (den number),
            denTypeId, denType (tigers/wolves/bears/etc.), unitId.
        """
        return self._make_request(
            'GET',
            f'/organizations/v2/units/{org_guid}/subUnits',
            params={'swCache': 'true'}
        )

    def get_activities_dashboard(self, org_guid: str) -> dict:
        """Get unit activities dashboard (campouts, service, hikes).

        Args:
            org_guid: Organization GUID

        Returns:
            Dict with CampOuts, ServiceProjects, and Hikes sections,
            each with counts and attendance numbers.
        """
        return self._make_request(
            'GET',
            f'/organizations/v2/{org_guid}/unitActivitiesDashboard',
            params={'completedActivities': 'true'}
        )

    def get_role_types(self, person_guid: str) -> list:
        """Get a person's role types and permissions.

        Args:
            person_guid: Person GUID (from JWT token 'pgu' claim)

        Returns:
            List of role dicts with: role, organizationName, roleTypes
            (list of permission strings like 'Internet Advancement').
        """
        return self._make_request(
            'GET',
            f'/persons/{person_guid}/roleTypes',
            params={
                'includeParentRoles': 'true',
                'includeScoutbookRoles': 'true',
            }
        )

    def get_ypt_training(self, person_guid: str) -> dict:
        """Get Youth Protection Training status for a person.

        Args:
            person_guid: Person GUID

        Returns:
            Dict with: firstName, lastName, yptStatus (ACTIVE/EXPIRED),
            yptCompletionDate, yptExpireDate, enrollmentId.
        """
        return self._make_request(
            'GET',
            f'/persons/v2/{person_guid}/trainings/ypt'
        )

    def get_membership_registrations(self, person_guid: str,
                                     org_guid: str = None,
                                     statuses: list = None) -> list:
        """Get membership registration history for a person.

        Args:
            person_guid: Person GUID
            org_guid: Optional organization GUID to filter by
            statuses: Optional list of statuses (e.g. ['current'])

        Returns:
            List of registration dicts with: position, effectiveDate,
            expireDate, organizationName, councilName, etc.
        """
        body = {}
        if statuses:
            body['status'] = statuses
        if org_guid:
            body['organizationGuid'] = org_guid
        return self._make_request(
            'POST',
            f'/persons/v2/{person_guid}/membershipRegistrations',
            json=body
        )

    def get_adventures(self, rank_id: int = None) -> dict:
        """Get all adventures, optionally filtered by rank.

        Args:
            rank_id: Optional rank ID to filter adventures

        Returns:
            Dict with 'adventures' list, each containing: id, name,
            rankId, rank, required, versionId, version, etc.
        """
        params = {}
        if rank_id:
            params['rankId'] = rank_id
        return self._make_request('GET', '/advancements/adventures', params=params)

    def get_merit_badges(self) -> dict:
        """Get all merit badges.

        Returns:
            Dict with 'meritBadges' list, each containing: id, name,
            isEagleRequired, program, versions, etc.
        """
        return self._make_request('GET', '/advancements/meritBadges')

    def get_awards(self) -> dict:
        """Get all awards.

        Returns:
            Dict with 'awards' list, each containing: id, name,
            category, rankId, rank, program, versions, etc.
        """
        return self._make_request('GET', '/advancements/awards')

    def get_ss_electives(self) -> dict:
        """Get all Sea Scout electives.

        Returns:
            Dict with elective records.
        """
        return self._make_request('GET', '/advancements/ssElectives')

    # ── Youth Advancement Endpoints ────────────────────────────────

    def get_youth_activity_summary(self, user_id: int) -> dict:
        """Get a youth's activity summary (camping, hiking, service logs).

        Args:
            user_id: Youth's user ID

        Returns:
            Dict with campingLogs, hikingLogs, serviceLogs, longCruiseLogs.
        """
        return self._make_request(
            'GET',
            f'/advancements/v2/{user_id}/userActivitySummary'
        )

    def get_youth_merit_badges(self, user_id: int) -> list:
        """Get a youth's merit badge progress.

        Args:
            user_id: Youth's user ID

        Returns:
            List of merit badge records with completion status.
        """
        return self._make_request(
            'GET',
            f'/advancements/v2/youth/{user_id}/meritBadges'
        )

    def get_youth_ranks(self, user_id: int) -> dict:
        """Get a youth's rank progression.

        Args:
            user_id: Youth's user ID

        Returns:
            Dict with program list, each containing ranks with
            completion dates, leader approvals, etc.
        """
        return self._make_request(
            'GET',
            f'/advancements/v2/youth/{user_id}/ranks'
        )

    def get_youth_awards(self, user_id: int) -> list:
        """Get a youth's award progress.

        Args:
            user_id: Youth's user ID

        Returns:
            List of award records with completion status.
        """
        return self._make_request(
            'GET',
            f'/advancements/v2/youth/{user_id}/awards'
        )

    def get_youth_leadership_history(self, user_id: int) -> list:
        """Get a youth's leadership position history.

        Args:
            user_id: Youth's user ID

        Returns:
            List of leadership position records with dates, units, patrols.
        """
        return self._make_request(
            'GET',
            f'/advancements/youth/{user_id}/leadershipPositionHistory',
            params={'summary': 'true'}
        )

    # ── Messaging Endpoints ────────────────────────────────────────

    def get_recipients(self, org_guid: str) -> dict:
        """Get available message recipients for an organization.

        Args:
            org_guid: Organization GUID

        Returns:
            Dict with 'leaders', 'youths', and 'parents' lists.
            Each entry has: firstName, lastName, personGuid, memberId,
            hasEmail, noEmails. Youths also have relationships and
            hasParentGuardianEmail. Parents also have youths list.
        """
        return self._make_request(
            'GET',
            f'/organizations/v2/{org_guid}/recipients'
        )

    def send_email(self, org_guid: str, to_member_ids: list,
                   bcc_member_ids: list, subject: str, body: str) -> dict:
        """Send a message to organization members.

        Args:
            org_guid: Organization GUID
            to_member_ids: List of member IDs for the To field
            bcc_member_ids: List of member IDs for BCC (default in web UI)
            subject: Email subject line
            body: HTML body content

        Returns:
            Dict with 'message' key (e.g. 'Email sent.')
        """
        payload = {
            'to': {'memberId': to_member_ids},
            'bcc': {'memberId': bcc_member_ids},
            'subject': subject,
            'body': body,
        }
        return self._make_request(
            'POST',
            f'/advancements/v2/{org_guid}/email',
            json=payload
        )

    # ── Write Endpoints ─────────────────────────────────────────────

    def mark_requirements_complete(self, adventure_id: int, entries: list) -> list:
        """Mark advancement requirements as complete for one or more scouts.

        Args:
            adventure_id: Adventure ID
            entries: List of dicts, each containing:
                - organizationGuid (str): Unit GUID
                - userId (int): Scout's user ID
                - versionId (int): Adventure version ID
                - requirements (list): Requirements to mark complete, each with:
                    - id (int): Requirement ID
                    - dateCompleted (str): YYYY-MM-DD
                    - markedCompletedDate (str): YYYY-MM-DD
                    - started (bool): True
                    - completed (bool): True
                    - comments (dict, optional): {subject, body}

        Returns:
            List of result dicts with status per scout/requirement
        """
        # Set content-type for POST
        headers = {'Content-Type': 'application/json'}

        return self._make_request(
            'POST',
            f'/advancements/v2/youth/adventures/{adventure_id}/requirements',
            json=entries,
            headers=headers
        )
