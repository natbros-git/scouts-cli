"""Authentication management for Scouts CLI.

Handles JWT token storage, retrieval, and validation.
"""

import os
import json
import base64
import sys
from datetime import datetime, timezone

from ..config import TOKEN_DIR, TOKEN_FILE
from .errors import AuthenticationError


class ScoutingAuth:
    """Manages JWT authentication tokens for the BSA API."""

    def get_token(self) -> str:
        """Get a valid JWT token.

        If no valid cached token exists and browser auth is not disabled,
        attempts to acquire a token via Playwright browser automation.

        Returns:
            JWT token string

        Raises:
            AuthenticationError: If no token can be obtained
        """
        cached = self._load_cached_token()
        if cached and not self._is_expired(cached):
            return cached["token"]

        # No valid token — try browser auth (unless disabled)
        no_browser = os.environ.get(
            'SCOUTS_NO_BROWSER', ''
        ).lower() in ('1', 'true', 'yes')

        if not no_browser:
            try:
                from .browser_auth import acquire_token_via_browser
                token = acquire_token_via_browser()
                self.login_with_token(token)
                return token
            except Exception:
                pass  # Fall through to manual error

        if cached and self._is_expired(cached):
            raise AuthenticationError(
                f"Token expired at {cached.get('expires_at', 'unknown')}."
            )
        raise AuthenticationError("No authentication token found.")

    def get_token_info(self) -> dict:
        """Get cached token metadata (for 'auth status' command).

        Returns:
            Token metadata dict or empty dict if no token
        """
        cached = self._load_cached_token()
        if not cached:
            return {}

        cached["is_expired"] = self._is_expired(cached)
        return cached

    def login_with_token(self, token: str):
        """Store a manually provided JWT token.

        Args:
            token: JWT token string (starts with 'eyJ')

        Raises:
            AuthenticationError: If token is not a valid JWT
        """
        if not token.startswith("eyJ"):
            raise AuthenticationError(
                "Invalid token format. JWT tokens start with 'eyJ'. "
                "Make sure you copied the full token from LOGIN_DATA."
            )

        claims = self._decode_jwt_claims(token)

        exp = claims.get("exp")
        if not exp:
            raise AuthenticationError("Token has no expiration claim.")

        token_data = {
            "token": token,
            "obtained_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": datetime.fromtimestamp(exp, tz=timezone.utc).isoformat(),
            "user": claims.get("user", "unknown"),
            "uid": claims.get("uid"),
            "mid": claims.get("mid"),
            "pgu": claims.get("pgu"),
            "scope": claims.get("scope", []),
        }

        os.makedirs(TOKEN_DIR, exist_ok=True)
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f, indent=2)
        # Restrict token file permissions (Unix only; Windows os.chmod
        # only controls the read-only flag, not per-user access)
        if sys.platform != 'win32':
            os.chmod(TOKEN_FILE, 0o600)

    def login_with_browser(self, verbose: bool = False) -> dict:
        """Authenticate by opening browser to advancements.scouting.org.

        Uses Playwright with persistent Chrome context to capture the JWT
        from localStorage after the user completes Google OAuth sign-in.

        Args:
            verbose: Print progress to stderr

        Returns:
            Token metadata dict (same format as get_token_info())

        Raises:
            BrowserAuthError: If browser auth fails
        """
        from .browser_auth import acquire_token_via_browser
        token = acquire_token_via_browser(verbose=verbose)
        self.login_with_token(token)
        return self.get_token_info()

    def logout(self):
        """Remove cached token."""
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)

    def _load_cached_token(self) -> dict:
        """Load token from cache file."""
        if not os.path.exists(TOKEN_FILE):
            return {}

        try:
            with open(TOKEN_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _is_expired(self, token_data: dict) -> bool:
        """Check if cached token is expired."""
        expires_at = token_data.get("expires_at")
        if not expires_at:
            return True

        try:
            exp_dt = datetime.fromisoformat(expires_at)
            return datetime.now(timezone.utc) >= exp_dt
        except ValueError:
            return True

    @staticmethod
    def _decode_jwt_claims(token: str) -> dict:
        """Decode JWT payload without verification.

        Args:
            token: JWT token string

        Returns:
            Decoded claims dictionary
        """
        try:
            parts = token.split('.')
            if len(parts) != 3:
                raise AuthenticationError("Invalid JWT format (expected 3 parts).")

            payload = parts[1]
            # Add padding
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding

            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded)
        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            raise AuthenticationError(f"Failed to decode JWT token: {e}")
