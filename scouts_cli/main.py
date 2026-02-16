"""Main CLI entry point for Scouts CLI.

Handles argument parsing, command routing, and output coordination.
"""

import sys
import argparse

from .client import ScoutingClient, ScoutingError
from .client.auth import ScoutingAuth
from .commands import (
    LookupCommands, AdvancementCommands, ReferenceCommands,
    RosterCommands, ProfileCommands, OrgCommands, MessageCommands,
)
from .context import ScoutContext
from .formatters import JsonFormatter, HumanFormatter
from .utils.safety import confirm_send_message
from . import __version__


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for Scouts CLI."""

    parser = argparse.ArgumentParser(
        prog='scouts',
        description='BSA Internet Advancement CLI - Manage scout advancement programmatically',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Authenticate (opens browser for Google sign-in)
  scouts auth login
  scouts auth login --token "eyJhbG..."    # manual fallback

  # Check auth status
  scouts auth status

  # View your profile, scouts, roles, training, registrations
  scouts profile me
  scouts profile my-scouts
  scouts profile roles
  scouts profile training
  scouts profile registrations

  # Organization info (list all your orgs, then drill into one)
  scouts org list
  scouts org profile --org F4C19DEB-...
  scouts org dens --org F4C19DEB-...
  scouts org activities --org F4C19DEB-...

  # Roster: youth, adults, parents, search
  scouts roster list --org F4C19DEB-...
  scouts roster search --org F4C19DEB-... "James"
  scouts roster adults --org F4C19DEB-...
  scouts roster parents --org F4C19DEB-...

  # Ranks, adventures, merit badges, awards
  scouts rank list
  scouts adventure list --rank-id 10
  scouts adventure requirements 124 --version-id 287
  scouts merit-badge list
  scouts award list

  # Scout-specific advancement detail (merit badges, ranks, leadership, activity)
  scouts profile merit-badges 10312245
  scouts profile ranks 10312245
  scouts profile leadership 10312245
  scouts profile activity-summary 10312245

  # Advancement status and bulk entry
  scouts advancement status --org F4C19DEB-... --adventure 124 --members 140325643
  scouts advancement bulk-entry --org F4C19DEB-... --adventure 124 --version-id 287 \\
      --users 14048576 --requirements 2118 --date 2026-02-15 --approve

  # Messaging
  scouts message recipients --org F4C19DEB-...
  scouts message search --org F4C19DEB-... "John"
  scouts message send --org F4C19DEB-... --bcc 136612736,135608909 \\
      --subject "Meeting reminder" --body "Pack meeting Thursday at 6pm" --dry-run
"""
    )
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('--human', action='store_true',
                        help='Human-readable output instead of JSON')
    parser.add_argument('--verbose', action='store_true',
                        help='Verbose logging (show HTTP requests)')

    subparsers = parser.add_subparsers(dest='resource', help='Resource to manage')

    # ── auth ────────────────────────────────────────────────────
    auth_parser = subparsers.add_parser('auth', help='Authentication management',
)
    auth_sub = auth_parser.add_subparsers(dest='action')

    login_parser = auth_sub.add_parser('login',
        help='Authenticate (opens browser, or use --token for manual)')
    login_parser.add_argument('--token', required=False, default=None,
        help='JWT token (if omitted, opens browser for Google sign-in)')

    auth_sub.add_parser('status', help='Show current auth status')
    auth_sub.add_parser('logout', help='Remove cached token')

    # ── rank ────────────────────────────────────────────────────
    rank_parser = subparsers.add_parser('rank', help='Rank operations',
)
    rank_sub = rank_parser.add_subparsers(dest='action')

    list_parser = rank_sub.add_parser('list', help='List all ranks')
    list_parser.add_argument('--program-id', type=int, help='Filter by program ID')

    # ── adventure ───────────────────────────────────────────────
    adv_parser = subparsers.add_parser('adventure', help='Adventure operations',
)
    adv_sub = adv_parser.add_subparsers(dest='action')

    adv_list_parser = adv_sub.add_parser('list', help='List all adventures')
    adv_list_parser.add_argument('--rank-id', type=int, help='Filter by rank ID')

    req_parser = adv_sub.add_parser('requirements', help='Get adventure requirements')
    req_parser.add_argument('adventure_id', type=int, help='Adventure ID')
    req_parser.add_argument('--version-id', type=int, required=True, help='Version ID')

    # ── advancement ─────────────────────────────────────────────
    advancement_parser = subparsers.add_parser('advancement', help='Advancement operations',
       )
    advancement_sub = advancement_parser.add_subparsers(dest='action')

    # advancement status
    status_parser = advancement_sub.add_parser('status', help='Get scout advancement status')
    status_parser.add_argument('--org', required=True, help='Organization GUID')
    status_parser.add_argument('--adventure', type=int, required=True, help='Adventure ID')
    status_parser.add_argument('--members', required=True,
                               help='Comma-separated member IDs')

    # advancement bulk-entry
    bulk_parser = advancement_sub.add_parser('bulk-entry',
                                             help='Mark requirements complete for scouts')
    bulk_parser.add_argument('--org', required=True, help='Organization GUID')
    bulk_parser.add_argument('--adventure', type=int, required=True, help='Adventure ID')
    bulk_parser.add_argument('--version-id', type=int, required=True, help='Adventure version ID')
    bulk_parser.add_argument('--users', required=True,
                             help='Comma-separated user IDs (NOT member IDs)')
    bulk_parser.add_argument('--requirements', required=True,
                             help='Comma-separated requirement IDs')
    bulk_parser.add_argument('--date', help='Completion date (YYYY-MM-DD), default: today')
    bulk_parser.add_argument('--note', help='Comment/note text')
    bulk_parser.add_argument('--approve', action='store_true',
                             help='Mark as leader-approved')
    bulk_parser.add_argument('--dry-run', action='store_true',
                             help='Show what would be sent without submitting')

    # ── dashboard ───────────────────────────────────────────────
    dash_parser = subparsers.add_parser('dashboard', help='Organization dashboard',
)
    dash_parser.add_argument('org_guid', help='Organization GUID')

    # ── profile ────────────────────────────────────────────────
    profile_parser = subparsers.add_parser('profile', help='Profile information')
    profile_sub = profile_parser.add_subparsers(dest='action')

    profile_sub.add_parser('me', help='Show your profile')
    profile_sub.add_parser('my-scouts', help='Show your scouts (parent/guardian)')
    profile_sub.add_parser('roles', help='Show your roles and permissions')
    profile_sub.add_parser('training', help='Show your YPT training status')

    profile_reg_parser = profile_sub.add_parser('registrations',
                                                 help='Show your membership registrations')
    profile_reg_parser.add_argument('--org', help='Filter by organization GUID')

    scout_profile_parser = profile_sub.add_parser('scout',
                                                   help='Show a specific scout profile')
    scout_profile_parser.add_argument('user_id', type=int, help='Scout user ID')

    scout_mb_parser = profile_sub.add_parser('merit-badges',
                                              help='Show a scout\'s merit badge progress')
    scout_mb_parser.add_argument('user_id', type=int, help='Scout user ID')

    scout_ranks_parser = profile_sub.add_parser('ranks',
                                                 help='Show a scout\'s rank progression')
    scout_ranks_parser.add_argument('user_id', type=int, help='Scout user ID')

    scout_leadership_parser = profile_sub.add_parser('leadership',
                                                      help='Show a scout\'s leadership positions')
    scout_leadership_parser.add_argument('user_id', type=int, help='Scout user ID')

    scout_activity_parser = profile_sub.add_parser('activity-summary',
                                                    help='Show a scout\'s activity logs')
    scout_activity_parser.add_argument('user_id', type=int, help='Scout user ID')

    # ── roster ─────────────────────────────────────────────────
    roster_parser = subparsers.add_parser('roster', help='Scout roster operations')
    roster_sub = roster_parser.add_subparsers(dest='action')

    roster_list_parser = roster_sub.add_parser('list', help='List all scouts in the organization')
    roster_list_parser.add_argument('--org', required=True, help='Organization GUID')
    roster_list_parser.add_argument('--refresh', action='store_true',
                                    help='Force fresh API call (ignore cache)')

    roster_search_parser = roster_sub.add_parser('search', help='Search scouts by name')
    roster_search_parser.add_argument('--org', required=True, help='Organization GUID')
    roster_search_parser.add_argument('query', help='Name to search for (case-insensitive)')
    roster_search_parser.add_argument('--refresh', action='store_true',
                                      help='Force fresh API call (ignore cache)')

    roster_adults_parser = roster_sub.add_parser('adults', help='List adult leaders')
    roster_adults_parser.add_argument('--org', required=True, help='Organization GUID')

    roster_parents_parser = roster_sub.add_parser('parents',
                                                   help='List parent-youth relationships')
    roster_parents_parser.add_argument('--org', required=True, help='Organization GUID')

    roster_resolve_parser = roster_sub.add_parser('resolve',
        help='Resolve a scout name to userId/orgGuid across ALL organizations')
    roster_resolve_parser.add_argument('query',
        help='Scout name to search for (case-insensitive)')
    roster_resolve_parser.add_argument('--refresh', action='store_true',
        help='Force API call (ignore cached context)')

    # ── org ───────────────────────────────────────────────────
    org_parser = subparsers.add_parser('org', help='Organization information')
    org_sub = org_parser.add_subparsers(dest='action')

    org_list_parser = org_sub.add_parser('list',
        help='List all your organizations (role picker)')
    org_list_parser.add_argument('--refresh', action='store_true',
        help='Force API call (ignore cached context)')

    org_profile_parser = org_sub.add_parser('profile', help='Show organization profile')
    org_profile_parser.add_argument('--org', required=True, help='Organization GUID')

    org_dens_parser = org_sub.add_parser('dens', help='List dens/sub-units')
    org_dens_parser.add_argument('--org', required=True, help='Organization GUID')

    org_activities_parser = org_sub.add_parser('activities',
                                                help='Show activities dashboard')
    org_activities_parser.add_argument('--org', required=True, help='Organization GUID')

    # ── merit-badge ───────────────────────────────────────────
    mb_parser = subparsers.add_parser('merit-badge', help='Merit badge operations')
    mb_sub = mb_parser.add_subparsers(dest='action')
    mb_sub.add_parser('list', help='List all merit badges')

    # ── award ─────────────────────────────────────────────────
    award_parser = subparsers.add_parser('award', help='Award operations')
    award_sub = award_parser.add_subparsers(dest='action')
    award_sub.add_parser('list', help='List all awards')

    # ── ss-elective ───────────────────────────────────────────
    ss_parser = subparsers.add_parser('ss-elective', help='Sea Scout elective operations')
    ss_sub = ss_parser.add_subparsers(dest='action')
    ss_sub.add_parser('list', help='List all Sea Scout electives')

    # ── message ───────────────────────────────────────────────
    msg_parser = subparsers.add_parser('message', help='Messaging operations')
    msg_sub = msg_parser.add_subparsers(dest='action')

    msg_recipients_parser = msg_sub.add_parser('recipients',
                                                help='List available recipients')
    msg_recipients_parser.add_argument('--org', required=True, help='Organization GUID')

    msg_search_parser = msg_sub.add_parser('search',
                                            help='Search recipients by name')
    msg_search_parser.add_argument('--org', required=True, help='Organization GUID')
    msg_search_parser.add_argument('query', help='Name to search for')

    msg_send_parser = msg_sub.add_parser('send', help='Send a message')
    msg_send_parser.add_argument('--org', required=True, help='Organization GUID')
    msg_send_parser.add_argument('--bcc', required=True,
                                  help='Comma-separated member IDs (BCC recipients)')
    msg_send_parser.add_argument('--to',
                                  help='Comma-separated member IDs (To recipients, optional)')
    msg_send_parser.add_argument('--subject', required=True, help='Message subject')
    msg_send_parser.add_argument('--body', required=True, help='Message body (plain text)')
    msg_send_parser.add_argument('--dry-run', action='store_true',
                                  help='Show what would be sent without actually sending')
    msg_send_parser.add_argument('--no-footer', action='store_true',
                                  help='Skip the Youth Protection reminder footer')

    # ── context ───────────────────────────────────────────────
    ctx_parser = subparsers.add_parser('context',
        help='Local context cache (scouts, orgs, IDs)')
    ctx_sub = ctx_parser.add_subparsers(dest='action')

    ctx_sub.add_parser('show', help='Show cached context (scouts, orgs, user)')
    ctx_sub.add_parser('refresh', help='Refresh context from API')
    ctx_sub.add_parser('path', help='Print context file path')

    # ── reference ──────────────────────────────────────────────
    ref_parser = subparsers.add_parser('reference', help='Reference data operations')
    ref_sub = ref_parser.add_subparsers(dest='action')

    dump_parser = ref_sub.add_parser('dump',
        help='Dump complete rank/adventure/requirement tree for agent context')
    dump_parser.add_argument('--output', '-o',
        help='Output file path (default: stdout as JSON)')
    dump_parser.add_argument('--rank-ids',
        help='Comma-separated rank IDs (default: Cub Scouting ranks)')

    return parser


