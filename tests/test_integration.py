"""Integration tests for the HEBBS Python SDK.

Exercises every SDK operation against a live hebbs-server.
Run with: pytest tests/test_integration.py -v

Requires a running server:
    HEBBS_AUTH_ENABLED=false hebbs-server
"""

from __future__ import annotations

import asyncio
import time

import pytest

from hebbs import (
    Edge,
    EdgeType,
    ForgetResult,
    HebbsClient,
    HebbsNotFoundError,
    Memory,
    MemoryKind,
    PrimeOutput,
    RecallOutput,
    RecallStrategy,
    RecallStrategyConfig,
    ReflectResult,
    ScoringWeights,
    SubscribePush,
)

ENDPOINT = "localhost:6380"

pytestmark = [pytest.mark.requires_server, pytest.mark.asyncio]


@pytest.fixture
async def client():
    async with HebbsClient(ENDPOINT) as c:
        yield c


@pytest.fixture
async def clean_entity(client: HebbsClient):
    """Provides a unique entity_id and cleans it up after the test."""
    entity_id = f"test-entity-{int(time.time() * 1_000_000)}"
    yield entity_id
    try:
        await client.forget(entity_id=entity_id)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  1. Health
# ═══════════════════════════════════════════════════════════════════════════


class TestHealth:
    async def test_health_check(self, client: HebbsClient):
        status = await client.health()
        assert status.serving is True
        assert isinstance(status.version, str) and len(status.version) > 0
        assert isinstance(status.memory_count, int)
        assert isinstance(status.uptime_seconds, int)

    async def test_count(self, client: HebbsClient):
        count = await client.count()
        assert isinstance(count, int) and count >= 0


# ═══════════════════════════════════════════════════════════════════════════
#  2. Remember
# ═══════════════════════════════════════════════════════════════════════════


class TestRemember:
    async def test_remember_basic(self, client: HebbsClient, clean_entity: str):
        mem = await client.remember(
            "Acme Corp uses Salesforce for CRM",
            entity_id=clean_entity,
        )
        assert isinstance(mem, Memory)
        assert mem.content == "Acme Corp uses Salesforce for CRM"
        assert len(mem.id) > 0
        assert mem.entity_id == clean_entity
        assert mem.kind == MemoryKind.EPISODE

    async def test_remember_with_importance(self, client: HebbsClient, clean_entity: str):
        mem = await client.remember(
            "Critical deal info: $2M ARR opportunity",
            importance=0.95,
            entity_id=clean_entity,
        )
        assert mem.importance >= 0.9

    async def test_remember_with_context(self, client: HebbsClient, clean_entity: str):
        ctx = {"source": "discovery_call", "rep": "alice", "stage": "qualification"}
        mem = await client.remember(
            "Budget is $500K annually",
            importance=0.8,
            context=ctx,
            entity_id=clean_entity,
        )
        assert mem.context.get("source") == "discovery_call"
        assert mem.context.get("rep") == "alice"

    async def test_remember_with_edges(self, client: HebbsClient, clean_entity: str):
        m1 = await client.remember("First meeting with Acme", entity_id=clean_entity)
        m2 = await client.remember(
            "Follow-up meeting with Acme",
            entity_id=clean_entity,
            edges=[Edge(target_id=m1.id, edge_type=EdgeType.FOLLOWED_BY, confidence=0.9)],
        )
        assert isinstance(m2, Memory)

    async def test_remember_timestamps(self, client: HebbsClient, clean_entity: str):
        mem = await client.remember("Timestamped memory", entity_id=clean_entity)
        assert mem.created_at > 0
        assert mem.updated_at > 0

    async def test_remember_multiple_rapid(self, client: HebbsClient, clean_entity: str):
        """Store 10 memories quickly to test throughput."""
        memories = []
        for i in range(10):
            m = await client.remember(
                f"Bulk memory #{i}: prospect mentioned feature {i}",
                importance=round(0.5 + (i * 0.05), 2),
                entity_id=clean_entity,
            )
            memories.append(m)
        assert len(memories) == 10
        ids = {m.id for m in memories}
        assert len(ids) == 10


