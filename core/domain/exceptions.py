class DomainException(Exception):
    """Base class for domain exceptions."""

    pass


class NotificationError(DomainException):
    """Raised when a notification fails to send."""

    pass


class ConnectionError(DomainException):
    """Raised when the connection to an external service fails."""

    pass
