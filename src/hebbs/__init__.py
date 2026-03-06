"""HEBBS Python SDK -- async gRPC client for the HEBBS cognitive memory engine."""

from hebbs.client import HebbsClient
from hebbs.types import (
    Edge,
    EdgeType,
    ForgetResult,
    HealthStatus,
    Memory,
    MemoryKind,
    PrimeOutput,
    RecallOutput,
    RecallResult,
    RecallStrategy,
    ReflectResult,
    StrategyDetail,
    StrategyError,
    SubscribePush,
)
from hebbs.exceptions import (
    HebbsAuthenticationError,
    HebbsConnectionError,
    HebbsError,
    HebbsInternalError,
    HebbsInvalidArgumentError,
    HebbsNotFoundError,
    HebbsPermissionDeniedError,
    HebbsTimeoutError,
    HebbsUnavailableError,
)

__all__ = [
    "HebbsClient",
    "Memory",
    "MemoryKind",
    "Edge",
    "EdgeType",
    "RecallStrategy",
    "RecallResult",
    "RecallOutput",
    "StrategyDetail",
    "StrategyError",
    "PrimeOutput",
    "ForgetResult",
    "ReflectResult",
    "SubscribePush",
    "HealthStatus",
    "HebbsError",
    "HebbsAuthenticationError",
    "HebbsConnectionError",
    "HebbsPermissionDeniedError",
    "HebbsTimeoutError",
    "HebbsNotFoundError",
    "HebbsUnavailableError",
    "HebbsInvalidArgumentError",
    "HebbsInternalError",
]

__version__ = "0.1.0"