# ═══════════════════════════════════════════════════════════════════════════
#  3. Get
# ═══════════════════════════════════════════════════════════════════════════


class TestGet:
    async def test_get_by_id(self, client: HebbsClient, clean_entity: str):
        stored = await client.remember("Get me later", entity_id=clean_entity)
        fetched = await client.get(stored.id)
        assert fetched.id == stored.id
        assert fetched.content == "Get me later"

    async def test_get_not_found(self, client: HebbsClient):
        with pytest.raises(HebbsNotFoundError):
            await client.get(b"\x00" * 16)


# ═══════════════════════════════════════════════════════════════════════════
#  4. Recall — All Strategies + Scoring Weights
# ═══════════════════════════════════════════════════════════════════════════


class TestRecall:
    @pytest.fixture
    async def seeded_entity(self, client: HebbsClient, clean_entity: str):
        """Seed an entity with diverse memories for recall tests."""
        memories = []
        data = [
            ("Acme Corp uses Salesforce for their CRM system", 0.9),
            ("Acme has 500 employees across 3 offices", 0.7),
            ("Their annual IT budget is around $2 million", 0.85),
            ("VP of Sales is John Smith, decision maker", 0.95),
            ("They evaluated HubSpot last year but rejected it", 0.6),
            ("Main pain point: data silos between sales and marketing", 0.8),
            ("Contract renewal is in Q3 2026", 0.75),
            ("Competitor Globex also uses Salesforce", 0.5),
        ]
        for content, importance in data:
            m = await client.remember(content, importance=importance, entity_id=clean_entity)
            memories.append(m)
        await asyncio.sleep(0.5)
        return clean_entity, memories

    async def test_recall_similarity(self, client: HebbsClient, seeded_entity):
        entity_id, _ = seeded_entity
        result = await client.recall(
            "What CRM does Acme use?",
            strategies=["similarity"],
            top_k=5,
            entity_id=entity_id,
        )
        assert isinstance(result, RecallOutput)
        assert len(result.results) > 0
        assert all(isinstance(r.score, float) for r in result.results)
        assert all(isinstance(r.memory, Memory) for r in result.results)

        top_content = result.results[0].memory.content.lower()
        assert "salesforce" in top_content or "crm" in top_content

    async def test_recall_temporal(self, client: HebbsClient, seeded_entity):
        entity_id, _ = seeded_entity
        result = await client.recall(
            "",
            strategies=["temporal"],
            top_k=5,
            entity_id=entity_id,
        )
        assert isinstance(result, RecallOutput)
        if result.results:
            for r in result.results:
                details = [d for d in r.strategy_details if d.strategy == "temporal"]
                assert len(details) > 0

    async def test_recall_causal(self, client: HebbsClient, seeded_entity):
        entity_id, memories = seeded_entity
        result = await client.recall(
            "Salesforce CRM",
            strategies=["causal"],
            top_k=5,
            entity_id=entity_id,
        )
        assert isinstance(result, RecallOutput)

    async def test_recall_analogical(self, client: HebbsClient, seeded_entity):
        entity_id, _ = seeded_entity
        result = await client.recall(
            "What tools does the company use?",
            strategies=["analogical"],
            top_k=5,
            entity_id=entity_id,
        )
        assert isinstance(result, RecallOutput)

    async def test_recall_all_strategies(self, client: HebbsClient, seeded_entity):
        entity_id, _ = seeded_entity
        result = await client.recall(
            "Tell me about Acme Corp",
            strategies=["similarity", "temporal", "causal", "analogical"],
            top_k=5,
            entity_id=entity_id,
        )
        assert isinstance(result, RecallOutput)
        assert len(result.results) > 0

    async def test_recall_with_scoring_weights_dataclass(self, client: HebbsClient, seeded_entity):
        entity_id, _ = seeded_entity
        weights = ScoringWeights(
            w_relevance=1.0,
            w_recency=0.0,
            w_importance=0.0,
            w_reinforcement=0.0,
        )
        result = await client.recall(
            "CRM system",
            strategies=["similarity"],
            top_k=5,
            entity_id=entity_id,
            scoring_weights=weights,
        )
        assert len(result.results) > 0

    async def test_recall_with_scoring_weights_dict(self, client: HebbsClient, seeded_entity):
        entity_id, _ = seeded_entity
        result = await client.recall(
            "CRM system",
            strategies=["similarity"],
            top_k=5,
            entity_id=entity_id,
            scoring_weights={
                "w_relevance": 0.0,
                "w_recency": 0.0,
                "w_importance": 1.0,
                "w_reinforcement": 0.0,
            },
        )
        assert len(result.results) > 0

    async def test_recall_weights_recency_heavy(self, client: HebbsClient, seeded_entity):
        entity_id, _ = seeded_entity
        result = await client.recall(
            "Acme",
            strategies=["similarity"],
            top_k=5,
            entity_id=entity_id,
            scoring_weights=ScoringWeights(
                w_relevance=0.1,
                w_recency=0.8,
                w_importance=0.05,
                w_reinforcement=0.05,
            ),
        )
        assert len(result.results) > 0

    async def test_recall_weights_reinforcement_heavy(self, client: HebbsClient, seeded_entity):
        entity_id, _ = seeded_entity
        result = await client.recall(
            "Acme",
            strategies=["similarity"],
            top_k=5,
            entity_id=entity_id,
            scoring_weights=ScoringWeights(
                w_relevance=0.1,
                w_recency=0.1,
                w_importance=0.1,
                w_reinforcement=0.7,
            ),
        )
        assert len(result.results) > 0

    async def test_recall_weights_with_max_age(self, client: HebbsClient, seeded_entity):
        entity_id, _ = seeded_entity
        result = await client.recall(
            "Acme",
            strategies=["similarity"],
            top_k=5,
            entity_id=entity_id,
            scoring_weights=ScoringWeights(
                w_relevance=0.5,
                w_recency=0.3,
                w_importance=0.1,
                w_reinforcement=0.1,
                max_age_us=3_600_000_000,
                reinforcement_cap=100,
            ),
        )
        assert isinstance(result, RecallOutput)

    async def test_recall_strategy_details(self, client: HebbsClient, seeded_entity):
        entity_id, _ = seeded_entity
        result = await client.recall(
            "Salesforce",
            strategies=["similarity"],
            top_k=3,
            entity_id=entity_id,
        )
        if result.results:
            r = result.results[0]
            assert len(r.strategy_details) > 0
            sd = r.strategy_details[0]
            assert sd.strategy == "similarity"
            assert isinstance(sd.relevance, float)

    async def test_recall_strategy_errors(self, client: HebbsClient, seeded_entity):
        """Strategy errors should be returned, not raised."""
        entity_id, _ = seeded_entity
        result = await client.recall(
            "test",
            strategies=["similarity"],
            top_k=3,
            entity_id=entity_id,
        )
        assert isinstance(result.strategy_errors, list)

    async def test_recall_default_strategy(self, client: HebbsClient, seeded_entity):
        entity_id, _ = seeded_entity
        result = await client.recall(
            "Acme",
            top_k=3,
            entity_id=entity_id,
        )
        assert len(result.results) > 0


