"""Browser-based authentication for Scouts CLI.

Uses Playwright to automate JWT token retrieval from advancements.scouting.org.
Maintains a persistent browser profile so Google OAuth session cookies survive
between runs -- after the first login, subsequent token refreshes are automatic.

Requires: pip install playwright
Uses system Chrome (channel='chrome'), not Playwright's bundled Chromium.
"""

import json
import sys
import time

from ..config import (
    WEB_BASE_URL,
    BROWSER_PROFILE_DIR,
    BROWSER_HEADLESS_TIMEOUT,
    BROWSER_HEADED_TIMEOUT,
    BROWSER_POLL_INTERVAL,
)
from .errors import BrowserAuthError


def _check_playwright_available():
    """Verify Playwright is installed and importable.

    Returns:
        The sync_playwright context manager

    Raises:
        BrowserAuthError: If Playwright is not installed
    """
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        raise BrowserAuthError(
            "Playwright is not installed. Browser-based login requires it.",
            suggestion=(
                "Install with: pip install playwright\n"
                "Or use manual token auth: scouts auth login --token <JWT>"
            )
        )


def _extract_token_from_page(page) -> str | None:
    """Read LOGIN_DATA from localStorage and return the JWT token, or None."""
    try:
        raw = page.evaluate("() => localStorage.getItem('LOGIN_DATA')")
        if not raw:
            return None
        data = json.loads(raw)
        token = data.get('token')
        if token and token.startswith('eyJ'):
            return token
        return None
    except Exception:
        return None


def _poll_for_token(page, timeout_seconds: int, poll_interval: float) -> str | None:
    """Poll localStorage until token appears or timeout is reached.

    Args:
        page: Playwright page object
        timeout_seconds: Max seconds to wait
        poll_interval: Seconds between polls

    Returns:
        JWT token string, or None if timeout
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        token = _extract_token_from_page(page)
        if token:
            return token
        time.sleep(poll_interval)
    return None


def acquire_token_via_browser(verbose: bool = False) -> str:
    """Acquire JWT token by navigating to advancements.scouting.org.

    Two-phase strategy:
    1. Headless attempt with persistent context (fast, silent, works if cookies warm)
    2. Headed fallback for user to complete Google OAuth login

    Args:
        verbose: If True, print progress to stderr

    Returns:
        JWT token string

    Raises:
        BrowserAuthError: If token cannot be obtained
    """
    sync_playwright = _check_playwright_available()

    # Phase 1: Headless attempt (warm cookies)
    if verbose:
        print("Attempting headless token refresh...", file=sys.stderr)

    token = _try_acquire(sync_playwright, headless=True,
                         timeout=BROWSER_HEADLESS_TIMEOUT, verbose=verbose)
    if token:
        if verbose:
            print("Token obtained via headless refresh.", file=sys.stderr)
        return token

    # Phase 2: Headed attempt (needs human interaction)
    print(
        "Opening browser for BSA login. Please sign in...",
        file=sys.stderr
    )

    token = _try_acquire(sync_playwright, headless=False,
                         timeout=BROWSER_HEADED_TIMEOUT, verbose=verbose)
    if token:
        print("Login successful. Token captured.", file=sys.stderr)
        return token

    raise BrowserAuthError(
        f"Timed out waiting for login ({BROWSER_HEADED_TIMEOUT}s). "
        "Please try again or use: scouts auth login --token <JWT>"
    )


def _try_acquire(sync_playwright, headless: bool, timeout: int,
                 verbose: bool = False) -> str | None:
    """Attempt to acquire token with a single browser launch.

    Args:
        sync_playwright: The sync_playwright context manager
        headless: Whether to run headless
        timeout: Seconds to wait for token
        verbose: Print progress to stderr

    Returns:
        JWT token string, or None if not found within timeout
    """
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_PROFILE_DIR,
            channel='chrome',
            headless=headless,
            args=['--disable-blink-features=AutomationControlled'],
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()

            if verbose:
                mode = "headless" if headless else "headed"
                print(f"  Navigating to {WEB_BASE_URL} ({mode})...",
                      file=sys.stderr)

            page.goto(WEB_BASE_URL, wait_until='networkidle', timeout=30000)

            # Check immediately before polling (token may already be there)
            token = _extract_token_from_page(page)
            if token:
                return token

            return _poll_for_token(page, timeout, BROWSER_POLL_INTERVAL)
        except Exception as e:
            if verbose:
                print(f"  Browser error: {e}", file=sys.stderr)
            return None
        finally:
            context.close()
