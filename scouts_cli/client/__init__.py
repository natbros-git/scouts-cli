"""Client package for Scouts CLI."""

from .scouting_client import ScoutingClient
from .errors import (
    ScoutingError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    BrowserAuthError,
)

__all__ = [
    "ScoutingClient",
    "ScoutingError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ValidationError",
    "RateLimitError",
    "BrowserAuthError",
]