# ═══════════════════════════════════════════════════════════════════════════
#  4b. Recall — Advanced Strategy Config (RecallStrategyConfig)
# ═══════════════════════════════════════════════════════════════════════════


class TestRecallAdvanced:
    """Tests for per-strategy configuration using RecallStrategyConfig."""

    @pytest.fixture
    async def seeded_entity_with_edges(self, client: HebbsClient, clean_entity: str):
        """Seed memories with causal edges for advanced recall tests."""
        m1 = await client.remember(
            "Discovery call with Acme Corp about CRM needs",
            importance=0.8,
            context={"stage": "discovery", "rep": "alice"},
            entity_id=clean_entity,
        )
        m2 = await client.remember(
            "Acme wants Salesforce replacement, budget $500K",
            importance=0.9,
            context={"stage": "qualification", "rep": "alice"},
            entity_id=clean_entity,
            edges=[Edge(target_id=m1.id, edge_type=EdgeType.FOLLOWED_BY)],
        )
        m3 = await client.remember(
            "Sent proposal to Acme, $200K annual license",
            importance=0.85,
            context={"stage": "proposal", "rep": "alice"},
            entity_id=clean_entity,
            edges=[Edge(target_id=m2.id, edge_type=EdgeType.CAUSED_BY)],
        )
        m4 = await client.remember(
            "Acme pushed back on pricing, wants 20% discount",
            importance=0.7,
            context={"stage": "negotiation", "rep": "alice"},
            entity_id=clean_entity,
            edges=[Edge(target_id=m3.id, edge_type=EdgeType.CAUSED_BY)],
        )
        m5 = await client.remember(
            "Enterprise CRM pricing patterns across industries",
            importance=0.6,
            context={"type": "insight", "domain": "pricing"},
            entity_id=clean_entity,
        )
        await asyncio.sleep(0.5)
        return clean_entity, [m1, m2, m3, m4, m5]

    async def test_recall_with_strategy_config_object(
        self, client: HebbsClient, seeded_entity_with_edges
    ):
        entity_id, _ = seeded_entity_with_edges
        result = await client.recall(
            "CRM needs",
            strategies=[RecallStrategyConfig("similarity", entity_id=entity_id)],
            top_k=5,
        )
        assert isinstance(result, RecallOutput)
        assert len(result.results) > 0

    async def test_recall_backward_compat_strings_still_work(
        self, client: HebbsClient, seeded_entity_with_edges
    ):
        entity_id, _ = seeded_entity_with_edges
        result = await client.recall(
            "Acme CRM",
            strategies=["similarity"],
            top_k=3,
            entity_id=entity_id,
        )
        assert len(result.results) > 0

    async def test_recall_mixed_strings_and_configs(
        self, client: HebbsClient, seeded_entity_with_edges
    ):
        entity_id, _ = seeded_entity_with_edges
        result = await client.recall(
            "Acme pricing",
            strategies=[
                "similarity",
                RecallStrategyConfig("temporal", entity_id=entity_id),
            ],
            top_k=5,
            entity_id=entity_id,
        )
        assert isinstance(result, RecallOutput)

    async def test_recall_similarity_with_ef_search(
        self, client: HebbsClient, seeded_entity_with_edges
    ):
        entity_id, _ = seeded_entity_with_edges
        result = await client.recall(
            "CRM replacement",
            strategies=[RecallStrategyConfig("similarity", ef_search=200)],
            top_k=5,
            entity_id=entity_id,
        )
        assert isinstance(result, RecallOutput)
        assert len(result.results) > 0

    async def test_recall_temporal_with_time_range(
        self, client: HebbsClient, seeded_entity_with_edges
    ):
        entity_id, _ = seeded_entity_with_edges
        now_us = int(time.time() * 1_000_000)
        one_hour_ago = now_us - 3_600_000_000
        result = await client.recall(
            "",
            strategies=[
                RecallStrategyConfig(
                    "temporal",
                    entity_id=entity_id,
                    time_range=(one_hour_ago, now_us),
                )
            ],
            top_k=10,
        )
        assert isinstance(result, RecallOutput)

    async def test_recall_causal_with_seed(
        self, client: HebbsClient, seeded_entity_with_edges
    ):
        entity_id, memories = seeded_entity_with_edges
        seed = memories[0]
        result = await client.recall(
            "causal walk",
            strategies=[
                RecallStrategyConfig(
                    "causal",
                    seed_memory_id=seed.id,
                    entity_id=entity_id,
                )
            ],
            top_k=10,
        )
        assert isinstance(result, RecallOutput)

    async def test_recall_causal_with_max_depth(
        self, client: HebbsClient, seeded_entity_with_edges
    ):
        entity_id, memories = seeded_entity_with_edges
        result_deep = await client.recall(
            "causal chain",
            strategies=[
                RecallStrategyConfig(
                    "causal",
                    seed_memory_id=memories[0].id,
                    max_depth=5,
                    entity_id=entity_id,
                )
            ],
            top_k=10,
        )
        result_shallow = await client.recall(
            "causal chain",
            strategies=[
                RecallStrategyConfig(
                    "causal",
                    seed_memory_id=memories[0].id,
                    max_depth=1,
                    entity_id=entity_id,
                )
            ],
            top_k=10,
        )
        assert isinstance(result_deep, RecallOutput)
        assert isinstance(result_shallow, RecallOutput)
        assert len(result_shallow.results) <= len(result_deep.results)

    async def test_recall_causal_with_edge_types(
        self, client: HebbsClient, seeded_entity_with_edges
    ):
        entity_id, memories = seeded_entity_with_edges
        result = await client.recall(
            "causes",
            strategies=[
                RecallStrategyConfig(
                    "causal",
                    seed_memory_id=memories[0].id,
                    edge_types=[EdgeType.FOLLOWED_BY],
                    entity_id=entity_id,
                )
            ],
            top_k=10,
        )
        assert isinstance(result, RecallOutput)

    async def test_recall_analogical_with_alpha(
        self, client: HebbsClient, seeded_entity_with_edges
    ):
        entity_id, _ = seeded_entity_with_edges
        result_embedding = await client.recall(
            "pricing patterns",
            strategies=[
                RecallStrategyConfig("analogical", analogical_alpha=1.0)
            ],
            top_k=5,
            entity_id=entity_id,
        )
        result_structural = await client.recall(
            "pricing patterns",
            strategies=[
                RecallStrategyConfig("analogical", analogical_alpha=0.0)
            ],
            top_k=5,
            entity_id=entity_id,
        )
        result_balanced = await client.recall(
            "pricing patterns",
            strategies=[
                RecallStrategyConfig("analogical", analogical_alpha=0.5)
            ],
            top_k=5,
            entity_id=entity_id,
        )
        assert isinstance(result_embedding, RecallOutput)
        assert isinstance(result_structural, RecallOutput)
        assert isinstance(result_balanced, RecallOutput)

    async def test_recall_with_cue_context(
        self, client: HebbsClient, seeded_entity_with_edges
    ):
        entity_id, _ = seeded_entity_with_edges
        result = await client.recall(
            "pricing concerns",
            strategies=["similarity"],
            top_k=5,
            entity_id=entity_id,
            cue_context={"industry": "enterprise", "stage": "negotiation"},
        )
        assert isinstance(result, RecallOutput)

    async def test_recall_per_strategy_top_k(
        self, client: HebbsClient, seeded_entity_with_edges
    ):
        entity_id, _ = seeded_entity_with_edges
        result = await client.recall(
            "Acme",
            strategies=[RecallStrategyConfig("similarity", top_k=2)],
            entity_id=entity_id,
        )
        assert isinstance(result, RecallOutput)
        assert len(result.results) <= 2

    async def test_recall_causal_seed_not_found(
        self, client: HebbsClient, seeded_entity_with_edges
    ):
        entity_id, _ = seeded_entity_with_edges
        result = await client.recall(
            "test",
            strategies=[
                RecallStrategyConfig(
                    "causal",
                    seed_memory_id=b"\x00" * 16,
                    entity_id=entity_id,
                )
            ],
            top_k=5,
        )
        assert len(result.strategy_errors) > 0

    async def test_recall_all_strategies_with_configs(
        self, client: HebbsClient, seeded_entity_with_edges
    ):
        """All four strategies with per-strategy config in a single call."""
        entity_id, memories = seeded_entity_with_edges
        result = await client.recall(
            "Acme CRM pricing",
            strategies=[
                RecallStrategyConfig("similarity", ef_search=100),
                RecallStrategyConfig("temporal", entity_id=entity_id),
                RecallStrategyConfig(
                    "causal",
                    seed_memory_id=memories[0].id,
                    max_depth=3,
                    entity_id=entity_id,
                ),
                RecallStrategyConfig("analogical", analogical_alpha=0.7),
            ],
            top_k=5,
            entity_id=entity_id,
            scoring_weights=ScoringWeights(
                w_relevance=0.6,
                w_recency=0.2,
                w_importance=0.15,
                w_reinforcement=0.05,
            ),
        )
        assert isinstance(result, RecallOutput)


