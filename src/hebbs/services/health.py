"""Async wrapper for the HEBBS HealthService gRPC method."""

from __future__ import annotations

from hebbs._generated import hebbs_pb2, hebbs_pb2_grpc
from hebbs.exceptions import _map_grpc_error
from hebbs.types import HealthStatus


class HealthServiceClient:
    """Async client for the HEBBS HealthService."""

    def __init__(self, stub: hebbs_pb2_grpc.HealthServiceStub) -> None:
        self._stub = stub

    async def check(self) -> HealthStatus:
        try:
            resp = await self._stub.Check(hebbs_pb2.HealthCheckRequest())
        except Exception as e:
            raise _map_grpc_error(e) from e

        return HealthStatus(
            serving=(resp.status == hebbs_pb2.HealthCheckResponse.SERVING),
            version=resp.version,
            memory_count=resp.memory_count,
            uptime_seconds=resp.uptime_seconds,
        )
