"""
Safety confirmation utilities for message-sending operations.

Requires user to type a confirmation code before sending messages through the
BSA Internet Advancement messaging system. This prevents AI agents from
sending emails to scout families without explicit human approval.

Confirmation Methods:
- GUI Dialog: Uses system modal dialog (macOS osascript) when no TTY available
  (typical in agent environments). Set SCOUTS_GUI_CONFIRM=1 to force GUI mode.
- Terminal: Uses input() for confirmation code entry when running interactively.

Modeled after the Symphony CLI safety module.
"""

import json
import os
import sys
import secrets
import subprocess
from datetime import datetime
from typing import Optional, Tuple


def _is_gui_mode() -> bool:
    """Check if GUI confirmation mode should be used."""
    if os.environ.get('SCOUTS_GUI_CONFIRM', '').lower() in ('1', 'true', 'yes'):
        return True
    if not sys.stdin.isatty():
        return True
    return False


def _show_gui_dialog(title: str, message: str, code: str) -> Optional[str]:
    """
    Show a GUI dialog for confirmation code entry.

    Supports macOS (osascript), Windows (PowerShell), and Linux (zenity/kdialog).

    Returns:
        User's input string, or None if cancelled/error
    """
    platform = sys.platform

    if platform == 'darwin':
        script = f'''
        set userInput to text returned of (display dialog "{message}\\n\\nTo proceed, type exactly: {code}\\n(Leave empty to cancel)" ¬
            default answer "" ¬
            with title "{title}" ¬
            buttons {{"Cancel", "Confirm"}} ¬
            default button "Confirm" ¬
            with icon caution)
        return userInput
        '''
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return None

    elif platform == 'win32':
        ps_script = f'''
        Add-Type -AssemblyName Microsoft.VisualBasic
        $result = [Microsoft.VisualBasic.Interaction]::InputBox(
            "{message}`n`nTo proceed, type exactly: {code}`n(Leave empty to cancel)",
            "{title}",
            ""
        )
        Write-Output $result
        '''
        try:
            result = subprocess.run(
                ['powershell', '-Command', ps_script],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return None

    else:
        dialog_message = f"{message}\n\nTo proceed, type exactly: {code}\n(Leave empty to cancel)"
        try:
            result = subprocess.run(
                ['zenity', '--entry', '--title', title,
                 '--text', dialog_message, '--width', '400'],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except FileNotFoundError:
            pass
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return None

        try:
            result = subprocess.run(
                ['kdialog', '--title', title, '--inputbox', dialog_message],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except FileNotFoundError:
            pass
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return None

        return None


def generate_confirmation_code() -> str:
    """
    Generate a short random code like 'SEND-7X3K'.

    Uses only unambiguous characters (no 0/O, 1/I/L confusion).
    """
    alphabet = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    suffix = ''.join(secrets.choice(alphabet) for _ in range(4))
    return f"SEND-{suffix}"


def confirm_send_message(
    recipient_count: int,
    subject: str,
    body_preview: str,
    to_count: int = 0,
    bcc_count: int = 0,
) -> Tuple[bool, Optional[str]]:
    """
    Require user confirmation before sending a message through BSA messaging.

    CANNOT be bypassed. This is intentional — agents should not send emails
    to scout families without a human explicitly approving each message.

    Args:
        recipient_count: Total number of recipients
        subject: Email subject line
        body_preview: First ~200 chars of message body
        to_count: Number of To recipients
        bcc_count: Number of BCC recipients

    Returns:
        Tuple of (confirmed: bool, confirmation_code: str or None)
    """
    code = generate_confirmation_code()

    # Truncate body preview for dialog display
    if len(body_preview) > 200:
        body_preview = body_preview[:200] + '...'

    # Build the impact message
    recipient_parts = []
    if to_count:
        recipient_parts.append(f"{to_count} To")
    if bcc_count:
        recipient_parts.append(f"{bcc_count} BCC")
    recipient_summary = ', '.join(recipient_parts) if recipient_parts else f"{recipient_count} recipients"

    impact = (
        f"Recipients: {recipient_summary}\n"
        f"Subject: {subject}\n"
        f"Message: {body_preview}"
    )

    if _is_gui_mode():
        response = _show_gui_dialog(
            title="Scouts CLI - Confirm Send Message",
            message=(
                f"SENDING EMAIL VIA BSA INTERNET ADVANCEMENT\n\n{impact}"
            ),
            code=code
        )
        if response is None:
            if sys.stdin.isatty():
                print("\nGUI dialog cancelled or unavailable, falling back to terminal...",
                      file=sys.stderr)
            else:
                print("\nMessage send cancelled (no confirmation provided).",
                      file=sys.stderr)
                _log_send_attempt(subject, recipient_count, confirmed=False,
                                  confirmation_code=code)
                return False, None

        if response == code:
            _log_send_attempt(subject, recipient_count, confirmed=True,
                              confirmation_code=code)
            return True, code
        else:
            if response:
                print(f"\nConfirmation failed. Expected '{code}', got '{response}'",
                      file=sys.stderr)
            else:
                print("\nCancelled.", file=sys.stderr)
            _log_send_attempt(subject, recipient_count, confirmed=False,
                              confirmation_code=code)
            return False, None

    # Terminal-based confirmation
    print(f"\n{'='*60}", file=sys.stderr)
    print("  SENDING EMAIL VIA BSA INTERNET ADVANCEMENT", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"\n{impact}", file=sys.stderr)
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"To proceed, type exactly: {code}", file=sys.stderr)
    print(f"(or press Enter to cancel)", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    try:
        response = input("Confirmation: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.", file=sys.stderr)
        _log_send_attempt(subject, recipient_count, confirmed=False,
                          confirmation_code=code)
        return False, None

    if response == code:
        _log_send_attempt(subject, recipient_count, confirmed=True,
                          confirmation_code=code)
        return True, code
    else:
        if response:
            print(f"\nConfirmation failed. Expected '{code}', got '{response}'",
                  file=sys.stderr)
        else:
            print("\nCancelled.", file=sys.stderr)
        _log_send_attempt(subject, recipient_count, confirmed=False,
                          confirmation_code=code)
        return False, None


def _log_send_attempt(
    subject: str,
    recipient_count: int,
    confirmed: bool,
    confirmation_code: Optional[str],
    user: Optional[str] = None,
) -> None:
    """
    Log message send attempt to audit file.

    Creates an audit trail of all send attempts (both confirmed and cancelled).
    """
    try:
        audit_dir = os.path.expanduser("~/.scouts-cli/audit")
        os.makedirs(audit_dir, exist_ok=True)

        audit_file = os.path.join(audit_dir, f"audit-{datetime.now():%Y-%m}.jsonl")

        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "operation": "send-message",
            "subject": subject,
            "recipient_count": recipient_count,
            "confirmed": confirmed,
            "confirmation_code": confirmation_code,
            "user": user or os.environ.get("USER", "unknown"),
        }

        with open(audit_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