# ═══════════════════════════════════════════════════════════════════════════
#  5. Revise
# ═══════════════════════════════════════════════════════════════════════════


class TestRevise:
    async def test_revise_content(self, client: HebbsClient, clean_entity: str):
        mem = await client.remember("Original content", entity_id=clean_entity)
        revised = await client.revise(mem.id, content="Updated content")
        assert revised.content == "Updated content"
        assert revised.kind == MemoryKind.REVISION

    async def test_revise_importance(self, client: HebbsClient, clean_entity: str):
        mem = await client.remember("Low priority", importance=0.3, entity_id=clean_entity)
        revised = await client.revise(mem.id, importance=0.95)
        assert revised.importance >= 0.9

    async def test_revise_context(self, client: HebbsClient, clean_entity: str):
        mem = await client.remember("Contextual", context={"a": 1}, entity_id=clean_entity)
        revised = await client.revise(mem.id, context={"b": 2})
        assert "b" in revised.context

    async def test_revise_preserves_id(self, client: HebbsClient, clean_entity: str):
        mem = await client.remember("Will be revised", entity_id=clean_entity)
        revised = await client.revise(mem.id, content="Revised version")
        fetched = await client.get(revised.id)
        assert fetched.content == "Revised version"


# ═══════════════════════════════════════════════════════════════════════════
#  6. Prime
# ═══════════════════════════════════════════════════════════════════════════


