#!/usr/bin/env python3
"""Interactive bulk rank advancement tool.

Works for both Pack (Cub Scout adventures) and Troop (BSA rank requirements).
Auto-detects your unit from the local context cache.

READ-ONLY MODE by default. Use --write to enable submission.

Usage:
    python bulk_advance.py              # interactive, read-only
    python bulk_advance.py --org GUID   # specify org
    python bulk_advance.py --demo       # non-interactive demo
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))
from scouts_cli.client import ScoutingClient
from scouts_cli.config import BSA_RANK_NAMES

# ── BSA Ranks (Troops) ────────────────────────────────────────
BSA_RANKS = [
    {"id": 1, "name": "Scout",        "versionId": 84},
    {"id": 2, "name": "Tenderfoot",   "versionId": 83},
    {"id": 3, "name": "Second Class", "versionId": 98},
    {"id": 4, "name": "First Class",  "versionId": 99},
    {"id": 5, "name": "Star Scout",   "versionId": 40},
    {"id": 6, "name": "Life Scout",   "versionId": 41},
    {"id": 7, "name": "Eagle Scout",  "versionId": 108},
]


# ── Helpers ────────────────────────────────────────────────────
def pick_items(items, label_fn, prompt="Select (comma-separated numbers, or 'all'): "):
    """Display numbered list, return selected items."""
    for i, item in enumerate(items, 1):
        print(f"  {i:3d}. {label_fn(item)}")
    print()
    choice = input(prompt).strip()
    if choice.lower() == 'all':
        return items
    if choice.lower() in ('q', 'quit', 'exit', ''):
        return []
    try:
        indices = [int(x.strip()) - 1 for x in choice.split(',')]
        return [items[i] for i in indices if 0 <= i < len(items)]
    except (ValueError, IndexError):
        print("Invalid selection.")
        return []


def pick_one(items, label_fn, prompt="Select number: "):
    """Display numbered list, return one selected item."""
    for i, item in enumerate(items, 1):
        print(f"  {i:3d}. {label_fn(item)}")
    print()
    choice = input(prompt).strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(items):
            return items[idx]
    except (ValueError, IndexError):
        pass
    print("Invalid selection.")
    return None


def get_bsa_rank(user):
    """Extract the highest Scouts BSA rank from a raw user record."""
    for entry in user.get('highestRanksApproved', []):
        if entry.get('programId') == 2 or entry.get('program') == 'Scouts BSA':
            return entry.get('rank')
    bsa_awarded = [e for e in user.get('highestRanksAwarded', [])
                   if e.get('programId') == 2 or e.get('program') == 'Scouts BSA']
    if bsa_awarded:
        best = max(bsa_awarded, key=lambda e: e.get('level', 0))
        return best.get('rank')
    last = user.get('lastRankApproved') or {}
    if last.get('rank') in BSA_RANK_NAMES:
        return last.get('rank')
    return "Unranked"


def detect_org():
    """Auto-detect org GUID from context cache. Prefer Troop, fall back to first."""
    from scouts_cli.context import ScoutContext, CONTEXT_FILE
    ctx = ScoutContext()
    if not ctx.exists():
        return None
    data = ctx.show()
    orgs = data.get('organizations', [])
    # Prefer Troop
    for org in orgs:
        if org.get('unitType') == 'Troop':
            return org.get('orgGuid')
    # Fall back to first org
    return orgs[0].get('orgGuid') if orgs else None


def load_roster(client, org_guid):
    """Load youth roster with correct BSA rank determination."""
    raw = client.get_roster(org_guid)
    users = raw.get('users', [])
    youth = []
    for u in users:
        if not u.get('userId'):
            continue
        youth.append({
            'userId': u.get('userId'),
            'memberId': u.get('memberId'),
            'firstName': u.get('firstName'),
            'lastName': u.get('lastName'),
            'fullName': u.get('personFullName'),
            'rank': get_bsa_rank(u),
        })
    youth.sort(key=lambda m: (m.get("lastName") or "") + (m.get("firstName") or ""))
    return youth


def load_rank_requirements(client, rank):
    """Load requirements for a BSA rank."""
    result = client._make_request(
        'GET',
        f'/advancements/ranks/{rank["id"]}/requirements',
        params={'versionId': rank['versionId']}
    )
    reqs = result.get('requirements', [])
    reqs = [r for r in reqs if r.get('requirementNumber')]
    reqs.sort(key=lambda r: r.get('sortOrder', ''))
    return reqs


def load_scout_rank_status(client, org_guid, rank_id, member_ids):
    """Load current advancement status for scouts on a rank."""
    member_str = ','.join(str(m) for m in member_ids)
    result = client._make_request(
        'GET',
        f'/advancements/v2/organization/{org_guid}/ranks/{rank_id}/userRequirements',
        params={'memberId': member_str}
    )
    return result if isinstance(result, list) else []


# ── Main Flow ──────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Bulk rank advancement")
    parser.add_argument("--org", help="Organization GUID (auto-detected if omitted)")
    parser.add_argument("--demo", action="store_true", help="Non-interactive demo")
    args = parser.parse_args()

    org_guid = args.org or detect_org()
    if not org_guid:
        print("No organization found. Run 'scouts auth login' first, or pass --org.")
        sys.exit(1)

    print()
    print("=" * 60)
    print("  BULK RANK ADVANCEMENT")
    print("  [READ-ONLY MODE — no changes will be made]")
    print("=" * 60)
    print(f"  Org: {org_guid}")
    print()

    client = ScoutingClient()

    # Step 1: Load roster and pick scouts
    print("Loading roster...")
    roster = load_roster(client, org_guid)
    if not roster:
        print("Failed to load roster.")
        return
    print(f"  {len(roster)} scouts loaded.\n")

    if args.demo:
        selected_scouts = roster[:3]
        print(f"[DEMO] Auto-selected first 3 scouts:")
        for s in selected_scouts:
            print(f"  - {s.get('fullName')}  rank: {s.get('rank')}")
    else:
        print("Select scouts:")
        selected_scouts = pick_items(
            roster,
            lambda s: f"{s.get('fullName', '?'):25s}  rank: {s.get('rank', '?')}",
            prompt="Select scouts (comma-separated, or 'all'): "
        )
    if not selected_scouts:
        print("No scouts selected.")
        return

    # Step 2: Pick a rank
    if args.demo:
        rank = BSA_RANKS[1]  # Tenderfoot
        print(f"\n[DEMO] Auto-selected rank: {rank['name']}")
    else:
        print(f"\nSelect rank to work on:")
        rank = pick_one(BSA_RANKS, lambda r: r["name"], prompt="Rank: ")
    if not rank:
        return

    # Step 3: Load requirements
    print(f"\nLoading {rank['name']} requirements...")
    requirements = load_rank_requirements(client, rank)
    if not requirements:
        print("No requirements found.")
        return
    print(f"  {len(requirements)} requirements loaded.\n")

    # Step 4: Show current status
    print(f"Checking current {rank['name']} status for {len(selected_scouts)} scout(s)...")
    member_ids = [s['memberId'] for s in selected_scouts]
    statuses = load_scout_rank_status(client, org_guid, rank['id'], member_ids)

    status_by_member = {}
    for entry in statuses:
        mid = entry.get('memberId')
        req_status = {}
        for req in entry.get('requirements', []):
            req_status[req['id']] = req
        status_by_member[mid] = {
            'rank_status': entry.get('status'),
            'requirements': req_status,
        }

    print()
    for scout in selected_scouts:
        mid = scout['memberId']
        scout_status = status_by_member.get(mid, {'rank_status': None, 'requirements': {}})
        rank_st = scout_status['rank_status'] or 'Not started'
        done_count = sum(
            1 for req in requirements
            if scout_status['requirements'].get(int(req['id']), {}).get('status')
            in ('Leader Approved', 'Completed')
        )
        print(f"  {scout.get('fullName', '?'):25s}  [{rank_st}]  {done_count}/{len(requirements)} complete")

    # Step 5: Pick requirements
    if args.demo:
        selected_reqs = requirements[:5]
        print(f"\n[DEMO] Auto-selected first 5 requirements")
    else:
        print(f"\nRequirements for {rank['name']}:")

        def req_label(r):
            req_id = int(r['id'])
            statuses_for_req = []
            for scout in selected_scouts:
                mid = scout['memberId']
                s = status_by_member.get(mid, {'requirements': {}})
                req_data = s['requirements'].get(req_id)
                if req_data and req_data.get('status') in ('Leader Approved', 'Completed'):
                    statuses_for_req.append('done')
                elif req_data and req_data.get('dateCompleted'):
                    statuses_for_req.append('pending')
                else:
                    statuses_for_req.append('none')
            if all(s == 'done' for s in statuses_for_req):
                indicator = "✓"
            elif any(s != 'none' for s in statuses_for_req):
                indicator = "●"
            else:
                indicator = "-"
            return f"[{indicator}] {r['requirementNumber']:4s} {r.get('short', r.get('name', ''))[:50]}"

        selected_reqs = pick_items(
            requirements,
            req_label,
            prompt="Select requirements to mark (comma-separated, or 'all'): "
        )
    if not selected_reqs:
        print("No requirements selected.")
        return

    # Step 6: Status matrix
    print()
    print("=" * 60)
    print(f"  DETAIL: {rank['name']} — Selected Requirements")
    print("=" * 60)
    print()

    req_nums = [r['requirementNumber'] for r in selected_reqs]
    header = f"  {'Scout':<22s} | " + " | ".join(f"{n:^5s}" for n in req_nums)
    print(header)
    print("  " + "-" * (len(header) - 2))

    for scout in selected_scouts:
        mid = scout['memberId']
        scout_status = status_by_member.get(mid, {'rank_status': None, 'requirements': {}})
        cells = []
        for req in selected_reqs:
            req_data = scout_status['requirements'].get(int(req['id']))
            if req_data and req_data.get('status') in ('Leader Approved', 'Completed'):
                cells.append("  ✓  ")
            elif req_data and req_data.get('dateCompleted'):
                cells.append("  ●  ")
            else:
                cells.append("  -  ")
        name = scout.get('fullName', '?')[:22]
        print(f"  {name:<22s} | " + " | ".join(cells))

    print()
    print("  Legend: ✓ = approved, ● = completed (not yet approved), - = not done")

    # Step 7: Preview
    print()
    print("=" * 60)
    print("  PREVIEW (what would be submitted)")
    print("=" * 60)
    print()
    print(f"  Rank:         {rank['name']}")
    print(f"  Scouts:       {len(selected_scouts)}")
    for s in selected_scouts:
        uid_str = f"userId={s.get('userId')}" if s.get('userId') else "NO userId!"
        print(f"                - {s.get('fullName')} ({uid_str})")
    print(f"  Requirements: {len(selected_reqs)}")
    for r in selected_reqs:
        print(f"                - [{r['requirementNumber']}] {r.get('short', '')[:40]} (id={r['id']})")
    print(f"  Date:         (today)")
    print()
    print("  ** READ-ONLY MODE — nothing was submitted **")
    print()


if __name__ == "__main__":
    main()
