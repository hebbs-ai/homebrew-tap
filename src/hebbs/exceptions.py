"""HEBBS SDK exception hierarchy, mapped from gRPC status codes."""

from __future__ import annotations


class HebbsError(Exception):
    """Base exception for all HEBBS SDK errors."""


class HebbsConnectionError(HebbsError):
    """Failed to connect to the HEBBS server."""


class HebbsTimeoutError(HebbsError):
    """The operation exceeded the deadline."""


class HebbsNotFoundError(HebbsError):
    """The requested resource (memory, subscription, etc.) was not found."""


class HebbsUnavailableError(HebbsError):
    """The HEBBS server is temporarily unavailable."""


class HebbsInvalidArgumentError(HebbsError):
    """The request contained invalid arguments."""


class HebbsInternalError(HebbsError):
    """An internal server error occurred."""


class HebbsAuthenticationError(HebbsError):
    """Authentication failed (missing or invalid API key)."""


class HebbsPermissionDeniedError(HebbsError):
    """The API key does not have the required permissions."""


def _map_grpc_error(grpc_error: Exception) -> HebbsError:
    """Convert a grpc.RpcError into the appropriate HebbsError subclass."""
    import grpc

    if not isinstance(grpc_error, grpc.RpcError):
        return HebbsError(str(grpc_error))

    code = grpc_error.code()
    details = grpc_error.details() or str(grpc_error)

    mapping = {
        grpc.StatusCode.UNAVAILABLE: HebbsUnavailableError,
        grpc.StatusCode.DEADLINE_EXCEEDED: HebbsTimeoutError,
        grpc.StatusCode.NOT_FOUND: HebbsNotFoundError,
        grpc.StatusCode.INVALID_ARGUMENT: HebbsInvalidArgumentError,
        grpc.StatusCode.INTERNAL: HebbsInternalError,
        grpc.StatusCode.UNAUTHENTICATED: HebbsAuthenticationError,
        grpc.StatusCode.PERMISSION_DENIED: HebbsPermissionDeniedError,
    }

    cls = mapping.get(code, HebbsError)
    return cls(details)
