# @hebbs/sdk — TypeScript SDK for HEBBS

Async gRPC client for the [HEBBS](https://hebbs.ai) cognitive memory engine. Node.js 18+ only.

## Install

```bash
npm install @hebbs/sdk
```

## Quick Start

```typescript
import { HebbsClient } from '@hebbs/sdk';

const client = new HebbsClient('localhost:6380', {
  apiKey: process.env.HEBBS_API_KEY,
});
await client.connect();

// Store a memory
const memory = await client.remember({
  content: 'User prefers dark mode',
  importance: 0.8,
  entityId: 'user-123',
});

// Recall by similarity
const { results } = await client.recall({
  cue: 'user preferences',
  strategies: ['similarity'],
});

// Prime a session
const primeOut = await client.prime({ entityId: 'user-123' });

// Real-time subscribe
const sub = await client.subscribe({ entityId: 'user-123' });
await sub.feed('Tell me about user preferences');
for await (const push of sub) {
  console.log('Surfaced:', push.memory.content);
}
await sub.close();

await client.close();
```

## API

### HebbsClient

| Method | Description |
|--------|------------|
| `connect()` | Open gRPC channel |
| `close()` | Close connection |
| `remember(params)` | Store a memory |
| `get(memoryId)` | Retrieve by ID |
| `recall(params)` | Multi-strategy recall |
| `prime(params)` | Session warm-up |
| `revise(memoryId, params)` | Update a memory |
| `forget(params)` | GDPR-compliant erasure |
| `setPolicy(params)` | Configure tenant policy |
| `subscribe(params)` | Real-time streaming |
| `reflect(params)` | Generate insights |
| `insights(params)` | Retrieve insights |
| `health()` | Server health check |
| `count()` | Total memory count |

### Recall Strategies

- **similarity** — semantic vector search
- **temporal** — time-ordered retrieval
- **causal** — cause-and-effect graph traversal
- **analogical** — cross-domain pattern matching

### Error Handling

All SDK errors extend `HebbsError`. Specific subclasses map to gRPC status codes:

| Error | gRPC Status |
|-------|-------------|
| `HebbsConnectionError` | Channel failure |
| `HebbsUnavailableError` | UNAVAILABLE |
| `HebbsTimeoutError` | DEADLINE_EXCEEDED |
| `HebbsNotFoundError` | NOT_FOUND |
| `HebbsInvalidArgumentError` | INVALID_ARGUMENT |
| `HebbsAuthenticationError` | UNAUTHENTICATED |
| `HebbsPermissionDeniedError` | PERMISSION_DENIED |
| `HebbsInternalError` | INTERNAL |
| `HebbsRateLimitError` | RESOURCE_EXHAUSTED |

## Testing

```bash
# Unit tests (no server needed)
npm test

# Integration tests (requires live server)
HEBBS_TEST_SERVER=localhost:6380 HEBBS_API_KEY=hb_... npm run test:integration

# E2E validation (requires live server + OpenAI for reflect)
HEBBS_API_KEY=hb_... OPENAI_API_KEY=sk-... npm run test:e2e
```

## Demo App

```bash
cd demo && npm install

# Interactive mode (mock LLM, no API keys)
npx tsx src/index.ts interactive --mock-llm

# Interactive mode (real OpenAI)
OPENAI_API_KEY=sk-... npx tsx src/index.ts interactive

# Run scripted scenarios
npx tsx src/index.ts scenarios --all --mock-llm
```

## License

Apache-2.0
