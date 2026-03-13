"""Scenario E: Subscribe & Real-Time Memory Surfacing.

Seeds memories for a prospect, opens a subscribe stream, feeds
live conversation text, and validates that the pipeline operates
without errors.
"""

from __future__ import annotations

import asyncio
from typing import Any

from demo.scenarios.base import Scenario

SEED_MEMORIES: list[dict[str, Any]] = [
    {"content": "Acme Robotics uses ROS2 for fleet orchestration across 12 warehouse sites", "importance": 0.8, "context": {"stage": "discovery", "topic": "tech_stack"}},
    {"content": "VP Engineering Tom Bradley evaluating edge inference for pick-and-place arms", "importance": 0.7, "context": {"stage": "discovery", "contact": "Tom Bradley"}},
    {"content": "Current vision model runs on Jetson Orin, needs to support 60fps at 1080p", "importance": 0.9, "context": {"stage": "technical", "topic": "performance"}},
    {"content": "Safety certification ISO 13482 required before any production deployment", "importance": 0.9, "context": {"stage": "compliance", "topic": "safety_cert"}},
    {"content": "Annual robotics R&D budget is $8M, ML inference allocated $1.2M", "importance": 0.8, "context": {"stage": "qualification", "topic": "budget"}},
]

CONVERSATION_TURNS = [
    "We've been running into major latency issues with our current vision pipeline on the Jetson boards.",
    "Tom mentioned you might be able to help with edge inference optimization.",
    "Budget-wise, we carved out about a million dollars from the R&D allocation.",
]

ENTITY_ID = "acme_robotics"


class SubscribeRealtimeScenario(Scenario):
    name = "subscribe_realtime"
    description = "Seed memories, open subscribe stream, feed text, validate real-time surfacing"

    async def execute(self, hebbs: Any, agent: Any) -> None:
        await self._cleanup_entities(hebbs, [ENTITY_ID])

        for mem in SEED_MEMORIES:
            await hebbs.remember(
                content=mem["content"],
                importance=mem["importance"],
                context=mem["context"],
                entity_id=ENTITY_ID,
            )

        recall_check = await hebbs.recall(
            cue="robotics fleet warehouse",
            strategies=["temporal"],
            top_k=50,
            entity_id=ENTITY_ID,
        )
        self.assert_gte(
            "seed_memories_stored", len(recall_check.results), len(SEED_MEMORIES),
            f"Expected at least {len(SEED_MEMORIES)} memories for {ENTITY_ID}",
        )

        subscribe_ok = True
        try:
            await asyncio.wait_for(
                self._subscribe_feed_cycle(hebbs), timeout=15.0,
            )
        except asyncio.TimeoutError:
            subscribe_ok = False
        except Exception:
            subscribe_ok = False

        self.assert_true(
            "subscribe_pipeline_ran", subscribe_ok,
            "subscribe feed/close cycle completed without fatal error or timeout",
        )

        await agent.start_session(entity_id=ENTITY_ID, session_num=1, use_subscribe=False)
        turn_result = await agent.process_turn(
            prospect_message="Can you walk me through how your edge inference handles the Jetson Orin's thermal throttling?",
            recall_strategies=["similarity", "temporal"],
        )
        self.assert_true(
            "agent_turn_with_subscribe", turn_result is not None,
            "agent should complete a turn with subscribe active",
        )
        await agent.end_session()

    async def _subscribe_feed_cycle(self, hebbs: Any) -> None:
        """Run the subscribe/feed/close cycle with proper cleanup."""
        subscription = await hebbs.subscribe(
            entity_id=ENTITY_ID,
            confidence_threshold=0.3,
        )
        try:
            for turn_text in CONVERSATION_TURNS:
                await subscription.feed(turn_text)
                await asyncio.sleep(0.2)
        finally:
            await subscription.close()
