"""Memory extraction and context building for the sales agent.

Handles:
  - LLM-based structured memory extraction from conversation turns
  - Building recall context strings for the conversation LLM
  - Structured remember() calls with context metadata
  - Retry logic for malformed JSON extraction output

Adapted for the async gRPC SDK (HebbsClient).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from demo.display import DisplayManager, OperationRecord, TimedOperation
from demo.llm_client import LlmClient
from demo.prompts import extraction_prompt

logger = logging.getLogger(__name__)

MAX_EXTRACTION_RETRIES = 2


@dataclass
class ExtractedMemory:
    content: str
    importance: float
    context: dict[str, Any]
    edge_to_previous: bool = False


@dataclass
class ExtractionResult:
    memories: list[ExtractedMemory]
    skip_reason: str | None = None
    raw_response: str = ""
    parse_success: bool = True
    latency_ms: float = 0.0


def parse_extraction_response(raw: str) -> ExtractionResult:
    """Parse the LLM extraction response JSON into structured memories."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                return ExtractionResult(
                    memories=[], raw_response=raw, parse_success=False,
                    skip_reason="Failed to parse LLM output as JSON",
                )
        else:
            return ExtractionResult(
                memories=[], raw_response=raw, parse_success=False,
                skip_reason="No JSON object found in LLM output",
            )

    memories = []
    for mem_raw in data.get("memories", []):
        content = mem_raw.get("content", "").strip()
        if not content:
            continue
        importance = float(mem_raw.get("importance", 0.5))
        importance = max(0.0, min(1.0, importance))
        context = mem_raw.get("context", {})
        if not isinstance(context, dict):
            context = {}
        edge = bool(mem_raw.get("edge_to_previous", False))
        memories.append(ExtractedMemory(
            content=content, importance=importance, context=context, edge_to_previous=edge,
        ))

    return ExtractionResult(
        memories=memories,
        skip_reason=data.get("skip_reason"),
        raw_response=raw,
        parse_success=True,
    )