class TestPrime:
    async def test_prime_basic(self, client: HebbsClient, clean_entity: str):
        for i in range(5):
            await client.remember(
                f"Prime test memory {i} about sales pipeline",
                importance=0.7,
                entity_id=clean_entity,
            )
        await asyncio.sleep(0.3)

        result = await client.prime(clean_entity, max_memories=10)
        assert isinstance(result, PrimeOutput)
        assert isinstance(result.temporal_count, int)
        assert isinstance(result.similarity_count, int)

    async def test_prime_with_similarity_cue(self, client: HebbsClient, clean_entity: str):
        await client.remember("Uses Kubernetes for orchestration", entity_id=clean_entity)
        await client.remember("Runs on AWS us-east-1", entity_id=clean_entity)
        await asyncio.sleep(0.3)

        result = await client.prime(
            clean_entity,
            max_memories=5,
            similarity_cue="cloud infrastructure",
        )
        assert isinstance(result, PrimeOutput)

    async def test_prime_with_scoring_weights(self, client: HebbsClient, clean_entity: str):
        for i in range(3):
            await client.remember(f"Weighted prime memory {i}", entity_id=clean_entity)
        await asyncio.sleep(0.3)

        result = await client.prime(
            clean_entity,
            max_memories=5,
            scoring_weights=ScoringWeights(
                w_relevance=0.3,
                w_recency=0.5,
                w_importance=0.1,
                w_reinforcement=0.1,
            ),
        )
        assert isinstance(result, PrimeOutput)

    async def test_prime_empty_entity(self, client: HebbsClient):
        entity_id = f"empty-entity-{int(time.time() * 1_000_000)}"
        result = await client.prime(entity_id, max_memories=5)
        assert isinstance(result, PrimeOutput)
        assert len(result.results) == 0


