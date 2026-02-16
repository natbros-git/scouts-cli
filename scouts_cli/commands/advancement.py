"""Advancement commands for bulk entry and status."""

import sys
from datetime import date


class AdvancementCommands:
    """Commands for managing scout advancement."""

    def __init__(self, client):
        self.client = client

    def get_user_requirements(self, org_guid: str, adventure_id: int,
                              member_ids: list) -> list:
        """Get current advancement status for scouts on an adventure."""
        return self.client.get_user_requirements(org_guid, adventure_id, member_ids)

    def bulk_entry(self, adventure_id: int, org_guid: str, version_id: int,
                   user_ids: list, requirement_ids: list,
                   completion_date: str = None, note: str = None,
                   approve: bool = False, dry_run: bool = False) -> list:
        """Mark requirements complete for multiple scouts.

        Args:
            adventure_id: Adventure ID
            org_guid: Organization GUID
            version_id: Adventure version ID
            user_ids: List of scout user IDs (NOT member IDs)
            requirement_ids: List of requirement IDs to mark complete
            completion_date: Date completed (YYYY-MM-DD), defaults to today
            note: Optional comment body
            approve: If True, mark as leader-approved
            dry_run: If True, show what would be sent without submitting

        Returns:
            List of result dicts (or preview dicts if dry_run)
        """
        if not completion_date:
            completion_date = date.today().isoformat()

        today = date.today().isoformat()

        entries = []
        for user_id in user_ids:
            requirements = []
            for req_id in requirement_ids:
                req = {
                    "id": req_id,
                    "dateCompleted": completion_date,
                    "markedCompletedDate": today,
                    "started": True,
                    "completed": True,
                }
                if note:
                    req["comments"] = {
                        "subject": "Bulk Entry Comment",
                        "body": note
                    }
                requirements.append(req)

            entries.append({
                "organizationGuid": org_guid,
                "userId": user_id,
                "versionId": version_id,
                "requirements": requirements,
            })

        if dry_run:
            return {
                "dry_run": True,
                "adventure_id": adventure_id,
                "scout_count": len(user_ids),
                "requirement_count": len(requirement_ids),
                "completion_date": completion_date,
                "note": note,
                "approve": approve,
                "entries": entries,
            }

        # Confirm before submitting
        print(
            f"Submitting {len(requirement_ids)} requirement(s) for "
            f"{len(user_ids)} scout(s) on adventure {adventure_id}...",
            file=sys.stderr
        )

        return self.client.mark_requirements_complete(adventure_id, entries)