def main():
    """Main entry point."""
    # Pre-parse global flags so they work anywhere in the command line
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument('--human', action='store_true')
    global_parser.add_argument('--verbose', action='store_true')
    global_args, remaining = global_parser.parse_known_args()

    parser = create_parser()
    args = parser.parse_args(remaining)

    # Merge global flags into args
    args.human = global_args.human
    args.verbose = global_args.verbose

    if not args.resource:
        parser.print_help()
        sys.exit(0)

    formatter = HumanFormatter() if args.human else JsonFormatter()

    try:
        # ── auth (no client needed) ─────────────────────────────
        if args.resource == 'auth':
            auth = ScoutingAuth()

            if args.action == 'login':
                if args.token:
                    auth.login_with_token(args.token)
                    formatter.output_result({"status": "authenticated", "message": "Token saved."})
                else:
                    info = auth.login_with_browser(
                        verbose=getattr(args, 'verbose', False))
                    formatter.output_result({
                        "status": "authenticated",
                        "message": "Browser login successful. Token saved.",
                        "user": info.get("user"),
                        "expires_at": info.get("expires_at"),
                    })

            elif args.action == 'status':
                info = auth.get_token_info()
                if not info:
                    formatter.output_result({"status": "not_authenticated"})
                else:
                    formatter.output_result({
                        "status": "expired" if info.get("is_expired") else "authenticated",
                        "user": info.get("user"),
                        "uid": info.get("uid"),
                        "expires_at": info.get("expires_at"),
                    })

            elif args.action == 'logout':
                auth.logout()
                formatter.output_result({"status": "logged_out"})

            else:
                parser.parse_args(['auth', '--help'])

            sys.exit(0)

        # ── context (show/path don't need client) ────────────────
        if args.resource == 'context':
            ctx = ScoutContext()
            if args.action == 'show':
                result = ctx.show()
                formatter.output_result(result)
                sys.exit(0)
            elif args.action == 'path':
                from .context import CONTEXT_FILE
                formatter.output_result({'path': CONTEXT_FILE})
                sys.exit(0)
            elif args.action == 'refresh':
                # refresh needs a client — fall through
                pass
            else:
                parser.parse_args(['context', '--help'])
                sys.exit(0)

        # ── All other commands require a client ─────────────────
        client = ScoutingClient(verbose=getattr(args, 'verbose', False))

        # ── Auto-populate or auto-refresh stale context ──────────
        ctx = ScoutContext()
        if not ctx.exists():
            print("Populating local context (first run)...", file=sys.stderr)
            ctx.refresh(client)
            print("Context saved.", file=sys.stderr)
        elif ctx.is_stale():
            print("Context is stale, refreshing...", file=sys.stderr)
            ctx.refresh(client)
            print("Context refreshed.", file=sys.stderr)

        # ── context refresh (needs client) ───────────────────────
        if args.resource == 'context' and args.action == 'refresh':
            ctx = ScoutContext()
            data = ctx.refresh(client)
            scout_names = [s.get('fullName') for s in data.get('scouts', [])]
            org_names = [o.get('name') for o in data.get('organizations', [])]
            formatter.output_result({
                'status': 'refreshed',
                'scouts': scout_names,
                'organizations': org_names,
                'scoutCount': len(scout_names),
                'organizationCount': len(org_names),
            })
            sys.exit(0)

        if args.resource == 'rank':
            cmds = LookupCommands(client)
            if args.action == 'list':
                result = cmds.list_ranks(program_id=getattr(args, 'program_id', None))
                formatter.output_result(result)
            else:
                parser.parse_args(['rank', '--help'])

        elif args.resource == 'adventure':
            cmds = LookupCommands(client)
            if args.action == 'list':
                result = cmds.list_adventures(rank_id=getattr(args, 'rank_id', None))
                formatter.output_result(result)
            elif args.action == 'requirements':
                result = cmds.get_adventure_requirements(args.adventure_id, args.version_id)
                formatter.output_result(result)
            else:
                parser.parse_args(['adventure', '--help'])

        elif args.resource == 'advancement':
            cmds = AdvancementCommands(client)

            if args.action == 'status':
                member_ids = [int(m.strip()) for m in args.members.split(',')]
                result = cmds.get_user_requirements(args.org, args.adventure, member_ids)
                formatter.output_result(result)

            elif args.action == 'bulk-entry':
                user_ids = [int(u.strip()) for u in args.users.split(',')]
                req_ids = [int(r.strip()) for r in args.requirements.split(',')]
                result = cmds.bulk_entry(
                    adventure_id=args.adventure,
                    org_guid=args.org,
                    version_id=args.version_id,
                    user_ids=user_ids,
                    requirement_ids=req_ids,
                    completion_date=args.date,
                    note=args.note,
                    approve=args.approve,
                    dry_run=args.dry_run,
                )
                formatter.output_result(result)

            else:
                parser.parse_args(['advancement', '--help'])

        elif args.resource == 'dashboard':
            cmds = LookupCommands(client)
            result = cmds.get_dashboard(args.org_guid)
            formatter.output_result(result)

        elif args.resource == 'profile':
            cmds = ProfileCommands(client)
            if args.action == 'me':
                result = cmds.get_my_profile()
                formatter.output_result(result)
            elif args.action == 'my-scouts':
                result = cmds.get_my_scouts()
                formatter.output_result(result)
            elif args.action == 'roles':
                result = cmds.get_my_roles()
                formatter.output_result(result)
            elif args.action == 'training':
                result = cmds.get_my_training()
                formatter.output_result(result)
            elif args.action == 'registrations':
                result = cmds.get_my_registrations(
                    org_guid=getattr(args, 'org', None))
                formatter.output_result(result)
            elif args.action == 'scout':
                result = cmds.get_scout_profile(args.user_id)
                formatter.output_result(result)
            elif args.action == 'merit-badges':
                result = cmds.get_scout_merit_badges(args.user_id)
                formatter.output_result(result)
            elif args.action == 'ranks':
                result = cmds.get_scout_ranks(args.user_id)
                formatter.output_result(result)
            elif args.action == 'leadership':
                result = cmds.get_scout_leadership(args.user_id)
                formatter.output_result(result)
            elif args.action == 'activity-summary':
                result = cmds.get_scout_activity_summary(args.user_id)
                formatter.output_result(result)
            else:
                parser.parse_args(['profile', '--help'])

        elif args.resource == 'roster':
            cmds = RosterCommands(client)
            if args.action == 'list':
                result = cmds.list_roster(args.org,
                                          refresh=getattr(args, 'refresh', False))
                formatter.output_result(result)
            elif args.action == 'search':
                result = cmds.search_scouts(args.org, args.query,
                                            refresh=getattr(args, 'refresh', False))
                formatter.output_result(result)
            elif args.action == 'adults':
                result = cmds.list_adults(args.org)
                formatter.output_result(result)
            elif args.action == 'parents':
                result = cmds.list_parents(args.org)
                formatter.output_result(result)
            elif args.action == 'resolve':
                result = cmds.resolve(args.query,
                                      refresh=getattr(args, 'refresh', False))
                formatter.output_result(result)
            else:
                parser.parse_args(['roster', '--help'])

        elif args.resource == 'org':
            cmds = OrgCommands(client)
            if args.action == 'list':
                result = cmds.list_orgs(
                    refresh=getattr(args, 'refresh', False))
                formatter.output_result(result)
            elif args.action == 'profile':
                result = cmds.get_org_profile(args.org)
                formatter.output_result(result)
            elif args.action == 'dens':
                result = cmds.get_dens(args.org)
                formatter.output_result(result)
            elif args.action == 'activities':
                result = cmds.get_activities(args.org)
                formatter.output_result(result)
            else:
                parser.parse_args(['org', '--help'])

        elif args.resource == 'merit-badge':
            cmds = LookupCommands(client)
            if args.action == 'list':
                result = cmds.list_merit_badges()
                formatter.output_result(result)
            else:
                parser.parse_args(['merit-badge', '--help'])

        elif args.resource == 'award':
            cmds = LookupCommands(client)
            if args.action == 'list':
                result = cmds.list_awards()
                formatter.output_result(result)
            else:
                parser.parse_args(['award', '--help'])

        elif args.resource == 'ss-elective':
            cmds = LookupCommands(client)
            if args.action == 'list':
                result = cmds.list_ss_electives()
                formatter.output_result(result)
            else:
                parser.parse_args(['ss-elective', '--help'])

        elif args.resource == 'message':
            cmds = MessageCommands(client)
            if args.action == 'recipients':
                result = cmds.list_recipients(args.org)
                formatter.output_result(result)
            elif args.action == 'search':
                result = cmds.search_recipients(args.org, args.query)
                formatter.output_result(result)
            elif args.action == 'send':
                bcc_ids = [int(m.strip()) for m in args.bcc.split(',')]
                to_ids = []
                if getattr(args, 'to', None):
                    to_ids = [int(m.strip()) for m in args.to.split(',')]
                dry_run = getattr(args, 'dry_run', False)

                # Require human confirmation before sending (skip for dry-run)
                if not dry_run:
                    confirmed, _ = confirm_send_message(
                        recipient_count=len(to_ids) + len(bcc_ids),
                        subject=args.subject,
                        body_preview=args.body,
                        to_count=len(to_ids),
                        bcc_count=len(bcc_ids),
                    )
                    if not confirmed:
                        formatter.output_result({
                            'status': 'cancelled',
                            'message': 'Message send cancelled by user.',
                        })
                        sys.exit(0)

                result = cmds.send_message(
                    org_guid=args.org,
                    bcc_member_ids=bcc_ids,
                    subject=args.subject,
                    body=args.body,
                    to_member_ids=to_ids,
                    dry_run=dry_run,
                    no_footer=getattr(args, 'no_footer', False),
                )
                formatter.output_result(result)
            else:
                parser.parse_args(['message', '--help'])

        elif args.resource == 'reference':
            cmds = ReferenceCommands(client)
            if args.action == 'dump':
                rank_ids = None
                if getattr(args, 'rank_ids', None):
                    rank_ids = [int(r.strip()) for r in args.rank_ids.split(',')]
                result = cmds.dump_all(
                    output_file=getattr(args, 'output', None),
                    rank_ids=rank_ids,
                )
                formatter.output_result(result)
            else:
                parser.parse_args(['reference', '--help'])

        else:
            parser.print_help()

    except ScoutingError as e:
        formatter.output_error(e)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        formatter.output_error(e)
        sys.exit(1)


if __name__ == '__main__':
    main()
