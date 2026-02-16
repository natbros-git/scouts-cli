"""Reference data commands - dump complete rank/adventure/requirement tree."""

import sys
import json
import time


class ReferenceCommands:
    """Commands for reference data retrieval."""

    def __init__(self, client):
        self.client = client

    def dump_all(self, output_file: str = None, rank_ids: list = None) -> dict:
        """Dump the complete rank -> adventure -> requirements tree.

        Args:
            output_file: Optional path to save JSON output
            rank_ids: Optional list of rank IDs to include (default: all Cub Scouting)

        Returns:
            Complete reference data tree
        """
        if not rank_ids:
            # Default: Cub Scouting ranks
            rank_ids = [14, 8, 9, 10, 11, 12]  # Lion, Tiger, Wolf, Bear, Webelos, AOL

        print(f"Fetching reference data for {len(rank_ids)} ranks...", file=sys.stderr)

        # Get all ranks first
        all_ranks = self.client.get_ranks()
        rank_map = {}
        if isinstance(all_ranks, dict) and 'ranks' in all_ranks:
            for r in all_ranks['ranks']:
                rank_map[int(r['id'])] = {
                    'name': r['name'],
                    'program': r['program'],
                }

        result = {"ranks": []}
        total_adventures = 0
        total_requirements = 0

        for rank_id in rank_ids:
            rank_info = rank_map.get(rank_id, {'name': f'Rank {rank_id}', 'program': 'Unknown'})
            print(f"  Fetching adventures for {rank_info['name']}...", file=sys.stderr)

            # Get adventures for this rank
            adventures_response = self.client._make_request(
                'GET', '/advancements/adventures',
                params={'rankId': rank_id}
            )
            all_adventures = adventures_response.get('adventures', [])

            # Filter to only this rank's adventures and latest version
            rank_adventures = {}
            for adv in all_adventures:
                if int(adv.get('rankId', 0)) != rank_id:
                    continue
                name = adv['name']
                version = adv.get('version', 0) or 0
                if isinstance(version, str):
                    version = int(version) if version.isdigit() else 0
                # Keep the latest version of each adventure
                if name not in rank_adventures or version > rank_adventures[name].get('_version_num', 0):
                    rank_adventures[name] = {
                        'id': adv['id'],
                        'name': name,
                        'versionId': adv.get('versionId'),
                        'version': adv.get('version'),
                        'required': adv.get('required'),
                        'sortOrder': adv.get('sortOrder'),
                        '_version_num': version,
                    }

            # Fetch requirements for each adventure
            adventures_with_reqs = []
            for adv_name, adv in sorted(rank_adventures.items()):
                adv_id = adv['id']
                version_id = adv['versionId']
                if not version_id:
                    continue

                try:
                    req_data = self.client.get_adventure_requirements(adv_id, version_id)
                    requirements = []
                    for req in req_data.get('requirements', []):
                        if not req.get('number'):
                            continue  # Skip non-requirement entries (like resource links)
                        requirements.append({
                            'id': req['id'],
                            'number': req['number'],
                            'name': req['name'][:120],
                            'required': req.get('required', True),
                        })
                        total_requirements += 1

                    adventures_with_reqs.append({
                        'id': adv_id,
                        'name': adv_name,
                        'versionId': version_id,
                        'version': adv['version'],
                        'required': adv['required'],
                        'requirements': sorted(requirements, key=lambda r: r.get('number', '')),
                    })
                    total_adventures += 1

                    # Be polite to the API
                    time.sleep(0.1)

                except Exception as e:
                    print(f"    Warning: Failed to get requirements for {adv_name}: {e}",
                          file=sys.stderr)

            result["ranks"].append({
                'id': rank_id,
                'name': rank_info['name'],
                'program': rank_info['program'],
                'adventures': sorted(adventures_with_reqs,
                                     key=lambda a: (not a['required'], a['name'])),
            })

            print(f"    Found {len(adventures_with_reqs)} adventures", file=sys.stderr)

        result["summary"] = {
            "ranks": len(result["ranks"]),
            "total_adventures": total_adventures,
            "total_requirements": total_requirements,
        }

        if output_file:
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Reference data saved to: {output_file}", file=sys.stderr)

        return result
