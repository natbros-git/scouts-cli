"""Lookup commands for reference data (ranks, adventures, requirements)."""


class LookupCommands:
    """Commands for looking up reference data."""

    def __init__(self, client):
        self.client = client

    def list_ranks(self, program_id: int = None) -> list:
        """List all available ranks."""
        return self.client.get_ranks(program_id=program_id)

    def get_adventure_requirements(self, adventure_id: int, version_id: int) -> dict:
        """Get requirements for a specific adventure."""
        return self.client.get_adventure_requirements(adventure_id, version_id)

    def get_dashboard(self, org_guid: str) -> dict:
        """Get advancement dashboard for an organization."""
        return self.client.get_advancement_dashboard(org_guid)

    def list_adventures(self, rank_id: int = None) -> dict:
        """List all adventures, optionally filtered by rank.

        The API returns all adventures regardless of rankId param,
        so we filter client-side when rank_id is specified.

        Args:
            rank_id: Optional rank ID to filter by

        Returns:
            Dict with 'adventures' list and 'count'
        """
        raw = self.client.get_adventures(rank_id=rank_id)
        adventures = raw.get('adventures', [])

        if rank_id:
            adventures = [a for a in adventures
                          if int(a.get('rankId') or 0) == rank_id]

        return {
            'adventures': adventures,
            'count': len(adventures),
        }

    def list_merit_badges(self) -> dict:
        """List all merit badges.

        Returns:
            Dict with 'meritBadges' list and 'count'
        """
        raw = self.client.get_merit_badges()
        badges = raw.get('meritBadges', [])
        return {
            'meritBadges': badges,
            'count': len(badges),
        }

    def list_awards(self) -> dict:
        """List all awards.

        Returns:
            Dict with 'awards' list and 'count'
        """
        raw = self.client.get_awards()
        awards = raw.get('awards', [])
        return {
            'awards': awards,
            'count': len(awards),
        }

    def list_ss_electives(self) -> dict:
        """List all Sea Scout electives.

        Returns:
            Dict with electives data
        """
        return self.client.get_ss_electives()
