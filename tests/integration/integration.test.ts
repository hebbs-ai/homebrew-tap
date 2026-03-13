/**
 * Integration tests for the HEBBS TypeScript SDK.
 *
 * Requires a running HEBBS server. Skipped if HEBBS_TEST_SERVER is not set.
 * Run with: HEBBS_TEST_SERVER=localhost:6380 npm run test:integration
 */

import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import {
  HebbsClient,
  MemoryKind,
  EdgeType,
  HebbsNotFoundError,
  HebbsAuthenticationError,
  type RecallStrategyConfig,
  type ScoringWeights,
} from '../../src/index.js';

const SERVER = process.env['HEBBS_TEST_SERVER'] ?? process.env['HEBBS_ADDRESS'];
const API_KEY = process.env['HEBBS_API_KEY'];

const shouldRun = !!SERVER;

describe.skipIf(!shouldRun)('Integration: Health', () => {
  let client: HebbsClient;

  beforeAll(async () => {
    client = new HebbsClient(SERVER!, { apiKey: API_KEY });
    await client.connect();
  });
  afterAll(async () => client?.close());

  it('health check returns serving status', async () => {
    const status = await client.health();
    expect(status.serving).toBe(true);
    expect(status.version).toBeTruthy();
  });

  it('count returns a number', async () => {
    const n = await client.count();
    expect(typeof n).toBe('number');
  });
});

describe.skipIf(!shouldRun)('Integration: Remember', () => {
  let client: HebbsClient;

  beforeAll(async () => {
    client = new HebbsClient(SERVER!, { apiKey: API_KEY });
    await client.connect();
  });
  afterAll(async () => client?.close());

  it('stores a basic memory', async () => {
    const mem = await client.remember({
      content: 'TS SDK integration test memory',
      importance: 0.7,
      entityId: 'ts-test',
    });

    expect(mem.id).toBeInstanceOf(Buffer);
    expect(mem.id.length).toBeGreaterThan(0);
    expect(mem.content).toBe('TS SDK integration test memory');
    expect(mem.kind).toBe(MemoryKind.EPISODE);
  });

  it('stores a memory with context', async () => {
    const mem = await client.remember({
      content: 'Memory with context',
      context: { tool: 'typescript', version: 1 },
      entityId: 'ts-test',
    });

    expect(mem.context).toHaveProperty('tool');
  });

  it('stores a memory with edges', async () => {
    const mem1 = await client.remember({
      content: 'First event in chain',
      entityId: 'ts-test',
    });

    const mem2 = await client.remember({
      content: 'Second event in chain',
      entityId: 'ts-test',
      edges: [
        {
          targetId: mem1.id,
          edgeType: EdgeType.FOLLOWED_BY,
          confidence: 0.9,
        },
      ],
    });

    expect(mem2.id).not.toEqual(mem1.id);
  });
});

describe.skipIf(!shouldRun)('Integration: Get', () => {
  let client: HebbsClient;

  beforeAll(async () => {
    client = new HebbsClient(SERVER!, { apiKey: API_KEY });
    await client.connect();
  });
  afterAll(async () => client?.close());

  it('retrieves a memory by ID', async () => {
    const stored = await client.remember({
      content: 'Memory for get test',
      importance: 0.5,
    });

    const retrieved = await client.get(stored.id);
    expect(retrieved.content).toBe('Memory for get test');
    expect(retrieved.id.equals(stored.id)).toBe(true);
  });

  it('throws NotFoundError for missing ID', async () => {
    const fakeId = Buffer.alloc(16);
    await expect(client.get(fakeId)).rejects.toThrow(HebbsNotFoundError);
  });
});

describe.skipIf(!shouldRun)('Integration: Recall', () => {
  let client: HebbsClient;

  beforeAll(async () => {
    client = new HebbsClient(SERVER!, { apiKey: API_KEY });
    await client.connect();
    await client.remember({
      content: 'ACME Corp uses Salesforce for CRM',
      importance: 0.8,
      context: { industry: 'technology', tool: 'salesforce' },
      entityId: 'acme',
    });
  });
  afterAll(async () => client?.close());

  it('recalls by similarity', async () => {
    const result = await client.recall({ cue: 'What CRM does ACME use?' });
    expect(result.results.length).toBeGreaterThan(0);
  });

  it('recalls with multiple strategies', async () => {
    const result = await client.recall({
      cue: 'ACME technology',
      strategies: ['similarity', 'temporal'],
      entityId: 'acme',
    });
    expect(result.results).toBeDefined();
  });

  it('recalls with ScoringWeights', async () => {
    const weights: ScoringWeights = {
      wRelevance: 0.8,
      wRecency: 0.1,
      wImportance: 0.05,
      wReinforcement: 0.05,
    };
    const result = await client.recall({
      cue: 'ACME CRM',
      scoringWeights: weights,
    });
    expect(result.results).toBeDefined();
  });

  it('recalls with RecallStrategyConfig', async () => {
    const cfg: RecallStrategyConfig = {
      strategy: 'similarity',
      topK: 3,
      efSearch: 64,
    };
    const result = await client.recall({
      cue: 'Salesforce',
      strategies: [cfg],
    });
    expect(result.results).toBeDefined();
  });
});

