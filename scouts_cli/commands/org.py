"""Organization commands — org profile, dens, activities, list."""

from ..context import ScoutContext


class OrgCommands:
    """Commands for organization-level information."""

    def __init__(self, client):
        self.client = client

    def list_orgs(self, refresh: bool = False) -> dict:
        """List all organizations the current user has access to.

        Uses the local context cache for instant results. Falls back to
        the API if the context isn't populated yet.

        Args:
            refresh: Force API call instead of using cache

        Returns:
            Dict with 'organizations' list and 'count'
        """
        ctx = ScoutContext()

        # Use cached context if available
        if not refresh and ctx.exists():
            orgs = ctx.get_organizations()
            return {
                'organizations': orgs,
                'count': len(orgs),
                'source': 'cache',
            }

        # Fall back to API (and refresh context)
        data = ctx.refresh(self.client)
        orgs = data.get('organizations', [])
        return {
            'organizations': orgs,
            'count': len(orgs),
            'source': 'api',
        }

    def get_org_profile(self, org_guid: str) -> dict:
        """Get organization profile details.

        Args:
            org_guid: Organization GUID

        Returns:
            Simplified org profile dict
        """
        raw = self.client.get_org_profile(org_guid)

        charter = raw.get('charter') or {}
        address = raw.get('primaryAddress') or {}
        meeting = raw.get('unitMeetingInformation') or {}
        eligibility = raw.get('advancementEligibility') or {}

        # Key 3 leaders
        key3 = []
        for leader in raw.get('key3', []):
            key3.append({
                'position': leader.get('position'),
                'name': leader.get('personFullName'),
            })

        return {
            'organizationGuid': raw.get('organizationGuid'),
            'name': raw.get('name'),
            'fullName': raw.get('organizationFullName'),
            'number': raw.get('number'),
            'type': raw.get('type'),
            'program': raw.get('program'),
            'charter': {
                'organization': charter.get('communityOrganizationName'),
                'effectiveDate': charter.get('effectiveDate'),
                'expiryDate': charter.get('expiryDate'),
                'isActive': charter.get('isActive'),
            },
            'district': raw.get('districtName'),
            'council': raw.get('councilName'),
            'territory': raw.get('territoryName'),
            'address': {
                'line1': address.get('addressLine1'),
                'line2': address.get('addressLine2'),
                'city': address.get('city'),
                'state': address.get('state'),
                'zip': address.get('zip5'),
            },
            'meetingLocation': meeting.get('addressLine1'),
            'meetingAddress': meeting.get('addressLine2'),
            'meetingCity': meeting.get('city'),
            'meetingState': meeting.get('stateShort'),
            'key3Leaders': key3,
            'executiveOfficer': (raw.get('executiveOfficer') or {}).get('personFullName'),
            'advancementEligibility': eligibility,
            'webContact': [
                {'type': c.get('type'), 'contact': c.get('contact')}
                for c in raw.get('webContact', []) if c.get('contact')
            ],
        }

    def get_dens(self, org_guid: str) -> dict:
        """Get list of dens/sub-units for an organization.

        Args:
            org_guid: Organization GUID

        Returns:
            Dict with 'dens' list and 'count'
        """
        raw = self.client.get_sub_units(org_guid)

        dens = []
        for den in raw:
            dens.append({
                'subUnitId': den.get('subUnitId'),
                'denNumber': den.get('subUnitName'),
                'denType': den.get('denType'),
                'dateCreated': den.get('dateCreated'),
            })

        # Sort by den number
        dens.sort(key=lambda d: d.get('denNumber', ''))

        return {
            'dens': dens,
            'count': len(dens),
        }

    def get_activities(self, org_guid: str) -> dict:
        """Get unit activities dashboard (campouts, service projects, hikes).

        Args:
            org_guid: Organization GUID

        Returns:
            Activities summary dict
        """
        raw = self.client.get_activities_dashboard(org_guid)

        campouts = raw.get('CampOuts', {})
        service = raw.get('ServiceProjects', {})
        hikes = raw.get('Hikes', {})

        return {
            'campouts': {
                'count': campouts.get('Campouts', 0),
                'scoutsParticipating': campouts.get('CampoutsScoutParticipating', 0),
                'totalAttendance': campouts.get('CampoutsTotalAttendance', 0),
                'nightsCamped': campouts.get('NightsCamped', 0),
                'daysCamped': campouts.get('DaysCamped', 0),
            },
            'serviceProjects': {
                'count': service.get('ServiceProjects', 0),
                'scoutsParticipating': service.get('ServiceProjectsScoutParticipating', 0),
                'totalAttendance': service.get('ServiceProjectsTotalAttendance', 0),
                'serviceHours': service.get('ServiceHours', 0),
                'conservationHours': service.get('ConservationHours', 0),
            },
            'hikes': {
                'count': hikes.get('Hikes', 0),
                'scoutsParticipating': hikes.get('HikesScoutParticipating', 0),
                'totalAttendance': hikes.get('HikesTotalAttendance', 0),
            },
        }
