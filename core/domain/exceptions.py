class DomainException(Exception):
    """Base class for domain exceptions."""


class NotificationError(DomainException):
    """Raised when a notification fails to send."""


class ConnectionError(DomainException):
    """Raised when the connection to an external service fails."""
