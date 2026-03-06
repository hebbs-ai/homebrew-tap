"""HebbsClient: async gRPC client for the HEBBS memory engine.

Usage::

    async with HebbsClient("localhost:6380", api_key="hb_...") as h:
        mem = await h.remember("Acme Corp uses Salesforce", importance=0.8)
        results = await h.recall("What CRM does Acme use?")
"""

from __future__ import annotations

import os
from typing import Any

import grpc
import grpc.aio

from hebbs._generated import hebbs_pb2_grpc
from hebbs.exceptions import HebbsConnectionError
from hebbs.services.health import HealthServiceClient
from hebbs.services.memory import MemoryServiceClient
from hebbs.services.reflect import ReflectServiceClient
from hebbs.services.subscribe import SubscribeServiceClient, Subscription
from hebbs.types import (
    Edge,
    ForgetResult,
    HealthStatus,
    Memory,
    PrimeOutput,
    RecallOutput,
    ReflectResult,
)


class _AuthMetadataInterceptor(
    grpc.aio.UnaryUnaryClientInterceptor,
    grpc.aio.UnaryStreamClientInterceptor,
):
    """Injects ``authorization: Bearer <key>`` metadata into every gRPC call."""

    def __init__(self, api_key: str) -> None:
        self._metadata = [("authorization", f"Bearer {api_key}")]

    def _inject(self, client_call_details: grpc.aio.ClientCallDetails) -> _CallDetails:
        metadata = list(client_call_details.metadata or [])
        metadata.extend(self._metadata)
        return _CallDetails(
            method=client_call_details.method,
            timeout=client_call_details.timeout,
            metadata=metadata,
            credentials=client_call_details.credentials,
            wait_for_ready=client_call_details.wait_for_ready,
        )

    async def intercept_unary_unary(self, continuation, client_call_details, request):
        return await continuation(self._inject(client_call_details), request)

    async def intercept_unary_stream(self, continuation, client_call_details, request):
        return await continuation(self._inject(client_call_details), request)


class _CallDetails(grpc.aio.ClientCallDetails):
    """Concrete ``ClientCallDetails`` with writable attributes."""

    def __init__(self, method, timeout, metadata, credentials, wait_for_ready):
        self.method = method
        self.timeout = timeout
        self.metadata = metadata
        self.credentials = credentials
        self.wait_for_ready = wait_for_ready


