"""Message commands — list recipients and send messages."""


# The web UI auto-appends this Youth Protection reminder to all messages
YPT_FOOTER = (
    '<div><i>'
    '<b>Scouts!</b> In keeping with Youth Protection\'s no one-on-one contact '
    'rule, please remember to CC your parents/guardians or two adult leaders '
    'when communicating electronically.<br><br>'
    '<b>Adults!</b> In keeping with Youth Protection\'s no one-on-one contact '
    'rule, please remember to CC any Scouting youth\'s parents/guardians or '
    'another adult leader if you include a Scouting youth in a reply.'
    '</i></div>'
)


def _simplify_recipient(person: dict) -> dict:
    """Extract key fields from a recipient record."""
    return {
        'firstName': person.get('firstName'),
        'lastName': person.get('lastName'),
        'fullName': f"{person.get('firstName', '')} {person.get('lastName', '')}".strip(),
        'memberId': person.get('memberId'),
        'personGuid': person.get('personGuid'),
        'hasEmail': person.get('hasEmail'),
    }


class MessageCommands:
    """Commands for messaging organization members."""

    def __init__(self, client):
        self.client = client

    def list_recipients(self, org_guid: str) -> dict:
        """List all available message recipients for an organization.

        Args:
            org_guid: Organization GUID

        Returns:
            Dict with 'leaders', 'youths', 'parents' lists and counts
        """
        raw = self.client.get_recipients(org_guid)

        leaders = [_simplify_recipient(p) for p in raw.get('leaders', [])]
        parents = [_simplify_recipient(p) for p in raw.get('parents', [])]

        youths = []
        for youth in raw.get('youths', []):
            entry = _simplify_recipient(youth)
            entry['hasParentGuardianEmail'] = youth.get('hasParentGuardianEmail')
            # Include parent/guardian info for youth recipients
            guardians = []
            for rel in youth.get('relationships', []):
                guardians.append({
                    'name': f"{rel.get('firstName', '')} {rel.get('lastName', '')}".strip(),
                    'memberId': rel.get('memberId'),
                    'hasEmail': rel.get('hasEmail'),
                })
            if guardians:
                entry['guardians'] = guardians
            youths.append(entry)

        return {
            'leaders': leaders,
            'leadersCount': len(leaders),
            'youths': youths,
            'youthsCount': len(youths),
            'parents': parents,
            'parentsCount': len(parents),
        }

    def search_recipients(self, org_guid: str, query: str) -> dict:
        """Search recipients by name (case-insensitive substring match).

        Searches across leaders, youths, and parents.

        Args:
            org_guid: Organization GUID
            query: Name to search for

        Returns:
            Dict with 'matches' list, 'query', and 'count'
        """
        raw = self.client.get_recipients(org_guid)
        query_lower = query.lower()
        matches = []

        for category, people in [('leader', raw.get('leaders', [])),
                                  ('youth', raw.get('youths', [])),
                                  ('parent', raw.get('parents', []))]:
            for person in people:
                full_name = f"{person.get('firstName', '')} {person.get('lastName', '')}".lower()
                if query_lower in full_name:
                    entry = _simplify_recipient(person)
                    entry['type'] = category
                    matches.append(entry)

        return {
            'matches': matches,
            'query': query,
            'count': len(matches),
        }

    def send_message(self, org_guid: str, bcc_member_ids: list,
                     subject: str, body: str,
                     to_member_ids: list = None,
                     dry_run: bool = False,
                     no_footer: bool = False) -> dict:
        """Send a message to organization members.

        By default, recipients are added as BCC (matching the web UI behavior).
        The Youth Protection footer is automatically appended unless no_footer
        is set.

        Args:
            org_guid: Organization GUID
            bcc_member_ids: List of member IDs (BCC, default)
            subject: Email subject line
            body: Plain text message body (will be wrapped in HTML)
            to_member_ids: Optional list of member IDs for To field
            dry_run: If True, show what would be sent without actually sending
            no_footer: If True, skip the Youth Protection footer

        Returns:
            Result dict with send status or dry-run preview
        """
        to_ids = to_member_ids or []

        # Wrap plain text in HTML paragraphs
        html_body = '<div><div>'
        for paragraph in body.split('\n\n'):
            paragraph = paragraph.strip()
            if paragraph:
                # Escape basic HTML chars
                paragraph = (paragraph
                             .replace('&', '&amp;')
                             .replace('<', '&lt;')
                             .replace('>', '&gt;'))
                # Convert single newlines to <br>
                paragraph = paragraph.replace('\n', '<br>')
                html_body += f'<p>{paragraph}</p>'
        html_body += '</div>'

        if not no_footer:
            html_body += YPT_FOOTER

        html_body += '</div>'

        if dry_run:
            return {
                'dry_run': True,
                'org_guid': org_guid,
                'to_member_ids': to_ids,
                'bcc_member_ids': bcc_member_ids,
                'subject': subject,
                'body_html': html_body,
                'body_text': body,
            }

        result = self.client.send_email(
            org_guid=org_guid,
            to_member_ids=to_ids,
            bcc_member_ids=bcc_member_ids,
            subject=subject,
            body=html_body,
        )

        return {
            'status': 'sent',
            'message': result.get('message', 'Email sent.'),
            'to_count': len(to_ids),
            'bcc_count': len(bcc_member_ids),
            'subject': subject,
        }
