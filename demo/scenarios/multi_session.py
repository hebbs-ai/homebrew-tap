"""Scenario C: Multi-Session Relationship.

Five sessions with delta_corp simulating a two-week sales relationship.
Validates temporal recall, prime initialization, and memory accumulation.
"""

from __future__ import annotations

from typing import Any

from demo.scenarios.base import Scenario

ENTITY = "delta_corp"

SESSIONS: list[list[str]] = [
    [
        "Hi, I'm Raj Patel, CTO at Delta Corp. We're a fintech startup with about 50 engineers.",
        "We're building a real-time fraud detection platform and need persistent memory for our ML pipeline.",
        "Our current architecture stores embeddings in Pinecone but we're hitting consistency issues at scale.",
    ],
    [
        "Following up from our first call. I discussed HEBBS with my team and they had some questions.",
        "Our lead ML engineer asked about the causal graph. Can memories form directed edges automatically?",
        "Also, what's the write throughput like? We're ingesting about 10K events per second during peak hours.",
    ],
    [
        "Good news -- the team is excited after reviewing the architecture doc you sent.",
        "We ran your benchmark suite against our Pinecone setup. HEBBS was 3x faster on recall latency.",
        "Raj wants to start a proof-of-concept. Can we get a trial license for the embedded engine?",
    ],
    [
        "We've been running the PoC for a week now. The causal recall is a game-changer for fraud chains.",
        "One issue: memory compaction is taking longer than expected during off-peak batch runs.",
        "Our compliance team also needs clarification on data residency. We're regulated under SOC2 and PCI-DSS.",
    ],
    [
        "We're ready to move forward. The PoC results convinced leadership -- 40% faster fraud detection.",
        "Raj approved the budget. We want to start with a 100-seat license and scale from there.",
        "Can we schedule a technical onboarding session for next week? We want to go live before end of quarter.",
    ],
]


class MultiSessionScenario(Scenario):
    name = "multi_session"
    description = "Five-session relationship validating temporal recall, prime, and memory growth"

    async def execute(self, hebbs: Any, agent: Any) -> None:
        await self._cleanup_entities(hebbs, [ENTITY])
        counts_after_session: list[int] = []

        for session_idx, turns in enumerate(SESSIONS):
            await agent.start_session(entity_id=ENTITY, session_num=session_idx + 1)
            for message in turns:
                await agent.process_turn(message, recall_strategies=["similarity", "temporal"])
            await agent.end_session()
            recall_check = await hebbs.recall(
                cue="delta corp fintech fraud detection",
                strategies=["temporal"],
                top_k=200,
                entity_id=ENTITY,
            )
            counts_after_session.append(len(recall_check.results))

        for i in range(1, len(counts_after_session)):
            self.assert_gte(
                f"memory_growth_session_{i + 1}",
                counts_after_session[i],
                counts_after_session[i - 1],
                f"Session {i + 1} count ({counts_after_session[i]}) should be >= "
                f"session {i} count ({counts_after_session[i - 1]})",
            )

        self.assert_gte(
            "total_memories_after_all_sessions",
            counts_after_session[-1], 10,
            f"Expected at least 10 memories across 5 sessions, got {counts_after_session[-1]}",
        )

        temporal_recall = await hebbs.recall(
            cue="Delta Corp engagement history",
            strategies=["temporal"],
            top_k=20,
            entity_id=ENTITY,
        )
        self.assert_not_empty("temporal_recall_returns_results", temporal_recall.results)

        prime_out = await hebbs.prime(entity_id=ENTITY, max_memories=50)
        self.assert_not_empty("prime_returns_accumulated_context", prime_out.results)
        self.assert_gte(
            "prime_result_count", len(prime_out.results), 3,
            f"Prime should return at least 3 memories after 5 sessions, got {len(prime_out.results)}",
        )
