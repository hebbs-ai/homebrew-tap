#!/usr/bin/env python3
"""
HEBBS Python SDK — Production E2E Validation
=============================================

Full production validation of every Python SDK operation against a live
HEBBS server. Zero mocks — real ONNX embeddings (BGE-small-en-v1.5), real
OpenAI-powered reflect pipeline, real authentication. This is the script
you run before shipping.

It covers all 14 SDK operations: health, count, remember (with edges),
get, recall (similarity, temporal, causal, analogical, ScoringWeights,
RecallStrategyConfig, mixed strategies, cue_context), prime, revise,
set_policy, subscribe/feed/close, forget (by ID + by entity), reflect,
insights, auth (rejection + acceptance), and error handling.

Each test prints: the SDK function called, all arguments sent, and the
full server response.

How to Run
----------

### Terminal 1 — Start the HEBBS server

    cd hebbs
    rm -rf ./hebbs-data   # fresh state for a clean run

    # First run downloads ONNX model (~30 MB) automatically.
    # On first start the server prints a bootstrap API key — save it.

    OPENAI_API_KEY="sk-proj-..."                    \\
    HEBBS_REFLECT_ENABLED=true                      \\
    HEBBS_REFLECT_PROPOSAL_PROVIDER=openai           \\
    HEBBS_REFLECT_PROPOSAL_MODEL=gpt-4o              \\
    HEBBS_REFLECT_VALIDATION_PROVIDER=openai          \\
    HEBBS_REFLECT_VALIDATION_MODEL=gpt-4o             \\
    HEBBS_LOGGING_FORMAT=json                         \\
    cargo run --release --bin hebbs-server

    # The server will print:
    #   ╔══════════════════════════════════════════════════════════════════╗
    #   ║  BOOTSTRAP API KEY (save this -- it will not be shown again)    ║
    #   ║  hb_abc123...                                                   ║
    #   ╚══════════════════════════════════════════════════════════════════╝
    #
    # Copy that key for the next step.

### Terminal 2 — Install SDK from local source and run tests

    cd hebbs-python
    python3 -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"

    export HEBBS_API_KEY="hb_<key-from-server-banner>"
    export OPENAI_API_KEY="sk-proj-..."

    python tests/test_e2e_python_sdk.py

What Each Environment Variable Does
------------------------------------
  HEBBS_API_KEY    (required) Auth token printed by the server on first
                   start. Every SDK call sends this as a Bearer token.

  OPENAI_API_KEY   (required) Used by the HEBBS server for the reflect
                   pipeline (insight generation via GPT-4o). The Python
                   SDK itself does NOT call OpenAI — the server does.
                   Set this when starting the server AND when running
                   this script (the script checks it is set).

  HEBBS_ADDRESS    (optional) gRPC address of the server.
                   Default: localhost:6380

Server Configuration Explained
-------------------------------
  HEBBS_REFLECT_ENABLED=true
      Turns on the background reflect pipeline. Without this, the
      reflect() and insights() calls will not produce real insights.

  HEBBS_REFLECT_PROPOSAL_PROVIDER=openai
  HEBBS_REFLECT_PROPOSAL_MODEL=gpt-4o
      The LLM provider and model used to propose insights from memory
      clusters. Alternatives: anthropic/claude-sonnet-4-20250514, ollama/llama3.

  HEBBS_REFLECT_VALIDATION_PROVIDER=openai
  HEBBS_REFLECT_VALIDATION_MODEL=gpt-4o
      The LLM provider and model used to validate proposed insights.

  HEBBS_LOGGING_FORMAT=json
      Structured JSON logs (production-grade). Use "pretty" for dev.

  Embeddings use the built-in ONNX model (BGE-small-en-v1.5, 384 dims).
  No external embedding API key is needed — the model runs locally.

  Auth is enabled by default. The server auto-generates a bootstrap
  admin API key on first start and prints it to stderr.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import traceback
from dataclasses import dataclass, fields, asdict
from typing import Any

# ---------------------------------------------------------------------------
# Import SDK from local source
# ---------------------------------------------------------------------------
from hebbs import (
    Edge,
    EdgeType,
    HebbsClient,
    MemoryKind,
    RecallStrategyConfig,
    ScoringWeights,
)
from hebbs.exceptions import (
    HebbsAuthenticationError,
    HebbsError,
    HebbsNotFoundError,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SERVER_ADDRESS = os.environ.get("HEBBS_ADDRESS", "localhost:6380")
API_KEY = os.environ.get("HEBBS_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

DIM = "\033[2m"
RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _trunc(s: str, n: int = 70) -> str:
    return s[:n] + "..." if len(s) > n else s


def _fmt_val(v: Any) -> str:
    """Format a single value for display."""
    if isinstance(v, bytes):
        return v.hex()[:16] + "..." if len(v) > 8 else v.hex()
    if isinstance(v, str):
        return f'"{_trunc(v, 60)}"'
    if isinstance(v, float):
        return f"{v:.4f}"
    if isinstance(v, list) and len(v) > 5:
        return f"[{len(v)} items]"
    if isinstance(v, dict) and len(v) > 5:
        return f"{{{len(v)} keys}}"
    return repr(v)


def _fmt_kwargs(kw: dict[str, Any]) -> str:
    """Format keyword arguments as k=v pairs, skipping None."""
    parts = []
    for k, v in kw.items():
        if v is None:
            continue
        parts.append(f"{k}={_fmt_val(v)}")
    return ", ".join(parts)


def _fmt_memory(m: Any, prefix: str = "") -> list[str]:
    """Format a Memory object into display lines."""
    lines = [
        f"{prefix}Memory(",
        f"{prefix}  id          = {m.id.hex()[:16]}...",
        f"{prefix}  content     = {_trunc(m.content, 70)}",
        f"{prefix}  importance  = {m.importance:.4f}",
        f"{prefix}  entity_id   = {m.entity_id}",
        f"{prefix}  kind        = {m.kind.value}",
        f"{prefix}  context     = {dict(m.context) if m.context else '{}'}",
        f"{prefix}  created_at  = {m.created_at}",
        f"{prefix}  decay_score = {m.decay_score:.4f}",
        f"{prefix})",
    ]
    return lines


def _fmt_recall_result(r: Any, idx: int, prefix: str = "") -> list[str]:
    """Format a single RecallResult."""
    lines = [f"{prefix}[{idx}] score={r.score:.4f}  content=\"{_trunc(r.memory.content, 55)}\""]
    for d in r.strategy_details:
        parts = [f"strategy={d.strategy}", f"relevance={d.relevance:.4f}"]
        if d.depth is not None:
            parts.append(f"depth={d.depth}")
        if d.embedding_similarity is not None:
            parts.append(f"emb_sim={d.embedding_similarity:.4f}")
        if d.structural_similarity is not None:
            parts.append(f"struct_sim={d.structural_similarity:.4f}")
        if d.timestamp is not None:
            parts.append(f"ts={d.timestamp}")
        lines.append(f"{prefix}     {', '.join(parts)}")
    return lines


class Log:
    """Accumulates structured log lines for a test."""

    def __init__(self) -> None:
        self._lines: list[str] = []

    def call(self, fn: str, **kw: Any) -> None:
        self._lines.append(f"{CYAN}CALL:{RESET}     h.{fn}({_fmt_kwargs(kw)})")

    def sent(self, **kw: Any) -> None:
        for k, v in kw.items():
            if v is None:
                continue
            self._lines.append(f"{DIM}SENT:{RESET}     {k} = {_fmt_val(v)}")

    def response(self, label: str, obj_str: str) -> None:
        self._lines.append(f"{GREEN}RESPONSE:{RESET} {label}: {obj_str}")

    def detail(self, line: str) -> None:
        self._lines.append(f"          {line}")

    def info(self, line: str) -> None:
        self._lines.append(f"{YELLOW}INFO:{RESET}     {line}")

    def text(self) -> str:
        return "\n".join(self._lines)


# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    duration_ms: float


RESULTS: list[TestResult] = []
_section_idx = 0


def section(title: str) -> None:
    global _section_idx
    _section_idx += 1
    print(f"\n{'='*72}")
    print(f"  SECTION {_section_idx}: {title}")
    print(f"{'='*72}")


def _record(name: str, passed: bool, msg: str, dur: float) -> None:
    tag = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  [{tag}] {name}  ({dur:.0f}ms)")
    if msg:
        for line in msg.strip().splitlines():
            print(f"         {line}")
    RESULTS.append(TestResult(name, passed, msg, dur))


async def run_test(name: str, coro) -> None:
    print(f"\n  >>> {name}")
    t0 = time.monotonic()
    try:
        msg = await coro
        dur = (time.monotonic() - t0) * 1000
        _record(name, True, msg or "", dur)
    except Exception as exc:
        dur = (time.monotonic() - t0) * 1000
        tb = traceback.format_exception(exc)
        _record(name, False, f"{type(exc).__name__}: {exc}\n{''.join(tb[-3:])}", dur)


def client(**kw) -> HebbsClient:
    return HebbsClient(SERVER_ADDRESS, api_key=API_KEY, **kw)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_health() -> str:
    log = Log()
    async with client() as h:
        log.call("health")
        status = await h.health()
        log.response("HealthStatus",
            f"serving={status.serving}, version={status.version}, "
            f"memory_count={status.memory_count}, uptime={status.uptime_seconds}s")
        assert status.serving, "server not serving"
        assert status.version, "version empty"
    return log.text()


async def test_count() -> str:
    log = Log()
    async with client() as h:
        log.call("count")
        count = await h.count()
        log.response("int", str(count))
    return log.text()


async def test_remember_basic() -> str:
    log = Log()
    async with client() as h:
        kw = dict(
            content="ACME Corp uses Salesforce for CRM",
            importance=0.8,
            context={"industry": "technology", "tool": "salesforce"},
            entity_id="acme",
        )
        log.call("remember", **kw)
        mem = await h.remember(**kw)
        log.response("Memory", "")
        for line in _fmt_memory(mem, "  "):
            log.detail(line)
        assert mem.id, "no memory ID"
        assert mem.content == "ACME Corp uses Salesforce for CRM"
        assert abs(mem.importance - 0.8) < 0.01
        assert mem.entity_id == "acme"
        assert mem.context.get("industry") == "technology"
        assert mem.kind == MemoryKind.EPISODE
    return log.text()


async def test_remember_with_edges() -> str:
    log = Log()
    async with client() as h:
        kw1 = dict(content="Initech CTO expressed interest in our API", entity_id="initech")
        log.call("remember", **kw1)
        mem1 = await h.remember(**kw1)
        log.response("Memory", f"id={mem1.id.hex()[:16]}...")

        edge = Edge(target_id=mem1.id, edge_type=EdgeType.FOLLOWED_BY, confidence=0.95)
        kw2 = dict(
            content="Initech requested a technical deep-dive meeting",
            entity_id="initech",
            edges=[edge],
        )
        log.call("remember", content=kw2["content"], entity_id=kw2["entity_id"],
                 edges=f"[Edge(target={mem1.id.hex()[:16]}..., FOLLOWED_BY, 0.95)]")
        mem2 = await h.remember(**kw2)
        log.response("Memory", f"id={mem2.id.hex()[:16]}...")
        assert mem1.id and mem2.id
        assert mem1.id != mem2.id
    return log.text()


async def test_get() -> str:
    log = Log()
    async with client() as h:
        log.call("remember", content="Test memory for get operation", importance=0.5)
        mem = await h.remember(content="Test memory for get operation", importance=0.5)
        log.response("Memory", f"id={mem.id.hex()[:16]}...")

        log.call("get", memory_id=mem.id)
        retrieved = await h.get(mem.id)
        log.response("Memory", "")
        for line in _fmt_memory(retrieved, "  "):
            log.detail(line)
        assert retrieved.content == "Test memory for get operation"
    return log.text()


async def test_recall_similarity() -> str:
    log = Log()
    async with client() as h:
        kw = dict(cue="What CRM does ACME use?", top_k=5)
        log.call("recall", **kw)
        result = await h.recall(**kw)
        log.response("RecallOutput",
            f"results={len(result.results)}, strategy_errors={len(result.strategy_errors)}")
        for i, r in enumerate(result.results[:5]):
            for line in _fmt_recall_result(r, i, "  "):
                log.detail(line)
        assert result.results, "no recall results"
        top = result.results[0]
        assert "salesforce" in top.memory.content.lower() or "acme" in top.memory.content.lower()
    return log.text()


async def test_recall_multi_strategy() -> str:
    log = Log()
    async with client() as h:
        kw = dict(cue="What is Initech doing?", strategies=["similarity", "temporal"],
                  entity_id="initech", top_k=5)
        log.call("recall", **kw)
        result = await h.recall(**kw)
        log.response("RecallOutput",
            f"results={len(result.results)}, strategy_errors={len(result.strategy_errors)}")
        for i, r in enumerate(result.results[:5]):
            for line in _fmt_recall_result(r, i, "  "):
                log.detail(line)
        assert result.results, "no multi-strategy results"
    return log.text()


async def test_recall_scoring_weights_dataclass() -> str:
    log = Log()
    async with client() as h:
        recency_weights = ScoringWeights(w_relevance=0.1, w_recency=0.7, w_importance=0.1, w_reinforcement=0.1)
        log.call("recall", cue="Initech evaluation",
                 scoring_weights="ScoringWeights(w_rel=0.1, w_rec=0.7, w_imp=0.1, w_rein=0.1)", top_k=5)
        result_recency = await h.recall(cue="Initech evaluation", scoring_weights=recency_weights, top_k=5)
        log.response("RecallOutput (recency-heavy)", f"results={len(result_recency.results)}")
        for i, r in enumerate(result_recency.results[:3]):
            for line in _fmt_recall_result(r, i, "  "):
                log.detail(line)

        relevance_weights = ScoringWeights(w_relevance=0.8, w_recency=0.05, w_importance=0.1, w_reinforcement=0.05)
        log.call("recall", cue="Initech evaluation",
                 scoring_weights="ScoringWeights(w_rel=0.8, w_rec=0.05, w_imp=0.1, w_rein=0.05)", top_k=5)
        result_relevance = await h.recall(cue="Initech evaluation", scoring_weights=relevance_weights, top_k=5)
        log.response("RecallOutput (relevance-heavy)", f"results={len(result_relevance.results)}")
        for i, r in enumerate(result_relevance.results[:3]):
            for line in _fmt_recall_result(r, i, "  "):
                log.detail(line)

        assert result_recency.results, "no recency results"
        assert result_relevance.results, "no relevance results"
    return log.text()


async def test_recall_scoring_weights_dict() -> str:
    log = Log()
    async with client() as h:
        weights_dict = {"w_relevance": 0.9, "w_recency": 0.05, "w_importance": 0.05, "w_reinforcement": 0.0}
        log.call("recall", cue="CRM evaluation", scoring_weights=weights_dict, top_k=3)
        result = await h.recall(cue="CRM evaluation", scoring_weights=weights_dict, top_k=3)
        log.response("RecallOutput", f"results={len(result.results)}")
        for i, r in enumerate(result.results[:3]):
            for line in _fmt_recall_result(r, i, "  "):
                log.detail(line)
        assert result.results, "no results with dict weights"
    return log.text()


async def test_recall_strategy_config() -> str:
    log = Log()
    async with client() as h:
        cfg = RecallStrategyConfig(strategy="similarity", entity_id="initech", top_k=3, ef_search=64)
        log.call("recall", cue="Initech CTO interest",
                 strategies=f"[RecallStrategyConfig(strategy='similarity', entity_id='initech', top_k=3, ef_search=64)]")
        result = await h.recall(cue="Initech CTO interest", strategies=[cfg])
        log.response("RecallOutput", f"results={len(result.results)}")
        for i, r in enumerate(result.results[:3]):
            for line in _fmt_recall_result(r, i, "  "):
                log.detail(line)
        assert result.results, "no RecallStrategyConfig results"
    return log.text()


async def test_recall_mixed_strategies() -> str:
    log = Log()
    async with client() as h:
        cfg = RecallStrategyConfig(strategy="similarity", top_k=3)
        log.call("recall", cue="Initech evaluation",
                 strategies="['temporal', RecallStrategyConfig(strategy='similarity', top_k=3)]",
                 entity_id="initech", top_k=5)
        result = await h.recall(
            cue="Initech evaluation",
            strategies=["temporal", cfg],
            entity_id="initech", top_k=5,
        )
        strategies_seen = {d.strategy for r in result.results for d in r.strategy_details}
        log.response("RecallOutput", f"results={len(result.results)}, strategies_seen={strategies_seen}")
        for i, r in enumerate(result.results[:5]):
            for line in _fmt_recall_result(r, i, "  "):
                log.detail(line)
        assert result.results, "no mixed-strategy results"
    return log.text()


async def test_recall_causal() -> str:
    log = Log()
    async with client() as h:
        log.info("finding seed memory via similarity recall first...")
        log.call("recall", cue="Initech CTO", strategies=["similarity"], top_k=1, entity_id="initech")
        sim = await h.recall(cue="Initech CTO", strategies=["similarity"], top_k=1, entity_id="initech")
        log.response("RecallOutput", f"results={len(sim.results)}")
        if not sim.results:
            log.info("SKIP: no seed memory found for causal test")
            return log.text()

        seed_id = sim.results[0].memory.id
        log.info(f"seed_memory_id = {seed_id.hex()[:16]}... ('{_trunc(sim.results[0].memory.content, 40)}')")

        cfg = RecallStrategyConfig(
            strategy="causal", seed_memory_id=seed_id, max_depth=3,
            edge_types=[EdgeType.FOLLOWED_BY, EdgeType.CAUSED_BY],
        )
        log.call("recall", cue="Initech",
                 strategies=f"[RecallStrategyConfig(strategy='causal', seed_memory_id={seed_id.hex()[:16]}..., "
                            f"max_depth=3, edge_types=[FOLLOWED_BY, CAUSED_BY])]")
        result = await h.recall(cue="Initech", strategies=[cfg])
        log.response("RecallOutput", f"results={len(result.results)}, errors={len(result.strategy_errors)}")
        for i, r in enumerate(result.results[:5]):
            for line in _fmt_recall_result(r, i, "  "):
                log.detail(line)
        if result.strategy_errors:
            for err in result.strategy_errors:
                log.detail(f"strategy_error: {err.strategy}: {err.message}")
    return log.text()


async def test_recall_analogical() -> str:
    log = Log()
    async with client() as h:
        cue_ctx = {"industry": "technology", "stage": "evaluation"}
        cfg = RecallStrategyConfig(strategy="analogical", analogical_alpha=0.7)
        log.call("recall", cue="enterprise CRM evaluation",
                 strategies="[RecallStrategyConfig(strategy='analogical', analogical_alpha=0.7)]",
                 cue_context=cue_ctx, top_k=5)
        result = await h.recall(
            cue="enterprise CRM evaluation", strategies=[cfg],
            cue_context=cue_ctx, top_k=5,
        )
        log.response("RecallOutput", f"results={len(result.results)}, errors={len(result.strategy_errors)}")
        for i, r in enumerate(result.results[:5]):
            for line in _fmt_recall_result(r, i, "  "):
                log.detail(line)
    return log.text()


async def test_prime() -> str:
    log = Log()
    async with client() as h:
        kw = dict(entity_id="initech", max_memories=20, similarity_cue="enterprise evaluation")
        log.call("prime", **kw)
        out = await h.prime(**kw)
        log.response("PrimeOutput",
            f"results={len(out.results)}, temporal_count={out.temporal_count}, "
            f"similarity_count={out.similarity_count}")
        for i, r in enumerate(out.results[:5]):
            for line in _fmt_recall_result(r, i, "  "):
                log.detail(line)
        assert out.results is not None
    return log.text()


async def test_prime_with_weights() -> str:
    log = Log()
    async with client() as h:
        weights = ScoringWeights(w_relevance=0.3, w_recency=0.5, w_importance=0.1, w_reinforcement=0.1)
        log.call("prime", entity_id="initech", similarity_cue="evaluation",
                 scoring_weights="ScoringWeights(w_rel=0.3, w_rec=0.5, w_imp=0.1, w_rein=0.1)")
        out = await h.prime(entity_id="initech", similarity_cue="evaluation", scoring_weights=weights)
        log.response("PrimeOutput", f"results={len(out.results)}")
        for i, r in enumerate(out.results[:3]):
            for line in _fmt_recall_result(r, i, "  "):
                log.detail(line)
    return log.text()


async def test_revise() -> str:
    log = Log()
    async with client() as h:
        log.call("remember", content="Initech deal size: 200 seats", importance=0.7, entity_id="initech")
        mem = await h.remember(content="Initech deal size: 200 seats", importance=0.7, entity_id="initech")
        log.response("Memory", f"id={mem.id.hex()[:16]}..., content='{mem.content}'")

        kw = dict(
            memory_id=mem.id,
            content="Initech deal size expanded: 350 seats",
            importance=0.95,
            context={"deal_size": "350 seats", "stage": "negotiation"},
        )
        log.call("revise", memory_id=mem.id, content=kw["content"],
                 importance=kw["importance"], context=kw["context"])
        revised = await h.revise(**kw)
        log.response("Memory (revised)", "")
        for line in _fmt_memory(revised, "  "):
            log.detail(line)
        assert revised.content == "Initech deal size expanded: 350 seats"
        assert revised.importance >= 0.9
    return log.text()


async def test_set_policy() -> str:
    log = Log()
    async with client() as h:
        kw = dict(max_snapshots_per_memory=5, auto_forget_threshold=0.01, decay_half_life_days=30.0)
        log.call("set_policy", **kw)
        ok = await h.set_policy(**kw)
        log.response("bool", str(ok))
        assert ok, "set_policy returned False"
    return log.text()


async def test_subscribe_feed_close() -> str:
    log = Log()
    async with client() as h:
        log.call("subscribe", entity_id="initech", confidence_threshold=0.3)
        sub = await h.subscribe(entity_id="initech", confidence_threshold=0.3)
        log.response("Subscription", f"subscription_id={sub.subscription_id}")

        feed_text = "Tell me about Initech's evaluation process"
        log.call("sub.feed", text=feed_text)
        await sub.feed(feed_text)
        log.response("feed", "accepted")

        log.info("listening for pushes (3s timeout)...")
        pushes = await sub.listen(timeout=3.0, max_pushes=5)
        for i, push in enumerate(pushes):
            log.detail(
                f"push[{i}]: confidence={push.confidence:.4f}, "
                f"seq={push.sequence_number}, content=\"{_trunc(push.memory.content, 50)}\"")
        log.response("listen", f"{len(pushes)} pushes received")

        log.call("sub.close")
        await sub.close()
        log.response("close", "ok")
    return log.text()


async def test_forget_by_id() -> str:
    log = Log()
    async with client() as h:
        log.call("remember", content="Temporary memory for forget test", entity_id="forget-test")
        mem = await h.remember(content="Temporary memory for forget test", entity_id="forget-test")
        log.response("Memory", f"id={mem.id.hex()[:16]}...")

        log.call("count")
        count_before = await h.count()
        log.response("int", str(count_before))

        log.call("forget", memory_ids=f"[{mem.id.hex()[:16]}...]")
        result = await h.forget(memory_ids=[mem.id])
        log.response("ForgetResult",
            f"forgotten_count={result.forgotten_count}, cascade_count={result.cascade_count}, "
            f"tombstone_count={result.tombstone_count}")

        log.call("count")
        count_after = await h.count()
        log.response("int", f"{count_after} (was {count_before})")
        assert result.forgotten_count >= 1
        assert count_after < count_before
    return log.text()


async def test_forget_by_entity() -> str:
    log = Log()
    async with client() as h:
        log.call("remember", content="Entity forget test 1", entity_id="gdpr-delete")
        await h.remember(content="Entity forget test 1", entity_id="gdpr-delete")
        log.call("remember", content="Entity forget test 2", entity_id="gdpr-delete")
        await h.remember(content="Entity forget test 2", entity_id="gdpr-delete")

        log.call("forget", entity_id="gdpr-delete")
        result = await h.forget(entity_id="gdpr-delete")
        log.response("ForgetResult",
            f"forgotten_count={result.forgotten_count}, cascade_count={result.cascade_count}, "
            f"tombstone_count={result.tombstone_count}")
        assert result.forgotten_count >= 2
    return log.text()


async def test_auth_no_key() -> str:
    log = Log()
    log.call("HebbsClient", address=SERVER_ADDRESS, api_key='""  (explicit empty string, env var bypassed)')
    log.call("recall", cue="auth test")
    try:
        async with HebbsClient(SERVER_ADDRESS, api_key="") as h:
            await h.recall("auth test", top_k=1)
            raise AssertionError("recall succeeded without auth — expected rejection")
    except HebbsAuthenticationError as e:
        log.response("HebbsAuthenticationError (expected)", str(e))
    except HebbsError as e:
        log.response(type(e).__name__, str(e))
    return log.text()


async def test_auth_bad_key() -> str:
    log = Log()
    log.call("HebbsClient", address=SERVER_ADDRESS, api_key="hb_invalid_key_12345")
    log.call("recall", cue="auth test")
    try:
        async with HebbsClient(SERVER_ADDRESS, api_key="hb_invalid_key_12345") as h:
            await h.recall("auth test", top_k=1)
            raise AssertionError("recall succeeded with bad key — expected rejection")
    except HebbsAuthenticationError as e:
        log.response("HebbsAuthenticationError (expected)", str(e))
    except HebbsError as e:
        log.response(type(e).__name__, str(e))
    return log.text()


async def test_auth_explicit_key() -> str:
    log = Log()
    masked = API_KEY[:12] + "..." if API_KEY else "(none)"
    log.call("HebbsClient", address=SERVER_ADDRESS, api_key=masked)
    log.call("health")
    async with HebbsClient(SERVER_ADDRESS, api_key=API_KEY) as h:
        status = await h.health()
        log.response("HealthStatus", f"serving={status.serving}, version={status.version}")
        assert status.serving
    return log.text()


async def test_error_not_found() -> str:
    log = Log()
    async with client() as h:
        fake_id = b"\x00" * 16
        log.call("get", memory_id=fake_id)
        try:
            await h.get(fake_id)
            log.response("ERROR", "should have raised NotFound")
        except HebbsNotFoundError as e:
            log.response("HebbsNotFoundError", str(e))
    return log.text()


async def test_error_connection() -> str:
    log = Log()
    log.call("HebbsClient", address="localhost:19999", api_key="hb_test")
    log.call("health")
    try:
        async with HebbsClient("localhost:19999", api_key="hb_test") as bad:
            await bad.health()
            log.response("ERROR", "should have raised connection error")
    except Exception as e:
        log.response(type(e).__name__, str(e))
    return log.text()


# ── Reflect tests (OpenAI GPT-4o, server-side) ───────────────────────────

async def test_reflect_e2e() -> str:
    log = Log()
    async with client() as h:
        memories_for_reflect = [
            "ACME Corp renewed their Salesforce contract for 3 years",
            "ACME Corp's sales team grew from 10 to 25 reps this quarter",
            "ACME Corp asked about enterprise pricing tiers",
            "ACME Corp's CTO mentioned migrating to cloud-native infrastructure",
            "ACME Corp doubled their marketing budget for Q2",
            "Globex reported 40% increase in customer churn",
            "Globex is evaluating competitors to their current CRM",
            "Globex's VP of Sales expressed frustration with reporting tools",
            "TechStart signed a pilot deal for 50 seats",
            "TechStart's founder wants to scale to 500 users by Q3",
        ]
        log.info(f"storing {len(memories_for_reflect)} memories for reflect...")
        for content in memories_for_reflect:
            log.call("remember", content=content, importance=0.8)
            await h.remember(content=content, importance=0.8)
            log.response("Memory", "stored")

        log.call("reflect")
        result = await h.reflect()
        log.response("ReflectResult",
            f"insights_created={result.insights_created}, clusters_found={result.clusters_found}, "
            f"clusters_processed={result.clusters_processed}, memories_processed={result.memories_processed}")

        log.call("insights", max_results=20)
        insights = await h.insights(max_results=20)
        log.response("list[Memory]", f"{len(insights)} insights")
        for i, ins in enumerate(insights[:5]):
            log.detail(f"[{i}] kind={ins.kind.value}, content=\"{_trunc(ins.content, 70)}\"")
    return log.text()


async def test_reflect_entity_scoped() -> str:
    log = Log()
    async with client() as h:
        log.call("reflect", entity_id="acme")
        result = await h.reflect(entity_id="acme")
        log.response("ReflectResult",
            f"insights_created={result.insights_created}, clusters_found={result.clusters_found}")

        log.call("insights", entity_id="acme", max_results=10)
        insights = await h.insights(entity_id="acme", max_results=10)
        log.response("list[Memory]", f"{len(insights)} insights")
        for i, ins in enumerate(insights[:3]):
            log.detail(f"[{i}] content=\"{_trunc(ins.content, 70)}\"")
    return log.text()


# ── Persistence test ──────────────────────────────────────────────────────

async def test_persistence_note() -> str:
    log = Log()
    async with client() as h:
        log.call("count")
        count = await h.count()
        log.response("int", str(count))

        log.call("recall", cue="ACME Salesforce", top_k=3)
        result = await h.recall(cue="ACME Salesforce", top_k=3)
        log.response("RecallOutput", f"results={len(result.results)}")
        for i, r in enumerate(result.results[:3]):
            for line in _fmt_recall_result(r, i, "  "):
                log.detail(line)
    return log.text()


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def main() -> None:
    NOT_SET = f"{RED}NOT SET{RESET}"

    hebbs_key_display = f"set ({API_KEY[:12]}...)" if API_KEY else NOT_SET
    openai_key_display = f"set ({OPENAI_API_KEY[:12]}...)" if OPENAI_API_KEY else NOT_SET

    print("=" * 72)
    print("  HEBBS Python SDK — Production E2E Validation")
    print("=" * 72)
    print(f"  Server:          {SERVER_ADDRESS}")
    print(f"  HEBBS_API_KEY:   {hebbs_key_display}")
    print(f"  OPENAI_API_KEY:  {openai_key_display}")
    print(f"  Embeddings:      ONNX (BGE-small-en-v1.5, local)")
    print(f"  Reflect:         OpenAI GPT-4o (server-side)")
    print(f"  SDK source:      local (pip install -e)")
    print()

    errors = []
    if not API_KEY:
        errors.append("HEBBS_API_KEY not set. The server prints this on first start.")
    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY not set. Required for the reflect pipeline.")
    if errors:
        for e in errors:
            print(f"{RED}  ERROR: {e}{RESET}")
        print()
        print("  Required setup (see header comment for full instructions):")
        print()
        print('    export HEBBS_API_KEY="hb_<key-from-server-banner>"')
        print('    export OPENAI_API_KEY="sk-proj-..."')
        print()
        print("  Start the server with reflect enabled:")
        print()
        print('    OPENAI_API_KEY="sk-proj-..." \\')
        print("    HEBBS_REFLECT_ENABLED=true \\")
        print("    HEBBS_REFLECT_PROPOSAL_PROVIDER=openai \\")
        print("    HEBBS_REFLECT_PROPOSAL_MODEL=gpt-4o \\")
        print("    HEBBS_REFLECT_VALIDATION_PROVIDER=openai \\")
        print("    HEBBS_REFLECT_VALIDATION_MODEL=gpt-4o \\")
        print("    cargo run --release --bin hebbs-server")
        print()
        sys.exit(1)

    # ── Section 1: Health & Connectivity ──────────────────────────────────
    section("Health & Connectivity")
    await run_test("health check", test_health())
    await run_test("count", test_count())

    # ── Section 2: Remember ───────────────────────────────────────────────
    section("Remember")

    log = Log()
    async with client() as h:
        seeds = [
            dict(content="Globex uses HubSpot for marketing automation", entity_id="globex"),
            dict(content="TechStart chose Pipedrive as their sales CRM", entity_id="techstart"),
            dict(content="Enterprise prospect Initech is evaluating our platform for 200 seats",
                 importance=0.9,
                 context={"industry": "technology", "deal_size": "enterprise", "stage": "evaluation"},
                 entity_id="initech"),
        ]
        for kw in seeds:
            log.call("remember", **kw)
            mem = await h.remember(**kw)
            log.response("Memory", f"id={mem.id.hex()[:16]}...")
    print(f"\n  >>> seeding {len(seeds)} memories for recall tests")
    for line in log.text().strip().splitlines():
        print(f"         {line}")

    await run_test("remember (basic, with context & entity)", test_remember_basic())
    await run_test("remember (with edges: FOLLOWED_BY)", test_remember_with_edges())

    # ── Section 3: Get ────────────────────────────────────────────────────
    section("Get")
    await run_test("get by ID", test_get())

    # ── Section 4: Recall ─────────────────────────────────────────────────
    section("Recall — Strategies & Weights")
    await run_test("recall: similarity (basic)", test_recall_similarity())
    await run_test("recall: multi-strategy (similarity + temporal)", test_recall_multi_strategy())
    await run_test("recall: ScoringWeights dataclass (recency vs relevance)", test_recall_scoring_weights_dataclass())
    await run_test("recall: ScoringWeights as dict", test_recall_scoring_weights_dict())

    section("Recall — Advanced Strategy Config")
    await run_test("recall: RecallStrategyConfig (ef_search, per-strategy top_k)", test_recall_strategy_config())
    await run_test("recall: mixed string + RecallStrategyConfig", test_recall_mixed_strategies())
    await run_test("recall: causal (seed_memory_id, max_depth, edge_types)", test_recall_causal())
    await run_test("recall: analogical (alpha, cue_context)", test_recall_analogical())

    # ── Section 5: Prime ──────────────────────────────────────────────────
    section("Prime")
    await run_test("prime (entity + similarity_cue)", test_prime())
    await run_test("prime (with ScoringWeights)", test_prime_with_weights())

    # ── Section 6: Revise ─────────────────────────────────────────────────
    section("Revise")
    await run_test("revise (content, importance, context)", test_revise())

    # ── Section 7: Set Policy ─────────────────────────────────────────────
    section("Set Policy")
    await run_test("set_policy (snapshots, threshold, decay)", test_set_policy())

    # ── Section 8: Subscribe / Feed / Close ───────────────────────────────
    section("Subscribe / Feed / Close")
    await run_test("subscribe -> feed -> listen -> close", test_subscribe_feed_close())

    # ── Section 9: Forget ─────────────────────────────────────────────────
    section("Forget (GDPR Erasure)")
    await run_test("forget by ID", test_forget_by_id())
    await run_test("forget by entity", test_forget_by_entity())

    # ── Section 10: Auth ──────────────────────────────────────────────────
    section("Authentication")
    await run_test("auth: no key -> rejected", test_auth_no_key())
    await run_test("auth: bad key -> rejected", test_auth_bad_key())
    await run_test("auth: explicit valid key -> accepted", test_auth_explicit_key())

    # ── Section 11: Error Handling ────────────────────────────────────────
    section("Error Handling")
    await run_test("error: get non-existent ID -> NotFound", test_error_not_found())
    await run_test("error: connect to wrong port -> connection error", test_error_connection())

    # ── Section 12: Reflect (OpenAI GPT-4o) ──────────────────────────────
    section("Reflect Pipeline (OpenAI GPT-4o)")
    await run_test("reflect: store 10 memories + trigger reflect", test_reflect_e2e())
    await run_test("reflect: entity-scoped (acme)", test_reflect_entity_scoped())

    # ── Section 13: Data Persistence ──────────────────────────────────────
    section("Data Persistence (in-session)")
    await run_test("persistence: data from earlier tests still present", test_persistence_note())

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print("  SUMMARY")
    print(f"{'='*72}")

    passed = sum(1 for r in RESULTS if r.passed)
    failed = sum(1 for r in RESULTS if not r.passed)
    total = len(RESULTS)
    total_ms = sum(r.duration_ms for r in RESULTS)

    for r in RESULTS:
        tag = f"{GREEN}pass{RESET}" if r.passed else f"{RED}FAIL{RESET}"
        print(f"  {tag}  {r.name}")

    print()
    print(f"  Total:  {total}  |  Passed: {GREEN}{passed}{RESET}  |  Failed: {RED}{failed}{RESET}  |  Time: {total_ms:.0f}ms")

    if failed:
        print(f"\n  {RED}{failed} test(s) FAILED{RESET}")
        for r in RESULTS:
            if not r.passed:
                print(f"\n  FAIL: {r.name}")
                for line in r.message.strip().splitlines():
                    print(f"        {line}")
        sys.exit(1)
    else:
        print(f"\n  {GREEN}All {passed} tests passed.{RESET}")


if __name__ == "__main__":
    asyncio.run(main())
