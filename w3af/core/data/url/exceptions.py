from w3af.core.exceptions import BaseFrameworkException


class HTTPRequestException(BaseFrameworkException):
    """Raised when one HTTP request fails."""

    def __init__(self, message, request=None):
        super().__init__(message)
        self.request = request

    def get_url(self):
        if self.request is None:
            return None

        return self.request.get_full_url()


class ConnectionPoolException(HTTPRequestException):
    """Raised when a connection cannot be obtained from the pool."""
