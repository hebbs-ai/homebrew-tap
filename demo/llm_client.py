"""Unified LLM client wrapping Gemini, OpenAI, Anthropic, and Ollama.

Provides a single interface for conversation generation and memory extraction.
Gemini is the default provider, using the google-genai SDK.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from demo.config import DemoConfig, LlmProviderConfig


@dataclass
class LlmResponse:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    model: str = ""
    provider: str = ""


@dataclass
class LlmStats:
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_latency_ms: float = 0.0
    calls_by_role: dict[str, int] = field(default_factory=dict)

    def record(self, response: LlmResponse, role: str) -> None:
        self.total_calls += 1
        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens
        self.total_latency_ms += response.latency_ms
        self.calls_by_role[role] = self.calls_by_role.get(role, 0) + 1

    @property
    def estimated_cost_usd(self) -> float:
        return (self.total_input_tokens * 2.50 + self.total_output_tokens * 10.00) / 1_000_000


class LlmClient:
    """Unified LLM client supporting Gemini, OpenAI, Anthropic, and Ollama."""

    def __init__(self, config: DemoConfig) -> None:
        self._config = config
        self._clients: dict[str, Any] = {}
        self.stats = LlmStats()

    # ── Provider clients (lazy init) ─────────────────────────────────────

    def _get_gemini_client(self) -> Any:
        if "gemini" not in self._clients:
            from google import genai
            prov = self._config.llm.gemini
            self._clients["gemini"] = genai.Client(api_key=prov.api_key)
        return self._clients["gemini"]

    def _get_gemini_vertex_client(self) -> Any:
        if "gemini_vertex" not in self._clients:
            from google import genai
            prov = self._config.llm.gemini_vertex
            self._clients["gemini_vertex"] = genai.Client(
                vertexai=True,
                project=prov.project,
                location=prov.location,
            )
        return self._clients["gemini_vertex"]

    def _get_openai_client(self) -> Any:
        if "openai" not in self._clients:
            import openai
            prov = self._config.llm.openai
            self._clients["openai"] = openai.OpenAI(api_key=prov.api_key)
        return self._clients["openai"]

    def _get_anthropic_client(self) -> Any:
        if "anthropic" not in self._clients:
            import anthropic
            prov = self._config.llm.anthropic
            self._clients["anthropic"] = anthropic.Anthropic(api_key=prov.api_key)
        return self._clients["anthropic"]

    # ── Provider call implementations ────────────────────────────────────

    def _call_gemini(
        self, messages: list[dict[str, str]], model: str, temperature: float = 0.7,
    ) -> LlmResponse:
        client = self._get_gemini_client()

        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        non_system = [m for m in messages if m["role"] != "system"]

        contents = []
        for m in non_system:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})

        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

        config = {"temperature": temperature}
        if system_parts:
            config["system_instruction"] = "\n\n".join(system_parts)

        t0 = time.perf_counter()
        resp = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        elapsed = (time.perf_counter() - t0) * 1000

        content = resp.text or ""
        input_tokens = getattr(resp.usage_metadata, "prompt_token_count", 0) if resp.usage_metadata else 0
        output_tokens = getattr(resp.usage_metadata, "candidates_token_count", 0) if resp.usage_metadata else 0

        return LlmResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=elapsed,
            model=model,
            provider="gemini",
        )

    def _call_openai(
        self, messages: list[dict[str, str]], model: str, temperature: float = 0.7,
    ) -> LlmResponse:
        client = self._get_openai_client()
        t0 = time.perf_counter()
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=temperature,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        choice = resp.choices[0]
        usage = resp.usage
        return LlmResponse(
            content=choice.message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_ms=elapsed,
            model=model,
            provider="openai",
        )

    def _call_anthropic(
        self, messages: list[dict[str, str]], model: str, temperature: float = 0.7,
    ) -> LlmResponse:
        client = self._get_anthropic_client()
        system_parts = []
        non_system = []
        for m in messages:
            if m["role"] == "system":
                system_parts.append(m["content"])
            else:
                non_system.append(m)
        if not non_system:
            non_system = [{"role": "user", "content": "Hello"}]

        t0 = time.perf_counter()
        resp = client.messages.create(
            model=model,
            system="\n\n".join(system_parts) if system_parts else "",
            messages=non_system,
            temperature=temperature,
            max_tokens=1024,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        content = resp.content[0].text if resp.content else ""
        return LlmResponse(
            content=content,
            input_tokens=resp.usage.input_tokens if resp.usage else 0,
            output_tokens=resp.usage.output_tokens if resp.usage else 0,
            latency_ms=elapsed,
            model=model,
            provider="anthropic",
        )

    def _call_ollama(
        self, messages: list[dict[str, str]], model: str, temperature: float = 0.7,
    ) -> LlmResponse:
        import urllib.request
        base_url = self._config.llm.ollama.base_url.rstrip("/")
        payload = json.dumps({
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }).encode()
        req = urllib.request.Request(
            f"{base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read())
        elapsed = (time.perf_counter() - t0) * 1000
        content = body.get("message", {}).get("content", "")
        return LlmResponse(
            content=content,
            input_tokens=body.get("prompt_eval_count", 0),
            output_tokens=body.get("eval_count", 0),
            latency_ms=elapsed,
            model=model,
            provider="ollama",
        )

    def _call_gemini_vertex(
        self, messages: list[dict[str, str]], model: str, temperature: float = 0.7,
    ) -> LlmResponse:
        client = self._get_gemini_vertex_client()

        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        non_system = [m for m in messages if m["role"] != "system"]

        contents = []
        for m in non_system:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})

        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

        config = {"temperature": temperature}
        if system_parts:
            config["system_instruction"] = "\n\n".join(system_parts)

        t0 = time.perf_counter()
        resp = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        elapsed = (time.perf_counter() - t0) * 1000

        content = resp.text or ""
        input_tokens = getattr(resp.usage_metadata, "prompt_token_count", 0) if resp.usage_metadata else 0
        output_tokens = getattr(resp.usage_metadata, "candidates_token_count", 0) if resp.usage_metadata else 0

        return LlmResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=elapsed,
            model=model,
            provider="gemini-vertex",
        )

    # ── Dispatch ─────────────────────────────────────────────────────────

    def _dispatch(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
    ) -> LlmResponse:
        dispatch_map = {
            "gemini": self._call_gemini,
            "gemini-vertex": self._call_gemini_vertex,
            "gemini_vertex": self._call_gemini_vertex,
            "openai": self._call_openai,
            "anthropic": self._call_anthropic,
            "ollama": self._call_ollama,
        }
        fn = dispatch_map.get(provider)
        if fn is None:
            raise ValueError(f"Unknown LLM provider: {provider}")
        return fn(messages, model, temperature)

    def conversation(self, messages: list[dict[str, str]]) -> LlmResponse:
        """Generate a conversation response using the configured conversation LLM."""
        resp = self._dispatch(
            self._config.llm.conversation_provider,
            self._config.llm.conversation_model,
            messages,
            temperature=0.7,
        )
        self.stats.record(resp, "conversation")
        return resp

    def extract_memories(self, messages: list[dict[str, str]]) -> LlmResponse:
        """Extract structured memories from a conversation turn."""
        resp = self._dispatch(
            self._config.llm.extraction_provider,
            self._config.llm.extraction_model,
            messages,
            temperature=0.1,
        )
        self.stats.record(resp, "extraction")
        return resp

    def simulate_prospect(self, messages: list[dict[str, str]]) -> LlmResponse:
        """Simulate a prospect's response in scripted mode."""
        resp = self._dispatch(
            self._config.llm.conversation_provider,
            self._config.llm.conversation_model,
            messages,
            temperature=0.8,
        )
        self.stats.record(resp, "simulation")
        return resp