class HebbsClient:
    """Async client for the HEBBS cognitive memory engine.

    Connects to a running HEBBS gRPC server and exposes all operations
    as async methods with Pythonic types (no protobuf in the public API).

    Args:
        address: Server gRPC endpoint (default ``localhost:6380``).
        api_key: API key for authentication (``hb_...``). Falls back to
            the ``HEBBS_API_KEY`` environment variable if not provided.
        tenant_id: Explicit tenant ID (normally derived from the API key).
        channel_options: Additional gRPC channel options.
    """

    def __init__(
        self,
        address: str = "localhost:6380",
        *,
        api_key: str | None = None,
        tenant_id: str | None = None,
        channel_options: list[tuple[str, Any]] | None = None,
    ) -> None:
        self._address = address
        self._api_key = api_key or os.environ.get("HEBBS_API_KEY")
        self._tenant_id = tenant_id
        self._channel_options = channel_options or []
        self._channel: grpc.aio.Channel | None = None
        self._memory: MemoryServiceClient | None = None
        self._subscribe: SubscribeServiceClient | None = None
        self._reflect: ReflectServiceClient | None = None
        self._health: HealthServiceClient | None = None

    def _ensure_connected(self) -> None:
        if self._channel is None:
            raise HebbsConnectionError(
                "Not connected. Use 'async with HebbsClient(...) as h:' or call connect()."
            )

    async def connect(self) -> HebbsClient:
        """Open the gRPC channel and create service stubs."""
        interceptors = []
        if self._api_key:
            interceptors.append(_AuthMetadataInterceptor(self._api_key))

        self._channel = grpc.aio.insecure_channel(
            self._address,
            options=self._channel_options,
            interceptors=interceptors or None,
        )
        mem_stub = hebbs_pb2_grpc.MemoryServiceStub(self._channel)
        sub_stub = hebbs_pb2_grpc.SubscribeServiceStub(self._channel)
        ref_stub = hebbs_pb2_grpc.ReflectServiceStub(self._channel)
        hlt_stub = hebbs_pb2_grpc.HealthServiceStub(self._channel)

        self._memory = MemoryServiceClient(mem_stub, self._tenant_id)
        self._subscribe = SubscribeServiceClient(sub_stub, self._tenant_id)
        self._reflect = ReflectServiceClient(ref_stub, self._tenant_id)
        self._health = HealthServiceClient(hlt_stub)
        return self

    async def close(self) -> None:
        """Close the gRPC channel."""
        if self._channel is not None:
            await self._channel.close()
            self._channel = None

    async def __aenter__(self) -> HebbsClient:
        return await self.connect()

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ── MemoryService ────────────────────────────────────────────────────

    async def remember(
        self,
        content: str,
        importance: float | None = None,
        context: dict[str, Any] | None = None,
        entity_id: str | None = None,
        edges: list[Edge] | None = None,
    ) -> Memory:
        """Store a memory in HEBBS."""
        self._ensure_connected()
        assert self._memory is not None
        return await self._memory.remember(content, importance, context, entity_id, edges)

    async def get(self, memory_id: bytes) -> Memory:
        """Retrieve a single memory by ID."""
        self._ensure_connected()
        assert self._memory is not None
        return await self._memory.get(memory_id)

    async def recall(
        self,
        cue: str,
        strategies: list[str] | None = None,
        top_k: int | None = None,
        entity_id: str | None = None,
    ) -> RecallOutput:
        """Recall memories matching a cue using one or more strategies."""
        self._ensure_connected()
        assert self._memory is not None
        return await self._memory.recall(cue, strategies, top_k, entity_id)

    async def prime(
        self,
        entity_id: str,
        max_memories: int | None = None,
        similarity_cue: str | None = None,
    ) -> PrimeOutput:
        """Prime a session: load relevant memories for an entity."""
        self._ensure_connected()
        assert self._memory is not None
        return await self._memory.prime(entity_id, max_memories, similarity_cue)

    async def revise(
        self,
        memory_id: bytes,
        content: str | None = None,
        importance: float | None = None,
        context: dict[str, Any] | None = None,
        entity_id: str | None = None,
    ) -> Memory:
        """Revise an existing memory."""
        self._ensure_connected()
        assert self._memory is not None
        return await self._memory.revise(memory_id, content, importance, context, entity_id)

    async def forget(
        self,
        entity_id: str | None = None,
        memory_ids: list[bytes] | None = None,
    ) -> ForgetResult:
        """Forget memories by entity or specific IDs (GDPR-compliant erasure)."""
        self._ensure_connected()
        assert self._memory is not None
        return await self._memory.forget(entity_id, memory_ids)

    async def set_policy(
        self,
        max_snapshots_per_memory: int | None = None,
        auto_forget_threshold: float | None = None,
        decay_half_life_days: float | None = None,
    ) -> bool:
        """Set tenant policy parameters."""
        self._ensure_connected()
        assert self._memory is not None
        return await self._memory.set_policy(
            max_snapshots_per_memory, auto_forget_threshold, decay_half_life_days,
        )

    # ── SubscribeService ─────────────────────────────────────────────────

    async def subscribe(
        self,
        entity_id: str | None = None,
        confidence_threshold: float = 0.5,
    ) -> Subscription:
        """Open a real-time subscription for memory surfacing."""
        self._ensure_connected()
        assert self._subscribe is not None
        return await self._subscribe.subscribe(entity_id, confidence_threshold)

    # ── ReflectService ───────────────────────────────────────────────────

    async def reflect(self, entity_id: str | None = None) -> ReflectResult:
        """Trigger the reflect pipeline to generate insights from memory clusters."""
        self._ensure_connected()
        assert self._reflect is not None
        return await self._reflect.reflect(entity_id)

    async def insights(
        self,
        entity_id: str | None = None,
        max_results: int | None = None,
    ) -> list[Memory]:
        """Retrieve accumulated insights."""
        self._ensure_connected()
        assert self._reflect is not None
        return await self._reflect.get_insights(entity_id, max_results)

    # ── HealthService ────────────────────────────────────────────────────

    async def health(self) -> HealthStatus:
        """Check server health, version, and memory count."""
        self._ensure_connected()
        assert self._health is not None
        return await self._health.check()

    async def count(self) -> int:
        """Return the total memory count (via health check)."""
        status = await self.health()
        return status.memory_count
