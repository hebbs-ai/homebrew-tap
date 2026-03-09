<p align="center">
  <img src="assets/logo-icon.png" alt="HEBBS logo" width="128" height="128" />
</p>

# HEBBS

> **HEBBS is under active development.** If you'd like to use it now, please reach out: [Quick chat with the founder](https://buxo.ai/parag/hebbsai-quick-chat-with-founder)

**The memory engine for AI agents.** One binary. Sub-10ms recall. Agents that actually learn.

HEBBS is a memory primitive purpose-built for AI agents. It replaces the patchwork of vector databases, key-value stores, and graph databases that agent developers cobble together today with a single, fast, embeddable engine.

Vector search tells your agent what's *similar*. HEBBS tells your agent what *happened*, what *caused* it, and what *worked before*.

```bash
curl -sSf https://hebbs.ai/install | sh
hebbs-server
```

---

## Why HEBBS Exists

Current "memory" solutions for AI agents are storage dressed up as intelligence. They solve narrow retrieval problems but miss the deeper cognitive capabilities agents actually need.

| Approach | What it does | What it misses |
|---|---|---|
| Conversation History | Append-only log, truncate at window | No importance weighting, no consolidation, context just gets cut |
| Vector DB / RAG | Similarity retrieval over chunks | One retrieval path, no decay, no structural consolidation |
| Redis / KV Cache | Fast storage of computed results | No semantic understanding, manual key management for everything |
| Knowledge Graphs | Structured relationships | Hard to populate automatically, rigid schema, no temporal context |

HEBBS moves beyond storage into cognition: importance-driven encoding, multi-path recall, episodic-to-semantic consolidation, native decay and reinforcement, and revision over append.

---

## Quick Start

### Install

```bash
# macOS (Apple Silicon) / Linux (x86_64 / aarch64)
curl -sSf https://hebbs.ai/install | sh
export PATH="$HOME/.hebbs/bin:$PATH"
```

Pin a version or change the install directory:

```bash
HEBBS_VERSION=v0.1.0 curl -sSf https://hebbs.ai/install | sh
HEBBS_INSTALL_DIR=/usr/local/bin curl -sSf https://hebbs.ai/install | sh
```

### Start the Server

```bash
hebbs-server                      # start on localhost:6380 (gRPC) + :6381 (HTTP)
hebbs-cli remember "hello world"  # store a memory
hebbs-cli recall "hello"          # recall it
```

### Connect from Python

```bash
pip install hebbs
```

```python
from hebbs import HebbsClient

client = HebbsClient("localhost:6380")
```

### Connect from TypeScript

```bash
npm install @hebbs/sdk
```

```typescript
import { HebbsClient } from '@hebbs/sdk';

const client = new HebbsClient('localhost:6380', { apiKey: process.env.HEBBS_API_KEY });
await client.connect();
```

### Remember

<details>
<summary>Python</summary>

```python
await client.remember(
    content="Prospect mentioned competitor contract expires March 15",
    importance=0.95,
    entity_id="acme",
    context={"stage": "discovery", "signal": "urgency"},
)
```

</details>

<details>
<summary>TypeScript</summary>

```typescript
await client.remember({
    content: 'Prospect mentioned competitor contract expires March 15',
    importance: 0.95,
    entityId: 'acme',
    context: { stage: 'discovery', signal: 'urgency' },
});
```

</details>

### Recall

<details>
<summary>Python</summary>

```python
# What happened with this prospect? (Temporal)
history = await client.recall(cue="acme engagement", strategy="temporal", entity_id="acme")

# How should I handle this objection? (Similarity)
responses = await client.recall(cue="we built this in-house", strategy="similarity")

# Why did the last similar deal fall through? (Causal)
causes = await client.recall(cue="deal lost after pricing", strategy="causal")

# I've never sold to healthcare -- what's transferable? (Analogical)
patterns = await client.recall(cue="healthcare compliance objection", strategy="analogical")
```

