"""SalesAgent: the core conversation loop with full HEBBS integration.

Ties together:
  - LLM conversation generation
  - Memory extraction and storage
  - Multi-strategy recall for context building
  - Subscribe for real-time memory surfacing
  - Prime for session initialization
  - Reflect for institutional learning
  - Display manager for observability

All HEBBS operations are async, going through the gRPC SDK.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from demo.config import DemoConfig
from demo.display import DisplayManager, OperationRecord, TimedOperation, Verbosity
from demo.llm_client import LlmClient, MockLlmClient
from demo.memory_manager import MemoryManager
from demo.prompts import conversation_prompt

logger = logging.getLogger(__name__)


@dataclass
class TurnResult:
    """Result of a single conversation turn."""
    prospect_message: str
    agent_response: str
    memories_created: int
    memories_recalled: int
    subscribe_pushes: int
    turn_latency_ms: float


@dataclass
class HebbsSessionStats:
    """Accumulated HEBBS operation stats for the current session."""
    turns: int = 0
    memories_created: int = 0
    memories_recalled: int = 0
    primed_memories: int = 0
    subscribe_pushes: int = 0
    reflect_runs: int = 0
    forget_runs: int = 0
    recall_calls: int = 0
    remember_calls: int = 0


@dataclass
class SessionResult:
    """Result of a complete conversation session."""
    entity_id: str
    turns: list[TurnResult] = field(default_factory=list)
    primed_memories: int = 0
    total_memories_created: int = 0
    total_memories_recalled: int = 0
    total_subscribe_pushes: int = 0


class SalesAgent:
    """AI Sales Intelligence Agent powered by HEBBS (gRPC client)."""

    def __init__(
        self,
        config: DemoConfig,
        hebbs: Any,
        llm_client: LlmClient | None = None,
        display: DisplayManager | None = None,
        use_mock_llm: bool = False,
    ) -> None:
        self._config = config
        self._hebbs = hebbs
        self._display = display or DisplayManager()

        if use_mock_llm:
            self._llm = MockLlmClient(config)
        else:
            self._llm = llm_client or LlmClient(config)

        self._memory_mgr = MemoryManager(hebbs, self._llm, self._display)
        self._session_history: list[dict[str, str]] = []
        self._current_entity: str | None = None
        self._subscription: Any = None
        self._pending_extractions: list[asyncio.Task[list[Any]]] = []
        self._hebbs_stats = HebbsSessionStats()

    @property
    def llm_client(self) -> LlmClient:
        return self._llm

    @property
    def memory_manager(self) -> MemoryManager:
        return self._memory_mgr

    @property
    def hebbs(self) -> Any:
        return self._hebbs

    @property
    def hebbs_stats(self) -> HebbsSessionStats:
        return self._hebbs_stats

    async def start_session(
        self,
        entity_id: str,
        session_num: int | None = None,
        use_subscribe: bool = False,
        similarity_cue: str | None = None,
    ) -> str:
        """Initialize a new conversation session with an entity."""
        self._current_entity = entity_id
        self._session_history = []
        self._display.display_session_header(entity_id, session_num)

        context, primed = await self._memory_mgr.prime_session(
            entity_id=entity_id,
            similarity_cue=similarity_cue,
        )
        self._hebbs_stats.primed_memories += len(primed) if primed else 0

        if use_subscribe:
            try:
                self._subscription = await self._hebbs.subscribe(
                    entity_id=entity_id,
                    confidence_threshold=0.5,
                )
            except Exception as e:
                logger.warning("subscribe() failed: %s", e)
                self._subscription = None

        return context

    async def flush_pending(self) -> int:
        """Await all background extraction tasks. Returns total memories stored."""
        if not self._pending_extractions:
            return 0
        results = await asyncio.gather(
            *self._pending_extractions, return_exceptions=True,
        )
        self._pending_extractions.clear()
        total = 0
        for r in results:
            if isinstance(r, list):
                total += len(r)
        self._hebbs_stats.memories_created += total
        self._hebbs_stats.remember_calls += total
        return total

    async def end_session(self) -> None:
        """Clean up the current session."""
        await self.flush_pending()
        if self._subscription is not None:
            try:
                await self._subscription.close()
            except Exception:
                pass
            self._subscription = None
        self._session_history = []
        self._current_entity = None

    async def _fetch_insights(self, entity_id: str | None) -> list[Any]:
        """Fetch insights for an entity, swallowing errors."""
        try:
            return await self._hebbs.insights(entity_id=entity_id, max_results=5)
        except Exception:
            return []

    async def process_turn(
        self,
        prospect_message: str,
        recall_strategies: list[str] | None = None,
    ) -> TurnResult:
        """Process a single conversation turn.

        Flow (optimized for perceived latency):
          1. Flush any pending background extractions from the previous turn
          2. Display prospect message
          3. Feed to subscribe (if active)
          4. Recall memories + fetch insights in parallel
          5. Generate agent response via LLM
          6. Show response immediately
          7. Fire memory extraction as a background task
        """
        await self.flush_pending()

        t0 = time.perf_counter()
        self._display.start_turn()
        entity = self._current_entity

        self._display.display_prospect_message(entity or "Prospect", prospect_message)

        subscribe_pushes: list[Any] = []
        if self._subscription is not None:
            with TimedOperation() as sub_timer:
                try:
                    await self._subscription.feed(prospect_message)
                    await asyncio.sleep(0.05)
                    try:
                        push = await asyncio.wait_for(
                            self._subscription.__anext__(), timeout=0.1,
                        )
                        subscribe_pushes.append(push)
                    except (asyncio.TimeoutError, StopAsyncIteration):
                        pass
                except Exception as e:
                    logger.warning("subscribe feed/poll failed: %s", e)

            if subscribe_pushes:
                details = []
                for p in subscribe_pushes:
                    details.append(
                        f'"{p.memory.content[:55]}" (confidence: {p.confidence:.2f})'
                    )
                record = OperationRecord(
                    operation="SUBSCRIBE",
                    latency_ms=sub_timer.elapsed_ms,
                    summary=f"{len(subscribe_pushes)} memory surfaced (confidence: {subscribe_pushes[0].confidence:.2f})",
                    details=details,
                    highlight_color="yellow",
                )
                self._display.record_operation(record)

        strategies = recall_strategies or ["similarity"]

        (recalled_context, recall_results), insights_list = await asyncio.gather(
            self._memory_mgr.recall_context(
                cue=prospect_message,
                entity_id=entity,
                strategies=strategies,
            ),
            self._fetch_insights(entity),
        )

        subscribe_context = self._memory_mgr.get_subscribe_context(subscribe_pushes)
        full_context = recalled_context
        if subscribe_context:
            full_context += "\n\n--- REAL-TIME SURFACED ---\n" + subscribe_context

        insights_str = ""
        if insights_list:
            insights_str = "\n".join(f"- {ins.content}" for ins in insights_list)

        messages = conversation_prompt(
            prospect_message=prospect_message,
            recalled_context=full_context,
            session_history=self._session_history,
            entity_id=entity,
            insights=insights_str,
        )

        with TimedOperation() as llm_timer:
            llm_resp = await asyncio.to_thread(self._llm.conversation, messages)

        agent_response = llm_resp.content

        llm_details = [
            f"model: {llm_resp.model}  |  provider: {llm_resp.provider}",
            f"tokens: {llm_resp.input_tokens} in / {llm_resp.output_tokens} out",
        ]
        self._display.record_operation(OperationRecord(
            operation="LLM CHAT",
            latency_ms=llm_timer.elapsed_ms,
            summary=f"response generated ({llm_resp.output_tokens} tokens)",
            details=llm_details,
            highlight_color="yellow",
            llm_ms=llm_timer.elapsed_ms,
        ))

        self._session_history.append({"role": "user", "content": prospect_message})
        self._session_history.append({"role": "assistant", "content": agent_response})

        self._display.display_turn()
        self._display.display_agent_response(agent_response)

        task = asyncio.create_task(
            self._memory_mgr.extract_and_remember(
                prospect_message=prospect_message,
                agent_response=agent_response,
                entity_id=entity,
                recalled_context=recalled_context,
                immediate_display=True,
            )
        )
        self._pending_extractions.append(task)

        elapsed_ms = (time.perf_counter() - t0) * 1000

        self._hebbs_stats.turns += 1
        self._hebbs_stats.memories_recalled += len(recall_results)
        self._hebbs_stats.subscribe_pushes += len(subscribe_pushes)
        self._hebbs_stats.recall_calls += 1

        return TurnResult(
            prospect_message=prospect_message,
            agent_response=agent_response,
            memories_created=0,
            memories_recalled=len(recall_results),
            subscribe_pushes=len(subscribe_pushes),
            turn_latency_ms=elapsed_ms,
        )

    async def run_reflect(self, entity_id: str | None = None) -> Any:
        """Trigger the reflect pipeline and display results."""
        with TimedOperation() as timer:
            try:
                result = await self._hebbs.reflect(entity_id=entity_id)
            except Exception as e:
                logger.warning("reflect() failed: %s", e)
                return None

        self._hebbs_stats.reflect_runs += 1
        self._display.display_reflect(
            memories_processed=result.memories_processed,
            clusters_found=result.clusters_found,
            insights_created=result.insights_created,
            latency_ms=timer.elapsed_ms,
        )
        return result

    async def run_forget(self, entity_id: str) -> Any:
        """Forget all memories for an entity and display results."""
        with TimedOperation() as timer:
            try:
                result = await self._hebbs.forget(entity_id=entity_id)
            except Exception as e:
                logger.warning("forget() failed: %s", e)
                return None

        self._hebbs_stats.forget_runs += 1
        self._display.display_forget(
            entity_id=entity_id,
            forgotten_count=result.forgotten_count,
            cascade_count=result.cascade_count,
            tombstone_count=result.tombstone_count,
            latency_ms=timer.elapsed_ms,
        )
        return result