class MockLlmClient(LlmClient):
    """Mock LLM client for testing without API keys."""

    def __init__(self, config: DemoConfig | None = None) -> None:
        super().__init__(config or DemoConfig())
        self._canned_conversation = (
            "That's a great question. Based on what I've seen with similar companies, "
            "I'd recommend we start with a discovery call to understand your specific needs. "
            "What's your biggest pain point right now?"
        )
        self._canned_extraction = json.dumps({
            "memories": [
                {
                    "content": "Prospect expressed interest in the product",
                    "importance": 0.7,
                    "context": {"topic": "general", "stage": "discovery", "sentiment": "positive"},
                    "edge_to_previous": False,
                }
            ],
            "skip_reason": None,
        })
        self._call_count = 0

    def _dispatch(
        self, provider: str, model: str, messages: list[dict[str, str]], temperature: float = 0.7,
    ) -> LlmResponse:
        self._call_count += 1
        last_user = ""
        for m in reversed(messages):
            if m["role"] == "user":
                last_user = m["content"]
                break

        is_extraction = any("memory extraction" in m.get("content", "").lower() for m in messages)
        content = self._canned_extraction if is_extraction else self._canned_conversation

        return LlmResponse(
            content=content,
            input_tokens=len(last_user.split()) * 2,
            output_tokens=len(content.split()) * 2,
            latency_ms=5.0,
            model="mock",
            provider="mock",
        )