</details>

<details>
<summary>TypeScript</summary>

```typescript
// What happened with this prospect? (Temporal)
const history = await client.recall({ cue: 'acme engagement', strategies: ['temporal'], entityId: 'acme' });

// How should I handle this objection? (Similarity)
const responses = await client.recall({ cue: 'we built this in-house', strategies: ['similarity'] });

// Why did the last similar deal fall through? (Causal)
const causes = await client.recall({ cue: 'deal lost after pricing', strategies: ['causal'] });

// I've never sold to healthcare -- what's transferable? (Analogical)
const patterns = await client.recall({ cue: 'healthcare compliance objection', strategies: ['analogical'] });
```

</details>

### Subscribe (Real-time)

<details>
<summary>Python</summary>

```python
sub = await client.subscribe(entity_id="acme", confidence_threshold=0.8)
await sub.feed("They just mentioned compliance concerns again")
async for push in sub:
    inject_into_agent_context(push.memory)
```

</details>

<details>
<summary>TypeScript</summary>

```typescript
const sub = await client.subscribe({ entityId: 'acme', confidenceThreshold: 0.8 });
await sub.feed('They just mentioned compliance concerns again');
for await (const push of sub) {
    injectIntoAgentContext(push.memory);
}
```

</details>

### Reflect

<details>
<summary>Python</summary>

```python
result = await client.reflect()
insights = await client.insights(entity_id="acme", max_results=10)
```

</details>

<details>
<summary>TypeScript</summary>

```typescript
const result = await client.reflect();
const insights = await client.insights({ entityId: 'acme', maxResults: 10 });
```

</details>

### Reference Demos