# ═══════════════════════════════════════════════════════════════════════════
#  7. Forget
# ═══════════════════════════════════════════════════════════════════════════


class TestForget:
    async def test_forget_by_entity(self, client: HebbsClient):
        entity_id = f"forget-entity-{int(time.time() * 1_000_000)}"
        for i in range(5):
            await client.remember(f"Ephemeral memory {i}", entity_id=entity_id)

        result = await client.forget(entity_id=entity_id)
        assert isinstance(result, ForgetResult)
        assert result.forgotten_count >= 5

    async def test_forget_by_memory_ids(self, client: HebbsClient, clean_entity: str):
        m1 = await client.remember("Delete me 1", entity_id=clean_entity)
        m2 = await client.remember("Delete me 2", entity_id=clean_entity)
        _m3 = await client.remember("Keep me", entity_id=clean_entity)

        result = await client.forget(memory_ids=[m1.id, m2.id])
        assert isinstance(result, ForgetResult)
        assert result.forgotten_count >= 2

    async def test_forget_cascade_and_tombstone(self, client: HebbsClient):
        entity_id = f"cascade-{int(time.time() * 1_000_000)}"
        m1 = await client.remember("Root memory", entity_id=entity_id)
        await client.remember(
            "Child memory",
            entity_id=entity_id,
            edges=[Edge(target_id=m1.id, edge_type=EdgeType.CAUSED_BY)],
        )
        result = await client.forget(entity_id=entity_id)
        assert isinstance(result.cascade_count, int)
        assert isinstance(result.tombstone_count, int)

    async def test_forget_idempotent(self, client: HebbsClient):
        entity_id = f"idempotent-{int(time.time() * 1_000_000)}"
        await client.remember("One-time memory", entity_id=entity_id)
        await client.forget(entity_id=entity_id)
        result2 = await client.forget(entity_id=entity_id)
        assert result2.forgotten_count == 0

    async def test_recall_after_forget(self, client: HebbsClient):
        entity_id = f"recall-after-forget-{int(time.time() * 1_000_000)}"
        await client.remember("Secret data that must be erased", entity_id=entity_id)
        await asyncio.sleep(0.3)
        await client.forget(entity_id=entity_id)
        await asyncio.sleep(0.3)

        result = await client.recall(
            "Secret data",
            strategies=["similarity"],
            top_k=5,
            entity_id=entity_id,
        )
        assert len(result.results) == 0


