"""Profile commands — view user profile and associated scouts."""


class ProfileCommands:
    """Commands for viewing profile information."""

    def __init__(self, client):
        self.client = client

    def get_my_profile(self) -> dict:
        """Get the current authenticated user's profile.

        Uses the userId from the cached JWT token.

        Returns:
            Simplified profile dict
        """
        token_info = self.client.auth.get_token_info()
        user_id = token_info.get('uid')
        if not user_id:
            return {"error": "No userId found in token. Re-authenticate with 'scouts auth login'."}

        raw = self.client.get_person_profile(user_id)
        profile = raw.get('profile', {})
        positions = raw.get('organizationPositions', [])
        councils = raw.get('currentCouncils', [])

        # Extract org positions
        orgs = []
        for org in positions:
            org_positions = [p.get('name') or p.get('position') for p in org.get('positions', [])]
            orgs.append({
                'organization': org.get('organizationName'),
                'unitType': org.get('unitType'),
                'unitNumber': org.get('unitNumber'),
                'orgGuid': org.get('organizationGuid'),
                'positions': org_positions,
            })

        return {
            'userId': profile.get('userId') or user_id,
            'memberId': profile.get('memberId'),
            'personGuid': profile.get('personGuid'),
            'firstName': profile.get('firstName'),
            'lastName': profile.get('lastName'),
            'fullName': profile.get('fullName'),
            'email': (raw.get('emails', [{}]) or [{}])[0].get('email'),
            'council': councils[0].get('councilName') if councils else None,
            'organizations': orgs,
        }

    def get_my_scouts(self) -> dict:
        """Get scouts associated with the current user (parent/guardian).

        Returns:
            Dict with 'scouts' list and 'count'
        """
        token_info = self.client.auth.get_token_info()
        user_id = token_info.get('uid')
        if not user_id:
            return {"error": "No userId found in token. Re-authenticate with 'scouts auth login'."}

        raw = self.client.get_my_scouts(user_id)

        # Deduplicate by personGuid (same scout can appear multiple times
        # with different positions)
        seen = {}
        for scout in raw:
            pg = scout.get('personGuid')
            if pg not in seen:
                seen[pg] = {
                    'userId': scout.get('userId'),
                    'memberId': scout.get('memberId'),
                    'firstName': scout.get('firstName'),
                    'lastName': scout.get('lastName'),
                    'relationship': scout.get('relationship'),
                    'orgGuid': scout.get('orgGuid'),
                    'organization': scout.get('organizationName'),
                    'unitType': scout.get('unitType'),
                    'unitNumber': scout.get('unitNumber'),
                    'program': scout.get('program'),
                    'positions': [scout.get('position')],
                }
            else:
                pos = scout.get('position')
                if pos and pos not in seen[pg]['positions']:
                    seen[pg]['positions'].append(pos)

        scouts = list(seen.values())
        return {
            'scouts': scouts,
            'count': len(scouts),
        }

    def get_scout_profile(self, user_id: int) -> dict:
        """Get a specific scout's profile by userId.

        Args:
            user_id: Scout's user ID

        Returns:
            Simplified profile dict with advancement info
        """
        raw = self.client.get_person_profile(user_id)
        profile = raw.get('profile', {})
        advancement = raw.get('advancementInfo', {})
        programs = raw.get('currentProgramsAndRanks', [])
        positions = raw.get('organizationPositions', [])

        # Extract org positions
        orgs = []
        for org in positions:
            org_positions = [p.get('name') or p.get('position') for p in org.get('positions', [])]
            orgs.append({
                'organization': org.get('organizationName'),
                'unitType': org.get('unitType'),
                'unitNumber': org.get('unitNumber'),
                'orgGuid': org.get('organizationGuid'),
                'positions': org_positions,
            })

        return {
            'userId': profile.get('userId') or user_id,
            'memberId': profile.get('memberId'),
            'personGuid': profile.get('personGuid'),
            'firstName': profile.get('firstName'),
            'lastName': profile.get('lastName'),
            'fullName': profile.get('fullName'),
            'dateOfBirth': profile.get('dateOfBirth'),
            'gender': profile.get('gender'),
            'programs': programs,
            'advancement': advancement,
            'organizations': orgs,
        }

    def get_scout_merit_badges(self, user_id: int) -> dict:
        """Get a specific scout's merit badge progress.

        Args:
            user_id: Scout's user ID

        Returns:
            Dict with 'meritBadges' list (earned/in-progress) and counts
        """
        raw = self.client.get_youth_merit_badges(user_id)

        badges = []
        for mb in raw:
            badges.append({
                'id': mb.get('id'),
                'name': mb.get('name'),
                'isEagleRequired': mb.get('isEagleRequired'),
                'percentCompleted': mb.get('percentCompleted'),
                'dateStarted': mb.get('dateStarted'),
                'dateCompleted': mb.get('dateCompleted'),
                'version': mb.get('version'),
                'versionId': mb.get('versionId'),
            })

        earned = [b for b in badges if b.get('percentCompleted') == 1]
        in_progress = [b for b in badges if 0 < (b.get('percentCompleted') or 0) < 1]

        return {
            'meritBadges': badges,
            'total': len(badges),
            'earned': len(earned),
            'inProgress': len(in_progress),
        }

    def get_scout_ranks(self, user_id: int) -> dict:
        """Get a specific scout's rank progression.

        Args:
            user_id: Scout's user ID

        Returns:
            Dict with program rank progressions
        """
        raw = self.client.get_youth_ranks(user_id)

        programs = []
        for prog in raw.get('program', []):
            ranks = []
            for rank in prog.get('ranks', []):
                ranks.append({
                    'id': rank.get('id'),
                    'name': rank.get('name'),
                    'level': rank.get('level'),
                    'versionId': rank.get('versionId'),
                    'version': rank.get('version'),
                    'dateEarned': rank.get('dateEarned'),
                    'awarded': rank.get('awarded'),
                    'percentCompleted': rank.get('percentCompleted'),
                })
            programs.append({
                'program': prog.get('program'),
                'programId': prog.get('programId'),
                'totalRanks': prog.get('totalNumberOfRanks'),
                'ranks': ranks,
            })

        return {
            'programs': programs,
        }

    def get_scout_leadership(self, user_id: int) -> dict:
        """Get a specific scout's leadership position history.

        Args:
            user_id: Scout's user ID

        Returns:
            Dict with 'positions' list and 'count'
        """
        raw = self.client.get_youth_leadership_history(user_id)

        positions = []
        for pos in raw:
            positions.append({
                'position': pos.get('position'),
                'startDate': pos.get('startDate'),
                'endDate': pos.get('endDate'),
                'unit': pos.get('unitLong'),
                'patrol': pos.get('patrol'),
                'den': pos.get('den'),
                'daysInPosition': pos.get('numberOfDaysInPosition'),
                'approved': pos.get('approved'),
            })

        return {
            'positions': positions,
            'count': len(positions),
        }

    def get_scout_activity_summary(self, user_id: int) -> dict:
        """Get a specific scout's activity summary (camping, hiking, service).

        Args:
            user_id: Scout's user ID

        Returns:
            Activity summary dict
        """
        raw = self.client.get_youth_activity_summary(user_id)

        camping = raw.get('campingLogs', {})
        hiking = raw.get('hikingLogs', {})
        service = raw.get('serviceLogs', {})

        return {
            'fullName': raw.get('fullName'),
            'memberId': raw.get('memberId'),
            'camping': {
                'totalDays': camping.get('totalNumberOfDays', 0),
                'totalNights': camping.get('totalNumberOfNights', 0),
                'percentToGoal': camping.get('percentCompleteTowardGoal', 0),
            },
            'hiking': {
                'totalMiles': hiking.get('totalNumberOfMiles', 0),
                'percentToGoal': hiking.get('percentCompleteTowardGoal', 0),
            },
            'service': {
                'totalHours': service.get('totalNumberOfHours', 0),
                'percentToGoal': service.get('percentCompleteTowardGoal', 0),
            },
        }

    def _get_person_guid(self) -> str | None:
        """Get personGuid from cached JWT token."""
        token_info = self.client.auth.get_token_info()
        return token_info.get('pgu')

    def get_my_roles(self) -> dict:
        """Get the current user's roles and permissions.

        Returns:
            Dict with 'roles' list and 'count'
        """
        person_guid = self._get_person_guid()
        if not person_guid:
            return {"error": "No personGuid found in token. Re-authenticate with 'scouts auth login'."}

        raw = self.client.get_role_types(person_guid)

        roles = []
        for role in raw:
            role_name = role.get('role')
            if not role_name:
                # Parent role entries have empty role name
                role_types = [rt.get('roleType') for rt in role.get('roleTypes', [])]
                if role_types:
                    role_name = role_types[0]
            roles.append({
                'role': role_name,
                'organization': role.get('organizationName'),
                'organizationNumber': role.get('organizationNumber'),
                'organizationGuid': role.get('organizationGuid'),
                'program': role.get('programType'),
                'effectiveDate': role.get('effectiveDate') or None,
                'expireDate': role.get('expireDate') or None,
                'status': role.get('status'),
                'permissions': [rt.get('roleType') for rt in role.get('roleTypes', [])],
            })

        return {
            'roles': roles,
            'count': len(roles),
        }

    def get_my_training(self) -> dict:
        """Get the current user's YPT training status.

        Returns:
            Training status dict
        """
        person_guid = self._get_person_guid()
        if not person_guid:
            return {"error": "No personGuid found in token. Re-authenticate with 'scouts auth login'."}

        raw = self.client.get_ypt_training(person_guid)

        return {
            'name': raw.get('personFullName'),
            'yptStatus': raw.get('yptStatus'),
            'completionDate': raw.get('yptCompletionDate'),
            'expireDate': raw.get('yptExpireDate'),
        }

    def get_my_registrations(self, org_guid: str = None) -> dict:
        """Get the current user's membership registrations.

        Args:
            org_guid: Optional organization GUID to filter by

        Returns:
            Dict with 'registrations' list and 'count'
        """
        person_guid = self._get_person_guid()
        if not person_guid:
            return {"error": "No personGuid found in token. Re-authenticate with 'scouts auth login'."}

        raw = self.client.get_membership_registrations(
            person_guid,
            org_guid=org_guid,
            statuses=['current'],
        )

        registrations = []
        for reg in raw:
            registrations.append({
                'position': reg.get('position'),
                'positionCode': reg.get('positionCode'),
                'organization': reg.get('organizationName'),
                'organizationNumber': reg.get('organizationNumber'),
                'organizationGuid': reg.get('organizationGuid'),
                'unitType': reg.get('unitType'),
                'council': reg.get('councilName'),
                'district': reg.get('districtName'),
                'effectiveDate': reg.get('effectiveDate'),
                'expireDate': reg.get('expireDate'),
                'isPaid': reg.get('isPaid'),
                'renewalStatus': reg.get('renewalStatus'),
                'registrantStatus': reg.get('registrantStatusName'),
            })

        return {
            'registrations': registrations,
            'count': len(registrations),
        }