The [hebbs-python](https://github.com/hebbs-ai/hebbs-python) repo includes a full AI Sales Intelligence Agent demo with 7 scripted scenarios, 5 LLM providers, and Rich terminal panels showing every HEBBS operation in real time.

```bash
pip install hebbs[demo]
hebbs-demo interactive --config gemini-vertex --verbosity verbose
hebbs-demo scenarios --all
```

The [hebbs-typescript](https://github.com/hebbs-ai/hebbs-typescript) repo includes an equivalent TypeScript demo with 3 scripted scenarios and an interactive mode.

```bash
cd hebbs-typescript/demo && npm install
npx tsx src/index.ts interactive --mock-llm
npx tsx src/index.ts scenarios --all --mock-llm
```

---

## The API

Nine operations. Three groups.

### Write

| Operation | What it does |
|---|---|
| `remember(experience, importance, context)` | Store a memory with importance scoring and structured context. |
| `revise(memory_id, new_evidence)` | Update a belief. Replaces, not appends. |
| `forget(criteria)` | Prune by staleness, irrelevance, or compliance (GDPR). |

### Read

| Operation | What it does |
|---|---|
| `recall(cue, strategy)` | Retrieve memories by similarity, time, causation, or analogy. |
| `prime(context)` | Pre-load relevant context before an agent turn. For frameworks. |
| `subscribe(input_stream, threshold)` | Real-time push. The engine surfaces memories as they become relevant. |

### Consolidate

| Operation | What it does |
|---|---|
| `reflect_policy(config)` | Configure automatic background consolidation triggers. |
| `reflect(scope)` | Manual trigger for on-demand consolidation. |
| `insights(filter)` | Query distilled knowledge produced by reflection. |

---

## Four Recall Strategies

Most memory systems give you one retrieval mode: similarity search. HEBBS gives you four.

| Strategy | Question it answers | Example |
|---|---|---|
| **Similarity** | "What looks like this?" | Finding relevant objection responses |
| **Temporal** | "What happened, in order?" | Reconstructing a prospect's full history |
| **Causal** | "What led to this outcome?" | Understanding why a deal was lost |
| **Analogical** | "What's structurally similar in a different domain?" | Applying finance patterns to healthcare |

All four run against a single engine. No fan-out across services.

---

## Tunable Scoring

Every recall result is ranked by a composite score that blends four signals:

| Signal | What it captures | Default weight |
|---|---|---|
| **Relevance** | Semantic similarity to the query | 0.50 |
| **Recency** | How recently the memory was created | 0.20 |
| **Importance** | Salience set at encoding time | 0.20 |
| **Reinforcement** | How often the memory has been recalled | 0.10 |

Pass `scoring_weights` to shift the blend for any recall or prime call:

<details>
<summary>Python</summary>

```python
# Pure semantic match -- ignore time, importance, and reinforcement
results = await client.recall(
    cue="competitor pricing objection",
    strategies=["similarity"],
    scoring_weights=ScoringWeights(w_relevance=1.0, w_recency=0.0, w_importance=0.0, w_reinforcement=0.0),
)

# "What just happened?" -- bias toward recent memories
results = await client.recall(
    cue="latest updates",
    strategies=["similarity"],
    scoring_weights=ScoringWeights(w_relevance=0.2, w_recency=0.8, w_importance=0.0, w_reinforcement=0.0),
)
```

</details>

<details>
<summary>TypeScript</summary>

```typescript
// Pure semantic match -- ignore time, importance, and reinforcement
const results = await client.recall({
    cue: 'competitor pricing objection',
    strategies: ['similarity'],
    scoringWeights: { wRelevance: 1.0, wRecency: 0.0, wImportance: 0.0, wReinforcement: 0.0 },
});

// "What just happened?" -- bias toward recent memories
const recent = await client.recall({
    cue: 'latest updates',
    strategies: ['similarity'],
    scoringWeights: { wRelevance: 0.2, wRecency: 0.8, wImportance: 0.0, wReinforcement: 0.0 },
});
```

</details>

Omit `scoring_weights` for the default composite blend. Works across Python, TypeScript, CLI (`--weights 1:0:0:0`), and REST API.

Full documentation: [docs.hebbs.ai/concepts/recall-strategies](https://docs.hebbs.ai/concepts/recall-strategies/)

---

## Performance

Benchmarked on a single `c6g.large` instance (2 vCPU, 4GB RAM) with 10M stored memories.

| Operation | p50 | p99 |
|---|---|---|
| `remember` | 0.8ms | 4ms |
| `recall` (similarity) | 2ms | 8ms |
| `recall` (temporal) | 0.5ms | 2ms |
| `recall` (causal) | 4ms | 12ms |
| `recall` (multi-strategy) | 6ms | 18ms |
| `subscribe` (event-to-push) | 1ms | 5ms |

### Scalability

| Memories | `recall` p99 (similarity) | `recall` p99 (temporal) |
|---|---|---|
| 100K | 3ms | 0.6ms |
| 1M | 5ms | 0.8ms |
| 10M | 8ms | 1.2ms |
| 100M | 12ms | 2.0ms |

---

## Architecture

```text
──────────────────────────────────────────────────────────
                     Client SDKs
             Python  │  TypeScript  │  Rust
──────────────────────────────────────────────────────────
                gRPC  │  HTTP/REST
──────────────────────────────────────────────────────────

                  Core Engine (Rust)

  ┌────────────┐ ┌────────────┐ ┌──────────────────┐
  │  Remember   │ │   Recall   │ │ Reflect Pipeline │
  │  Engine     │ │   Engine   │ │ (background)     │
  │             │ │            │ │                  │
  │ • encode    │ │ • prime    │ │ • cluster (Rust) │
  │ • score     │ │ • query    │ │ • propose (LLM)  │
  │ • index     │ │ • subscribe│ │ • validate (LLM) │
  │ • decay     │ │ • merge    │ │ • store insights │
  └─────┬───────┘ └─────┬──────┘ └────────┬─────────┘
        │               │                 │
  ┌─────┴───────────────┴─────────────────┴──────────┐
  │              Index Layer                         │
  │   Temporal (B-tree) │ Vector (HNSW) │ Graph      │
  └──────────────────────┬───────────────────────────┘
                         │
  ┌──────────────────────┴───────────────────────────┐
  │         Storage Engine (RocksDB)                 │
  │         Column Families per index type           │
  └──────────────────────────────────────────────────┘

  ┌───────────────────────┐  ┌────────────────────────┐
  │ Embedding Engine      │  │ LLM Provider Interface │
  │ (ONNX Runtime,        │  │ (Anthropic, OpenAI,    │
  │  built-in default)    │  │  Ollama -- pluggable)  │
  └───────────────────────┘  └────────────────────────┘
```

**Built with:**
- **Rust** -- no GC pauses, single static binary, C-level performance
- **RocksDB** -- embedded LSM storage, proven by TiKV and CockroachDB
- **HNSW** -- logarithmic-scaling vector index for similarity and analogical recall
- **ONNX Runtime** -- built-in CPU embeddings (<5ms), zero external API dependencies
- **gRPC** -- bidirectional streaming for real-time `subscribe` channels

---

## Deployment

### Standalone Server (the Redis model)

```bash
hebbs-server                                   # defaults: gRPC :6380, HTTP :6381, data ./hebbs-data
HEBBS_AUTH_ENABLED=true hebbs-server            # with API key authentication
```

### Embedded Library (the SQLite model)

```python
from hebbs import HEBBS

e = HEBBS.open("./agent-memory")  # No separate process
e.remember(...)
```

### Edge Mode (robots, laptops, workstations)

Same API, different configuration. A Jetson Orin, MacBook, or Intel laptop runs the complete engine including local reflection with on-device LLMs.

---

## Client Libraries

| Language | Package | Status |
|---|---|---|
| Python | `pip install hebbs` | Stable (gRPC + embedded via PyO3) |
| TypeScript | `npm install @hebbs/sdk` | Stable (gRPC, Node.js 18+) |
| Rust | `hebbs` crate (direct) | Stable |
| Go | `go get hebbs.ai/client` | Planned |

---

## Use Cases

**Voice Sales Agents** -- The most demanding test for agentic memory. A sales agent that remembers prospect history across calls, handles objections with proven responses, and learns which pitches convert over time.

**Customer Support** -- Recall past tickets for the same customer, surface solutions from similar issues, reduce escalations through consolidated troubleshooting knowledge.

**Coding Agents** -- Remember what approaches worked in this codebase, recall past debugging sessions, avoid repeating failed strategies.

**Robotics** -- Warehouse robots that learn navigation patterns, share blocked-aisle knowledge across a fleet, and reflect on operational efficiency. All running fully offline on edge hardware.

**Personal Assistants** -- Remember preferences, learn routines, pick up context across conversations.

---

## Contributing

We welcome contributions across the stack. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

All contributors must sign our [Contributor License Agreement](CLA.md) before their first PR can be merged. It's a one-time thing -- the CLA bot will walk you through it on your first pull request.

---

## License

HEBBS uses a dual-license model.

**The engine** (hebbs-core, hebbs-storage, hebbs-index, hebbs-embed, hebbs-reflect, hebbs-server, hebbs-cli) is licensed under [BSL 1.1](LICENSE-BSL). This is the same license used by CockroachDB, Sentry, and Terraform. You can use it freely in production. You can read the source, modify it, self-host it, build on top of it. The only thing you can't do is take HEBBS and offer it as a hosted service to third parties. Every version converts to Apache 2.0 after four years.

**Client libraries and protocol definitions** (hebbs-client, hebbs-proto, hebbs-ffi) are licensed under [Apache 2.0](LICENSE-APACHE). The code you import into your projects is fully open source with no restrictions.

Educational institutions and non-profit organizations can use the full engine without restriction.

If you need a different licensing arrangement, reach out at parag@hebbs.ai.

---

*Agents deserve better than a vector database and a prayer.*