# ═══════════════════════════════════════════════════════════════════════════
#  8. Reflect + Insights
# ═══════════════════════════════════════════════════════════════════════════


class TestReflect:
    async def test_reflect_entity(self, client: HebbsClient, clean_entity: str):
        for i in range(15):
            await client.remember(
                f"Sales pattern observation {i}: customers in fintech sector prefer API-first products",
                importance=0.7 + (i % 3) * 0.1,
                entity_id=clean_entity,
            )
        await asyncio.sleep(0.5)

        result = await client.reflect(entity_id=clean_entity)
        assert isinstance(result, ReflectResult)
        assert isinstance(result.insights_created, int)
        assert isinstance(result.clusters_found, int)
        assert isinstance(result.clusters_processed, int)
        assert isinstance(result.memories_processed, int)

    async def test_reflect_global(self, client: HebbsClient, clean_entity: str):
        for i in range(5):
            await client.remember(
                f"Global pattern {i}: enterprise customers need SSO",
                entity_id=clean_entity,
            )
        await asyncio.sleep(0.3)
        result = await client.reflect()
        assert isinstance(result, ReflectResult)

    async def test_insights_retrieval(self, client: HebbsClient, clean_entity: str):
        for i in range(10):
            await client.remember(
                f"Insight source {i}: customers ask about data residency",
                entity_id=clean_entity,
            )
        await asyncio.sleep(0.3)
        await client.reflect(entity_id=clean_entity)
        await asyncio.sleep(0.3)

        insights = await client.insights(entity_id=clean_entity)
        assert isinstance(insights, list)
        for insight in insights:
            assert isinstance(insight, Memory)
            assert insight.kind == MemoryKind.INSIGHT

    async def test_insights_max_results(self, client: HebbsClient, clean_entity: str):
        for i in range(10):
            await client.remember(f"Bulk insight source {i}", entity_id=clean_entity)
        await asyncio.sleep(0.3)
        await client.reflect(entity_id=clean_entity)
        await asyncio.sleep(0.3)

        insights = await client.insights(entity_id=clean_entity, max_results=2)
        assert len(insights) <= 2


# ═══════════════════════════════════════════════════════════════════════════
#  9. Subscribe
# ═══════════════════════════════════════════════════════════════════════════


class TestSubscribe:
    async def test_subscribe_and_feed(self, client: HebbsClient, clean_entity: str):
        for i in range(3):
            await client.remember(
                f"Background knowledge {i} about machine learning",
                entity_id=clean_entity,
            )
        await asyncio.sleep(0.3)

        sub = await client.subscribe(entity_id=clean_entity, confidence_threshold=0.1)
        assert sub.subscription_id > 0

        await sub.feed("Tell me about machine learning applications")

        pushes: list[SubscribePush] = []
        try:
            async for push in sub:
                assert isinstance(push, SubscribePush)
                assert isinstance(push.memory, Memory)
                assert isinstance(push.confidence, float)
                pushes.append(push)
                if len(pushes) >= 2:
                    break
        except asyncio.TimeoutError:
            pass
        finally:
            await sub.close()

    async def test_subscribe_close(self, client: HebbsClient, clean_entity: str):
        sub = await client.subscribe(entity_id=clean_entity)
        assert sub.subscription_id > 0
        await sub.close()


