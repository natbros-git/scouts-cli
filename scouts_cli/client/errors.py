"""Custom exception classes for Scouts CLI."""


class ScoutingError(Exception):
    """Base exception for all Scouts CLI errors."""

    def __init__(self, message, suggestion=None, **kwargs):
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion
        self.metadata = kwargs

    def to_dict(self):
        """Convert error to dictionary for JSON output."""
        result = {
            'error': self.__class__.__name__,
            'message': self.message
        }
        if self.suggestion:
            result['suggestion'] = self.suggestion
        result.update(self.metadata)
        return result


class AuthenticationError(ScoutingError):
    """Authentication failed (401) or token expired/missing."""

    def __init__(self, message='Authentication failed'):
        super().__init__(
            message=message,
            suggestion="Run 'scouts auth login' to authenticate via browser, "
                       "or 'scouts auth login --token <TOKEN>' for manual token auth."
        )


class AuthorizationError(ScoutingError):
    """Authorization failed (403)."""

    def __init__(self, message='Access denied', resource=None, **kwargs):
        super().__init__(
            message=message,
            suggestion="Check that you have the correct role (Den Leader, Scout Master, etc.) "
                       "for this unit.",
            resource=resource,
            **kwargs
        )


class NotFoundError(ScoutingError):
    """Resource not found (404)."""

    def __init__(self, message='Resource not found', resource=None):
        super().__init__(
            message=message,
            suggestion="Check the ID and try again. Use 'scouts rank list' to see valid IDs.",
            resource=resource
        )


class ValidationError(ScoutingError):
    """Invalid request data (400)."""

    def __init__(self, message='Invalid request', field=None, value=None):
        super().__init__(
            message=message,
            field=field,
            value=value
        )


class RateLimitError(ScoutingError):
    """Rate limit exceeded (429)."""

    def __init__(self, message='Rate limit exceeded', retry_after=None):
        super().__init__(
            message=message,
            suggestion=f"Wait {retry_after} seconds before retrying" if retry_after else "Wait before retrying",
            retry_after=retry_after
        )


class BrowserAuthError(ScoutingError):
    """Browser-based authentication failed."""

    def __init__(self, message='Browser authentication failed', suggestion=None):
        super().__init__(
            message=message,
            suggestion=suggestion or (
                "Try again, or use manual token auth: scouts auth login --token <JWT>"
            )
        )
