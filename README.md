# HEBBS Python SDK

Python client for the [HEBBS](https://hebbs.ai) cognitive memory engine. Provides an async gRPC client with a Pythonic interface -- no protobuf in the public API.

HEBBS gives your AI agents real memory: sub-10ms writes, sub-10ms recalls, four recall strategies, entity-scoped multitenancy, and GDPR-compliant erasure. This SDK wraps the gRPC API in idiomatic Python so you can integrate HEBBS in minutes.

## Quick Start

### 1. Install the HEBBS Server

```bash
curl -sSf https://hebbs.ai/install | sh
```

This installs `hebbs-server`, `hebbs-cli`, and `hebbs-bench` to `~/.hebbs/bin/`. The server runs BGE-small-en-v1.5 (ONNX) for embeddings internally -- no external embedding API needed.

### 2. Start the Server

```bash
hebbs-server
```

The server listens on `localhost:6380` (gRPC) by default.

### 3. Install the Python SDK

```bash
pip install hebbs
```

To include the demo app and all LLM providers:

```bash
pip install hebbs[demo]
```

### 4. Use the SDK

```python
import asyncio
from hebbs import HebbsClient

async def main():
    # Pass api_key directly, or set HEBBS_API_KEY env var
    async with HebbsClient("localhost:6380", api_key="hb_...") as h:
        # Store a memory (entity-scoped)
        mem = await h.remember(
            content="Acme Corp uses Salesforce CRM and has 200 engineers",
            importance=0.8,
            context={"company": "Acme Corp", "topic": "tech_stack"},
            entity_id="acme_corp",
        )

        # Recall by semantic similarity (entity-isolated)
        results = await h.recall(
            cue="What CRM does Acme use?",
            strategies=["similarity"],
            top_k=5,
            entity_id="acme_corp",
        )
        for r in results.results:
            print(f"  [{r.score:.2f}] {r.memory.content}")

        # Prime a session (load relevant context for an entity)
        prime = await h.prime(entity_id="acme_corp", max_memories=50)
        print(f"Primed {len(prime.results)} memories")

        # Generate insights from memory clusters (uses LLM)
        reflect = await h.reflect(entity_id="acme_corp")
        print(f"Created {reflect.insights_created} insights")

        # GDPR-compliant cryptographic erasure
        forget = await h.forget(entity_id="acme_corp")
        print(f"Forgot {forget.forgotten_count} memories")

asyncio.run(main())
```

## Entity Isolation (Multitenancy)

All HEBBS operations are scoped by `entity_id`. Memories stored under one entity are never returned when querying a different entity -- this applies to all four recall strategies, prime, reflect, and insights. No configuration needed; isolation is structural.

```python
await h.remember(content="Uses Salesforce", entity_id="acme_corp")
await h.remember(content="Uses HubSpot", entity_id="techflow_inc")

results = await h.recall(cue="What CRM?", entity_id="acme_corp")
# Only returns "Uses Salesforce" -- techflow_inc data is invisible
```

## Demo App

The demo ships an AI sales agent ("Atlas") that uses HEBBS for memory-augmented conversations. It shows every HEBBS operation in real-time panels: remember latency, recall scores, prime context, and session metrics.

### Configure an LLM

```bash
# Pick one:
export GEMINI_API_KEY="your-key"        # Gemini (default)
export OPENAI_API_KEY="your-key"        # OpenAI
export ANTHROPIC_API_KEY="your-key"     # Anthropic
# Or use Ollama / mock (no keys needed)
```

### Run Interactive Chat

```bash
hebbs-demo interactive
```

Or specify a config:

```bash
hebbs-demo interactive --config gemini-vertex  # Gemini via Vertex AI
hebbs-demo interactive --config gemini         # Gemini via API key
hebbs-demo interactive --config openai         # GPT-4o
hebbs-demo interactive --config local          # Ollama (no API key)
hebbs-demo interactive --mock-llm              # Mock LLM (no API key)
```

Switch entities mid-session to demonstrate multitenancy:

```bash
hebbs-demo interactive --entity acme_corp
# In-session: /session techflow_inc
```

### Session Summary

On exit, the CLI prints a session summary showing both LLM and HEBBS engine latency side by side:

```
┃ Metric             ┃                          Value ┃
│ Total LLM latency  │                       28,039ms │
│ HEBBS remember     │      4.5ms avg (18ms total)    │
│ HEBBS recall       │      5.5ms avg (22ms total)    │
│ HEBBS prime        │      3.2ms avg (3ms total)     │
```

### Run Scenarios

```bash
hebbs-demo scenarios --all                # Run all 7 scenarios
hebbs-demo scenarios --run discovery_call # Run a specific one
```

Available scenarios: `discovery_call`, `objection_handling`, `multi_session`, `reflect_learning`, `subscribe_realtime`, `forget_gdpr`, `multi_entity`.

## SDK Reference

### HebbsClient

| Method | Description |
|--------|-------------|
| `remember(content, importance, context, entity_id)` | Store a memory |
| `get(memory_id)` | Retrieve a memory by ID |
| `recall(cue, strategies, top_k, entity_id)` | Multi-strategy recall |
| `prime(entity_id, max_memories, similarity_cue)` | Session warm-up |
| `revise(memory_id, content, importance, context)` | Update a memory |
| `forget(entity_id, memory_ids)` | GDPR-compliant erasure |
| `set_policy(...)` | Configure tenant policies |
| `subscribe(entity_id, confidence_threshold)` | Real-time memory surfacing |
| `reflect(entity_id)` | Generate insights from clusters |
| `insights(entity_id, max_results)` | Retrieve accumulated insights |
| `health()` | Server health check |
| `count()` | Total memory count |

### Recall Strategies

- **similarity** -- semantic vector search (HNSW, entity-filtered)
- **temporal** -- time-ordered retrieval
- **causal** -- cause-and-effect graph traversal (entity-filtered)
- **analogical** -- cross-domain pattern matching (entity-filtered)

### LLM Providers

| Provider | Config | Env Variable |
|----------|--------|--------------|
| Gemini (Vertex AI) | `gemini-vertex.toml` | `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_PROJECT` |
| Gemini (API key) | `gemini.toml` | `GEMINI_API_KEY` |
| OpenAI | `openai.toml` | `OPENAI_API_KEY` |
| Anthropic | (custom toml) | `ANTHROPIC_API_KEY` |
| Ollama | `local.toml` | (none -- Ollama must be running) |

## Requirements

- Python >= 3.10
- A running HEBBS server (gRPC on port 6380)

## Contributing

Contributions are welcome. By submitting a pull request, you agree to the [Contributor License Agreement](CLA.md).

## License

Copyright 2025 Parag Arora. Apache 2.0 -- see [LICENSE](LICENSE).
