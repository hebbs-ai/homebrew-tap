"""Async wrapper for the HEBBS SubscribeService gRPC methods."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from hebbs._generated import hebbs_pb2, hebbs_pb2_grpc
from hebbs.exceptions import _map_grpc_error
from hebbs.services.memory import _proto_to_memory
from hebbs.types import SubscribePush


class Subscription:
    """Handle for an active HEBBS subscription stream.

    Use as an async iterator to receive pushes, and call feed() to send text.
    """

    def __init__(
        self,
        subscription_id: int,
        stream: AsyncIterator,
        feed_stub: hebbs_pb2_grpc.SubscribeServiceStub,
        tenant_id: str | None = None,
        grpc_call: Any = None,
    ) -> None:
        self._subscription_id = subscription_id
        self._stream = stream
        self._feed_stub = feed_stub
        self._tenant_id = tenant_id
        self._grpc_call = grpc_call

    @property
    def subscription_id(self) -> int:
        return self._subscription_id

    async def feed(self, text: str) -> None:
        req = hebbs_pb2.FeedRequest(
            subscription_id=self._subscription_id,
            text=text,
        )
        if self._tenant_id:
            req.tenant_id = self._tenant_id
        try:
            await self._feed_stub.Feed(req)
        except Exception as e:
            raise _map_grpc_error(e) from e

    async def close(self) -> None:
        req = hebbs_pb2.CloseSubscriptionRequest(
            subscription_id=self._subscription_id,
        )
        if self._tenant_id:
            req.tenant_id = self._tenant_id
        try:
            await self._feed_stub.CloseSubscription(req)
        except Exception:
            pass
        if self._grpc_call is not None and hasattr(self._grpc_call, "cancel"):
            self._grpc_call.cancel()

    async def listen(self, timeout: float = 5.0, max_pushes: int | None = None) -> list[SubscribePush]:
        """Collect pushes for up to ``timeout`` seconds.

        Returns as soon as the stream ends, the timeout expires, or
        ``max_pushes`` have been collected (whichever comes first).
        """
        pushes: list[SubscribePush] = []
        deadline = asyncio.get_event_loop().time() + timeout
        while max_pushes is None or len(pushes) < max_pushes:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                push = await asyncio.wait_for(self.__anext__(), timeout=remaining)
                pushes.append(push)
            except asyncio.TimeoutError:
                break
            except StopAsyncIteration:
                break
        return pushes

    def __aiter__(self) -> AsyncIterator[SubscribePush]:
        return self

    async def __anext__(self) -> SubscribePush:
        try:
            msg = await self._stream.__anext__()
        except StopAsyncIteration:
            raise
        except Exception as e:
            raise _map_grpc_error(e) from e
        return SubscribePush(
            subscription_id=msg.subscription_id,
            memory=_proto_to_memory(msg.memory),
            confidence=msg.confidence,
            push_timestamp_us=msg.push_timestamp_us,
            sequence_number=msg.sequence_number,
        )


class SubscribeServiceClient:
    """Async client for the HEBBS SubscribeService."""

    def __init__(self, stub: hebbs_pb2_grpc.SubscribeServiceStub, tenant_id: str | None = None) -> None:
        self._stub = stub
        self._tenant_id = tenant_id

    async def subscribe(
        self,
        entity_id: str | None = None,
        confidence_threshold: float = 0.5,
    ) -> Subscription:
        req = hebbs_pb2.SubscribeRequest(confidence_threshold=confidence_threshold)
        if entity_id:
            req.entity_id = entity_id
        if self._tenant_id:
            req.tenant_id = self._tenant_id

        try:
            grpc_call = self._stub.Subscribe(req)
            stream_iter = grpc_call.__aiter__()
            handshake = await stream_iter.__anext__()
        except Exception as e:
            raise _map_grpc_error(e) from e

        sub_id = handshake.subscription_id

        async def _data_stream():
            async for msg in stream_iter:
                if msg.HasField("memory"):
                    yield msg

        return Subscription(
            subscription_id=sub_id,
            stream=_data_stream(),
            feed_stub=self._stub,
            tenant_id=self._tenant_id,
            grpc_call=grpc_call,
        )