# ═══════════════════════════════════════════════════════════════════════════
#  10. SetPolicy
# ═══════════════════════════════════════════════════════════════════════════


class TestSetPolicy:
    async def test_set_policy(self, client: HebbsClient):
        applied = await client.set_policy(
            max_snapshots_per_memory=5,
            auto_forget_threshold=0.01,
            decay_half_life_days=30.0,
        )
        assert applied is True

    async def test_set_policy_partial(self, client: HebbsClient):
        applied = await client.set_policy(max_snapshots_per_memory=10)
        assert applied is True


# ═══════════════════════════════════════════════════════════════════════════
#  11. End-to-end flow (mirrors a CLI session)
# ═══════════════════════════════════════════════════════════════════════════


class TestEndToEnd:
    """Full lifecycle matching what you'd do with the CLI."""

    async def test_full_lifecycle(self, client: HebbsClient):
        entity = f"e2e-{int(time.time() * 1_000_000)}"

        status = await client.health()
        assert status.serving

        m1 = await client.remember(
            "Acme Corp is evaluating HEBBS for their AI infrastructure",
            importance=0.9,
            context={"source": "discovery_call", "rep": "alice"},
            entity_id=entity,
        )
        m2 = await client.remember(
            "Acme's CTO is excited about the real-time memory surfacing feature",
            importance=0.85,
            entity_id=entity,
            edges=[Edge(target_id=m1.id, edge_type=EdgeType.FOLLOWED_BY)],
        )
        await client.remember(
            "Budget approval expected by end of Q2",
            importance=0.7,
            entity_id=entity,
        )

        fetched = await client.get(m1.id)
        assert fetched.content == m1.content

        revised = await client.revise(m2.id, importance=0.95)
        assert revised.importance >= 0.9

        await asyncio.sleep(0.3)

        recall_sim = await client.recall(
            "What does Acme think about HEBBS?",
            strategies=["similarity"],
            top_k=5,
            entity_id=entity,
            scoring_weights=ScoringWeights(
                w_relevance=0.6,
                w_recency=0.2,
                w_importance=0.15,
                w_reinforcement=0.05,
            ),
        )
        assert len(recall_sim.results) > 0

        recall_temp = await client.recall(
            "",
            strategies=["temporal"],
            top_k=5,
            entity_id=entity,
        )
        assert isinstance(recall_temp, RecallOutput)

        recall_multi = await client.recall(
            "AI infrastructure evaluation",
            strategies=["similarity", "temporal", "causal", "analogical"],
            top_k=5,
            entity_id=entity,
        )
        assert isinstance(recall_multi, RecallOutput)

        primed = await client.prime(
            entity,
            max_memories=10,
            similarity_cue="HEBBS evaluation progress",
        )
        assert isinstance(primed, PrimeOutput)

        reflect_result = await client.reflect(entity_id=entity)
        assert isinstance(reflect_result, ReflectResult)

        insights = await client.insights(entity_id=entity, max_results=5)
        assert isinstance(insights, list)

        count_before = await client.count()
        forget_result = await client.forget(entity_id=entity)
        assert forget_result.forgotten_count >= 3
        count_after = await client.count()
        assert count_after <= count_before

        empty_recall = await client.recall(
            "Acme",
            strategies=["similarity"],
            entity_id=entity,
        )
        assert len(empty_recall.results) == 0


# ═══════════════════════════════════════════════════════════════════════════
#  12. Error handling
# ═══════════════════════════════════════════════════════════════════════════


class TestErrors:
    async def test_get_nonexistent(self, client: HebbsClient):
        with pytest.raises(HebbsNotFoundError):
            await client.get(b"\x00" * 16)

    async def test_connection_error(self):
        from hebbs import HebbsConnectionError
        client = HebbsClient("localhost:1")
        await client.connect()
        with pytest.raises((HebbsConnectionError, Exception)):
            await client.health()
        await client.close()
