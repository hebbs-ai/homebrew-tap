"""Async wrapper for the HEBBS ReflectService gRPC methods."""

from __future__ import annotations

from hebbs._generated import hebbs_pb2, hebbs_pb2_grpc
from hebbs.exceptions import _map_grpc_error
from hebbs.services.memory import _proto_to_memory
from hebbs.types import Memory, ReflectResult


class ReflectServiceClient:
    """Async client for the HEBBS ReflectService."""

    def __init__(self, stub: hebbs_pb2_grpc.ReflectServiceStub, tenant_id: str | None = None) -> None:
        self._stub = stub
        self._tenant_id = tenant_id

    async def reflect(self, entity_id: str | None = None) -> ReflectResult:
        scope = hebbs_pb2.ReflectScope()
        if entity_id:
            scope.entity.CopyFrom(hebbs_pb2.EntityScope(entity_id=entity_id))
        else:
            getattr(scope, "global").CopyFrom(hebbs_pb2.GlobalScope())

        req = hebbs_pb2.ReflectRequest(scope=scope)
        if self._tenant_id:
            req.tenant_id = self._tenant_id

        try:
            resp = await self._stub.Reflect(req)
        except Exception as e:
            raise _map_grpc_error(e) from e

        return ReflectResult(
            insights_created=resp.insights_created,
            clusters_found=resp.clusters_found,
            clusters_processed=resp.clusters_processed,
            memories_processed=resp.memories_processed,
        )

    async def get_insights(
        self,
        entity_id: str | None = None,
        max_results: int | None = None,
    ) -> list[Memory]:
        req = hebbs_pb2.GetInsightsRequest()
        if entity_id:
            req.entity_id = entity_id
        if max_results is not None:
            req.max_results = max_results
        if self._tenant_id:
            req.tenant_id = self._tenant_id

        try:
            resp = await self._stub.GetInsights(req)
        except Exception as e:
            raise _map_grpc_error(e) from e

        return [_proto_to_memory(m) for m in resp.insights]
