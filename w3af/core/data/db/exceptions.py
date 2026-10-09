from w3af.core.exceptions import BaseFrameworkException


class DBException(BaseFrameworkException):
    """Base exception for database operations."""


class NoSuchTableException(DBException):
    """Raised when a query references a missing table."""


class MalformedDBException(DBException):
    """Raised when a database file cannot be read as a valid database."""
