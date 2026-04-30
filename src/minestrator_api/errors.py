class MinestratorError(RuntimeError):
    """Base error raised by this library."""


class MinestratorApiError(MinestratorError):
    """Raised when an API request or API payload is invalid."""


class MinestratorNetworkError(MinestratorApiError):
    """Raised when an HTTP network error occurs."""


class MinestratorProtocolError(MinestratorApiError):
    """Raised when the API response does not match the expected format."""


class MinestratorDependencyError(MinestratorError):
    """Raised when an optional dependency is missing."""


class MinestratorWebSocketError(MinestratorError):
    """Raised when websocket setup or processing fails."""
