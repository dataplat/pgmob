"""Errors raised by the adapters"""


class AdapterError(Exception):
    """Generic adapter exception"""

    pass


class ProgrammingError(AdapterError):
    """Programming adapter exception raised by the provider"""

    pass


class NoResultsToFetch(AdapterError):
    """Raised when query did not return any results"""

    pass
