"""Tests for the LLM client mock and dispatch."""

from __future__ import annotations

from demo.config import DemoConfig
from demo.llm_client import MockLlmClient


def test_mock_client_conversation():
    client = MockLlmClient()
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello there!"},
    ]
    resp = client.conversation(messages)
    assert resp.content
    assert resp.provider == "mock"
    assert resp.model == "mock"
    assert resp.latency_ms > 0


def test_mock_client_extraction():
    client = MockLlmClient()
    messages = [
        {"role": "system", "content": "You are a memory extraction system."},
        {"role": "user", "content": "Prospect said something interesting."},
    ]
    resp = client.extract_memories(messages)
    assert resp.content
    assert '"memories"' in resp.content


def test_mock_client_stats_tracking():
    client = MockLlmClient()
    messages = [{"role": "user", "content": "Hi"}]
    client.conversation(messages)
    client.conversation(messages)
    client.extract_memories(messages)
    assert client.stats.total_calls == 3
    assert client.stats.calls_by_role["conversation"] == 2
    assert client.stats.calls_by_role["extraction"] == 1


def test_mock_client_simulates_prospect():
    client = MockLlmClient()
    messages = [{"role": "user", "content": "Tell me about your product."}]
    resp = client.simulate_prospect(messages)
    assert resp.content
    assert client.stats.calls_by_role["simulation"] == 1


def test_dispatch_unknown_provider():
    cfg = DemoConfig.default()
    from demo.llm_client import LlmClient
    client = LlmClient(cfg)
    import pytest
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        client._dispatch("nonexistent", "model", [{"role": "user", "content": "hi"}])