class MemoryManager:
    """Manages memory extraction and HEBBS integration for the sales agent.

    All HEBBS calls are async, going through the gRPC SDK.
    """

    def __init__(
        self,
        hebbs: Any,
        llm_client: LlmClient,
        display: DisplayManager,
    ) -> None:
        self._hebbs = hebbs
        self._llm = llm_client
        self._display = display
        self._last_memory_id: bytes | None = None
        self.total_remember_ms: float = 0.0
        self.total_recall_ms: float = 0.0
        self.total_prime_ms: float = 0.0
        self.remember_batches: int = 0
        self.recall_batches: int = 0
        self.prime_calls: int = 0

    async def extract_and_remember(
        self,
        prospect_message: str,
        agent_response: str,
        entity_id: str | None = None,
        recalled_context: str = "",
        immediate_display: bool = False,
    ) -> list[Any]:
        """Extract memories from a conversation turn and store them in HEBBS.

        When immediate_display is True, the REMEMBER record is rendered directly
        (used when extraction runs as a background task after the response is
        already displayed).

        Returns the list of Memory objects created.
        """
        extraction = await self._extract(
            prospect_message, agent_response, entity_id, recalled_context,
        )

        if not extraction.memories:
            return []

        stored: list[Any] = []
        with TimedOperation() as timer:
            for extracted in extraction.memories:
                try:
                    mem = await self._hebbs.remember(
                        content=extracted.content,
                        importance=extracted.importance,
                        context=extracted.context,
                        entity_id=entity_id,
                    )
                    stored.append(mem)
                    self._last_memory_id = mem.id
                except Exception as e:
                    logger.warning("remember() failed: %s", e)

        self.total_remember_ms += timer.elapsed_ms
        self.remember_batches += 1

        if stored:
            first = stored[0]
            ctx_parts = []
            if first.context:
                for k, v in list(first.context.items())[:3]:
                    ctx_parts.append(f"{k}={v}")

            details = []
            details.append(
                f"LLM extraction: {extraction.latency_ms:.0f}ms  |  "
                f"HEBBS store: {timer.elapsed_ms:.1f}ms"
            )
            for mem in stored:
                details.append(
                    f'content:  "{mem.content[:60]}..."'
                    if len(mem.content) > 60 else f'content:  "{mem.content}"'
                )
                if mem.context:
                    ctx = ", ".join(f"{k}={v}" for k, v in list(mem.context.items())[:4])
                    details.append(f"context:  {ctx}")

            entity_str = f", entity: {entity_id}" if entity_id else ""
            record = OperationRecord(
                operation="REMEMBER",
                latency_ms=timer.elapsed_ms + extraction.latency_ms,
                summary=f"{len(stored)} memory stored (importance: {first.importance:.1f}{entity_str})",
                details=details,
                highlight_color="green",
                server_ms=timer.elapsed_ms,
                llm_ms=extraction.latency_ms,
            )
            if immediate_display:
                self._display.display_record_immediate(record)
            else:
                self._display.record_operation(record)

        return stored

    async def _extract(
        self,
        prospect_message: str,
        agent_response: str,
        entity_id: str | None = None,
        recalled_context: str = "",
    ) -> ExtractionResult:
        """Call the extraction LLM to extract structured memories.

        Runs the synchronous LLM call in a thread to avoid blocking the event loop.
        """
        messages = extraction_prompt(prospect_message, agent_response, entity_id, recalled_context)

        for attempt in range(MAX_EXTRACTION_RETRIES + 1):
            try:
                llm_resp = await asyncio.to_thread(
                    self._llm.extract_memories, messages,
                )
                result = parse_extraction_response(llm_resp.content)
                result.latency_ms = llm_resp.latency_ms

                if result.parse_success or attempt == MAX_EXTRACTION_RETRIES:
                    return result
                logger.warning("Extraction parse failed (attempt %d), retrying", attempt + 1)
            except Exception as e:
                logger.warning("Extraction LLM call failed (attempt %d): %s", attempt + 1, e)
                if attempt == MAX_EXTRACTION_RETRIES:
                    return ExtractionResult(
                        memories=[], skip_reason=f"LLM call failed: {e}",
                        parse_success=False,
                    )
        return ExtractionResult(memories=[], skip_reason="Exhausted retries")

    async def recall_context(
        self,
        cue: str,
        entity_id: str | None = None,
        strategies: list[str] | None = None,
        top_k: int = 10,
    ) -> tuple[str, list[Any]]:
        """Recall relevant memories and format them as context for the conversation LLM.

        Returns (formatted_context_string, raw_recall_results).
        """
        strategies = strategies or ["similarity"]
        all_details: list[str] = []

        with TimedOperation() as timer:
            try:
                recall_out = await self._hebbs.recall(
                    cue=cue,
                    strategies=strategies,
                    top_k=top_k,
                    entity_id=entity_id,
                )
                results_list = list(recall_out.results)
            except Exception as e:
                logger.warning("recall(%s) failed: %s", "+".join(strategies), e)
                results_list = []

        total_ms = timer.elapsed_ms
        self.total_recall_ms += total_ms
        self.recall_batches += 1

        if results_list:
            for r in results_list[:10]:
                mem = r.memory
                kind_str = mem.kind.value.upper()
                score_str = f"{r.score:.2f}"
                content_preview = mem.content[:55] if len(mem.content) > 55 else mem.content
                badge = "[Insight]" if kind_str == "INSIGHT" else f"[{kind_str.title()}]"
                all_details.append(f'{score_str}  "{content_preview}"  {badge}')

            all_details.insert(0, f"HEBBS server: {total_ms:.1f}ms")

            strat_str = "+".join(s.title() for s in strategies)
            record = OperationRecord(
                operation="RECALL",
                latency_ms=total_ms,
                summary=f"{len(results_list)} memories retrieved (strategy: {strat_str})",
                details=all_details,
                highlight_color="blue",
                server_ms=total_ms,
            )
            self._display.record_operation(record)

        context_lines = []
        for r in results_list:
            mem = r.memory
            kind_str = mem.kind.value
            line = f"- [{kind_str}] {mem.content}"
            if mem.context:
                ctx_parts = [f"{k}={v}" for k, v in list(mem.context.items())[:3]]
                line += f" ({', '.join(ctx_parts)})"
            context_lines.append(line)

        return "\n".join(context_lines), results_list

    async def prime_session(
        self,
        entity_id: str,
        similarity_cue: str | None = None,
    ) -> tuple[str, list[Any]]:
        """Prime a session: load relevant memories and insights for an entity.

        Returns (formatted_context_string, raw_prime_results).
        """
        with TimedOperation() as timer:
            try:
                prime_out = await self._hebbs.prime(
                    entity_id=entity_id,
                    max_memories=50,
                    similarity_cue=similarity_cue,
                )
            except Exception as e:
                logger.warning("prime(%s) failed: %s", entity_id, e)
                from hebbs.types import PrimeOutput
                prime_out = PrimeOutput(results=[], temporal_count=0, similarity_count=0)

        self.total_prime_ms += timer.elapsed_ms
        self.prime_calls += 1

        self._display.display_prime(
            entity_id=entity_id,
            total=len(prime_out.results),
            temporal_count=prime_out.temporal_count,
            similarity_count=prime_out.similarity_count,
            latency_ms=timer.elapsed_ms,
        )

        insights_list: list[Any] = []
        try:
            insights_list = await self._hebbs.insights(entity_id=entity_id, max_results=10)
        except Exception as e:
            logger.warning("insights(%s) failed: %s", entity_id, e)

        self._display.display_insights(insights_list)

        context_lines = []
        for r in prime_out.results:
            mem = r.memory
            kind_str = mem.kind.value
            line = f"- [{kind_str}] {mem.content}"
            context_lines.append(line)

        for ins in insights_list:
            context_lines.append(f"- [insight] {ins.content}")

        return "\n".join(context_lines), prime_out.results

    def get_subscribe_context(self, pushes: list[Any]) -> str:
        """Format subscribe pushes into context for the conversation LLM."""
        if not pushes:
            return ""
        lines = []
        for push in pushes:
            mem = push.memory
            lines.append(f"- [surfaced, confidence={push.confidence:.2f}] {mem.content}")
        return "\n".join(lines)