describe.skipIf(!shouldRun)('Integration: Prime', () => {
  let client: HebbsClient;

  beforeAll(async () => {
    client = new HebbsClient(SERVER!, { apiKey: API_KEY });
    await client.connect();
  });
  afterAll(async () => client?.close());

  it('primes an entity session', async () => {
    const output = await client.prime({ entityId: 'acme' });
    expect(output.results).toBeDefined();
    expect(typeof output.temporalCount).toBe('number');
    expect(typeof output.similarityCount).toBe('number');
  });
});

describe.skipIf(!shouldRun)('Integration: Revise', () => {
  let client: HebbsClient;

  beforeAll(async () => {
    client = new HebbsClient(SERVER!, { apiKey: API_KEY });
    await client.connect();
  });
  afterAll(async () => client?.close());

  it('revises content and importance', async () => {
    const mem = await client.remember({
      content: 'Original content',
      importance: 0.5,
    });

    const revised = await client.revise(mem.id, {
      content: 'Revised content',
      importance: 0.9,
    });

    expect(revised.content).toBe('Revised content');
    expect(revised.importance).toBeGreaterThanOrEqual(0.9);
  });
});

describe.skipIf(!shouldRun)('Integration: SetPolicy', () => {
  let client: HebbsClient;

  beforeAll(async () => {
    client = new HebbsClient(SERVER!, { apiKey: API_KEY });
    await client.connect();
  });
  afterAll(async () => client?.close());

  it('applies policy changes', async () => {
    const ok = await client.setPolicy({
      maxSnapshotsPerMemory: 5,
      autoForgetThreshold: 0.01,
      decayHalfLifeDays: 30.0,
    });
    expect(ok).toBe(true);
  });
});

describe.skipIf(!shouldRun)('Integration: Subscribe', () => {
  let client: HebbsClient;

  beforeAll(async () => {
    client = new HebbsClient(SERVER!, { apiKey: API_KEY });
    await client.connect();
  });
  afterAll(async () => client?.close());

  it('opens, feeds, and closes a subscription', async () => {
    const sub = await client.subscribe({
      entityId: 'ts-test',
      confidenceThreshold: 0.3,
    });
    expect(sub.subscriptionId).toBeGreaterThan(0);

    await sub.feed('Tell me about TypeScript test data');
    await sub.close();
  });
});

describe.skipIf(!shouldRun)('Integration: Forget', () => {
  let client: HebbsClient;

  beforeAll(async () => {
    client = new HebbsClient(SERVER!, { apiKey: API_KEY });
    await client.connect();
  });
  afterAll(async () => client?.close());

  it('forgets by memory ID', async () => {
    const mem = await client.remember({
      content: 'Temporary for forget',
      entityId: 'forget-ts-test',
    });

    const result = await client.forget({ memoryIds: [mem.id] });
    expect(result.forgottenCount).toBeGreaterThanOrEqual(1);
  });

  it('forgets by entity', async () => {
    await client.remember({
      content: 'Entity forget 1',
      entityId: 'gdpr-ts-test',
    });
    await client.remember({
      content: 'Entity forget 2',
      entityId: 'gdpr-ts-test',
    });

    const result = await client.forget({ entityId: 'gdpr-ts-test' });
    expect(result.forgottenCount).toBeGreaterThanOrEqual(2);
  });
});

describe.skipIf(!shouldRun)('Integration: Reflect', () => {
  let client: HebbsClient;

  beforeAll(async () => {
    client = new HebbsClient(SERVER!, { apiKey: API_KEY });
    await client.connect();
  });
  afterAll(async () => client?.close());

  it('triggers global reflect', async () => {
    const result = await client.reflect();
    expect(typeof result.insightsCreated).toBe('number');
    expect(typeof result.clustersFound).toBe('number');
  });

  it('retrieves insights', async () => {
    const insights = await client.insights({ maxResults: 10 });
    expect(Array.isArray(insights)).toBe(true);
  });
});

describe.skipIf(!shouldRun)('Integration: Auth errors', () => {
  it('rejects empty API key', async () => {
    const bad = new HebbsClient(SERVER!, { apiKey: '' });
    await bad.connect();
    try {
      await expect(bad.recall({ cue: 'test' })).rejects.toThrow(
        HebbsAuthenticationError,
      );
    } finally {
      await bad.close();
    }
  });

  it('rejects invalid API key', async () => {
    const bad = new HebbsClient(SERVER!, { apiKey: 'hb_invalid_key_12345' });
    await bad.connect();
    try {
      await expect(bad.recall({ cue: 'test' })).rejects.toThrow(
        HebbsAuthenticationError,
      );
    } finally {
      await bad.close();
    }
  });
});
