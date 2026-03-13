#!/usr/bin/env npx tsx
/**
 * HEBBS TypeScript SDK -- Production E2E Validation
 * ==================================================
 *
 * Full production validation of every TypeScript SDK operation against a live
 * HEBBS server. Zero mocks -- real ONNX embeddings, real OpenAI-powered
 * reflect pipeline, real authentication.
 *
 * How to Run
 * ----------
 *
 * ### Terminal 1 -- Start the HEBBS server
 *
 *     cd hebbs
 *     rm -rf ./hebbs-data   # fresh state
 *
 *     OPENAI_API_KEY="sk-proj-..."             \
 *     HEBBS_REFLECT_ENABLED=true               \
 *     HEBBS_REFLECT_PROPOSAL_PROVIDER=openai    \
 *     HEBBS_REFLECT_PROPOSAL_MODEL=gpt-4o       \
 *     HEBBS_REFLECT_VALIDATION_PROVIDER=openai   \
 *     HEBBS_REFLECT_VALIDATION_MODEL=gpt-4o      \
 *     cargo run --release --bin hebbs-server
 *
 * ### Terminal 2 -- Run tests
 *
 *     cd hebbs-typescript
 *     npm install
 *     export HEBBS_API_KEY="hb_<key-from-server-banner>"
 *     export OPENAI_API_KEY="sk-proj-..."
 *     npx tsx tests/e2e/e2e.test.ts
 */

import {
  HebbsClient,
  MemoryKind,
  EdgeType,
  HebbsAuthenticationError,
  HebbsNotFoundError,
  HebbsError,
  type ScoringWeights,
  type RecallStrategyConfig,
  type Memory,
} from '../../src/index.js';

// ── Config ─────────────────────────────────────────────────────────────

const SERVER_ADDRESS = process.env['HEBBS_ADDRESS'] ?? 'localhost:6380';
const API_KEY = process.env['HEBBS_API_KEY'];
const OPENAI_KEY = process.env['OPENAI_API_KEY'];

const DIM = '\x1b[2m';
const RESET = '\x1b[0m';
const RED = '\x1b[31m';
const GREEN = '\x1b[32m';
const CYAN = '\x1b[36m';
const YELLOW = '\x1b[33m';

// ── Formatting ─────────────────────────────────────────────────────────

function trunc(s: string, n = 70): string {
  return s.length > n ? s.slice(0, n) + '...' : s;
}

function fmtVal(v: unknown): string {
  if (v instanceof Buffer) {
    return v.length > 8 ? v.toString('hex').slice(0, 16) + '...' : v.toString('hex');
  }
  if (typeof v === 'string') return `"${trunc(v, 60)}"`;
  if (typeof v === 'number') return v.toFixed(4);
  if (Array.isArray(v) && v.length > 5) return `[${v.length} items]`;
  return String(v);
}

function fmtMemory(m: Memory, prefix = ''): string[] {
  return [
    `${prefix}Memory(`,
    `${prefix}  id          = ${m.id.toString('hex').slice(0, 16)}...`,
    `${prefix}  content     = ${trunc(m.content, 70)}`,
    `${prefix}  importance  = ${m.importance.toFixed(4)}`,
    `${prefix}  entity_id   = ${m.entityId ?? 'undefined'}`,
    `${prefix}  kind        = ${m.kind}`,
    `${prefix}  context     = ${JSON.stringify(m.context)}`,
    `${prefix}  created_at  = ${m.createdAt}`,
    `${prefix}  decay_score = ${m.decayScore.toFixed(4)}`,
    `${prefix})`,
  ];
}

class Log {
  private lines: string[] = [];
  call(fn: string, kw: Record<string, unknown> = {}): void {
    const parts = Object.entries(kw)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => `${k}=${fmtVal(v)}`);
    this.lines.push(`${CYAN}CALL:${RESET}     h.${fn}(${parts.join(', ')})`);
  }
  response(label: string, obj: string): void {
    this.lines.push(`${GREEN}RESPONSE:${RESET} ${label}: ${obj}`);
  }
  detail(line: string): void {
    this.lines.push(`          ${line}`);
  }
  info(line: string): void {
    this.lines.push(`${YELLOW}INFO:${RESET}     ${line}`);
  }
  text(): string {
    return this.lines.join('\n');
  }
}

// ── Test Infrastructure ────────────────────────────────────────────────

interface TestResult {
  name: string;
  passed: boolean;
  message: string;
  durationMs: number;
}

const RESULTS: TestResult[] = [];
let sectionIdx = 0;

function section(title: string): void {
  sectionIdx++;
  console.log(`\n${'='.repeat(72)}`);
  console.log(`  SECTION ${sectionIdx}: ${title}`);
  console.log('='.repeat(72));
}

function record(name: string, passed: boolean, msg: string, dur: number): void {
  const tag = passed ? `${GREEN}PASS${RESET}` : `${RED}FAIL${RESET}`;
  console.log(`  [${tag}] ${name}  (${dur.toFixed(0)}ms)`);
  if (msg) {
    for (const line of msg.trim().split('\n')) {
      console.log(`         ${line}`);
    }
  }
  RESULTS.push({ name, passed, message: msg, durationMs: dur });
}

async function runTest(name: string, fn: () => Promise<string>): Promise<void> {
  console.log(`\n  >>> ${name}`);
  const t0 = performance.now();
  try {
    const msg = await fn();
    record(name, true, msg, performance.now() - t0);
  } catch (err: unknown) {
    const dur = performance.now() - t0;
    const e = err instanceof Error ? err : new Error(String(err));
    record(name, false, `${e.constructor.name}: ${e.message}\n${e.stack?.split('\n').slice(-3).join('\n') ?? ''}`, dur);
  }
}

function newClient(opts?: { apiKey?: string }): HebbsClient {
  return new HebbsClient(SERVER_ADDRESS, { apiKey: opts?.apiKey ?? API_KEY });
}

// ── Tests ──────────────────────────────────────────────────────────────

async function testHealth(): Promise<string> {
  const log = new Log();
  const c = newClient();
  await c.connect();
  try {
    log.call('health');
    const s = await c.health();
    log.response('HealthStatus', `serving=${s.serving}, version=${s.version}, memory_count=${s.memoryCount}, uptime=${s.uptimeSeconds}s`);
    if (!s.serving) throw new Error('server not serving');
    if (!s.version) throw new Error('version empty');
  } finally { await c.close(); }
  return log.text();
}

async function testCount(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    log.call('count');
    const n = await c.count();
    log.response('number', String(n));
  } finally { await c.close(); }
  return log.text();
}

async function testRememberBasic(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    const kw = { content: 'ACME Corp uses Salesforce for CRM', importance: 0.8, context: { industry: 'technology', tool: 'salesforce' }, entityId: 'acme' };
    log.call('remember', kw);
    const mem = await c.remember(kw);
    log.response('Memory', '');
    for (const l of fmtMemory(mem, '  ')) log.detail(l);
    if (!mem.id.length) throw new Error('no memory ID');
    if (mem.content !== 'ACME Corp uses Salesforce for CRM') throw new Error('content mismatch');
    if (Math.abs(mem.importance - 0.8) > 0.01) throw new Error('importance mismatch');
    if (mem.entityId !== 'acme') throw new Error('entity_id mismatch');
    if (mem.kind !== MemoryKind.EPISODE) throw new Error('kind mismatch');
  } finally { await c.close(); }
  return log.text();
}

async function testRememberWithEdges(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    log.call('remember', { content: 'Initech CTO expressed interest in our API', entityId: 'initech' });
    const mem1 = await c.remember({ content: 'Initech CTO expressed interest in our API', entityId: 'initech' });
    log.response('Memory', `id=${mem1.id.toString('hex').slice(0, 16)}...`);

    log.call('remember', { content: 'Initech requested a technical deep-dive meeting', entityId: 'initech', edges: 'FOLLOWED_BY' });
    const mem2 = await c.remember({
      content: 'Initech requested a technical deep-dive meeting',
      entityId: 'initech',
      edges: [{ targetId: mem1.id, edgeType: EdgeType.FOLLOWED_BY, confidence: 0.95 }],
    });
    log.response('Memory', `id=${mem2.id.toString('hex').slice(0, 16)}...`);
    if (mem1.id.equals(mem2.id)) throw new Error('IDs should differ');
  } finally { await c.close(); }
  return log.text();
}

async function testGet(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    log.call('remember', { content: 'Test memory for get operation', importance: 0.5 });
    const mem = await c.remember({ content: 'Test memory for get operation', importance: 0.5 });
    log.call('get', { memoryId: mem.id });
    const got = await c.get(mem.id);
    log.response('Memory', '');
    for (const l of fmtMemory(got, '  ')) log.detail(l);
    if (got.content !== 'Test memory for get operation') throw new Error('content mismatch');
  } finally { await c.close(); }
  return log.text();
}

async function testRecallSimilarity(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    log.call('recall', { cue: 'What CRM does ACME use?', topK: 5 });
    const r = await c.recall({ cue: 'What CRM does ACME use?', topK: 5 });
    log.response('RecallOutput', `results=${r.results.length}, strategy_errors=${r.strategyErrors.length}`);
    for (let i = 0; i < Math.min(r.results.length, 5); i++) {
      const rr = r.results[i];
      log.detail(`[${i}] score=${rr.score.toFixed(4)} content="${trunc(rr.memory.content, 55)}"`);
    }
    if (!r.results.length) throw new Error('no recall results');
  } finally { await c.close(); }
  return log.text();
}

async function testRecallMultiStrategy(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    log.call('recall', { cue: 'What is Initech doing?', strategies: ['similarity', 'temporal'], entityId: 'initech', topK: 5 });
    const r = await c.recall({ cue: 'What is Initech doing?', strategies: ['similarity', 'temporal'], entityId: 'initech', topK: 5 });
    log.response('RecallOutput', `results=${r.results.length}`);
    if (!r.results.length) throw new Error('no multi-strategy results');
  } finally { await c.close(); }
  return log.text();
}

async function testRecallScoringWeightsObject(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    const recencyWeights: ScoringWeights = { wRelevance: 0.1, wRecency: 0.7, wImportance: 0.1, wReinforcement: 0.1 };
    log.call('recall', { cue: 'Initech evaluation', scoringWeights: 'recency-heavy', topK: 5 });
    const r1 = await c.recall({ cue: 'Initech evaluation', scoringWeights: recencyWeights, topK: 5 });
    log.response('RecallOutput (recency)', `results=${r1.results.length}`);

    const relevanceWeights: ScoringWeights = { wRelevance: 0.8, wRecency: 0.05, wImportance: 0.1, wReinforcement: 0.05 };
    const r2 = await c.recall({ cue: 'Initech evaluation', scoringWeights: relevanceWeights, topK: 5 });
    log.response('RecallOutput (relevance)', `results=${r2.results.length}`);

    if (!r1.results.length) throw new Error('no recency results');
    if (!r2.results.length) throw new Error('no relevance results');
  } finally { await c.close(); }
  return log.text();
}

async function testRecallStrategyConfig(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    const cfg: RecallStrategyConfig = { strategy: 'similarity', entityId: 'initech', topK: 3, efSearch: 64 };
    log.call('recall', { cue: 'Initech CTO interest', strategies: 'RecallStrategyConfig' });
    const r = await c.recall({ cue: 'Initech CTO interest', strategies: [cfg] });
    log.response('RecallOutput', `results=${r.results.length}`);
    if (!r.results.length) throw new Error('no RecallStrategyConfig results');
  } finally { await c.close(); }
  return log.text();
}

async function testRecallMixed(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    const cfg: RecallStrategyConfig = { strategy: 'similarity', topK: 3 };
    log.call('recall', { cue: 'Initech evaluation', strategies: "['temporal', RecallStrategyConfig]", entityId: 'initech', topK: 5 });
    const r = await c.recall({ cue: 'Initech evaluation', strategies: ['temporal', cfg], entityId: 'initech', topK: 5 });
    log.response('RecallOutput', `results=${r.results.length}`);
    if (!r.results.length) throw new Error('no mixed results');
  } finally { await c.close(); }
  return log.text();
}

async function testRecallCausal(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    log.info('finding seed memory via similarity recall first...');
    const sim = await c.recall({ cue: 'Initech CTO', strategies: ['similarity'], topK: 1, entityId: 'initech' });
    if (!sim.results.length) { log.info('SKIP: no seed memory'); return log.text(); }
    const seedId = sim.results[0].memory.id;
    log.info(`seed_memory_id = ${seedId.toString('hex').slice(0, 16)}...`);

    const cfg: RecallStrategyConfig = {
      strategy: 'causal', seedMemoryId: seedId, maxDepth: 3,
      edgeTypes: [EdgeType.FOLLOWED_BY, EdgeType.CAUSED_BY],
    };
    const r = await c.recall({ cue: 'Initech', strategies: [cfg] });
    log.response('RecallOutput', `results=${r.results.length}, errors=${r.strategyErrors.length}`);
  } finally { await c.close(); }
  return log.text();
}

async function testRecallAnalogical(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    const cfg: RecallStrategyConfig = { strategy: 'analogical', analogicalAlpha: 0.7 };
    const r = await c.recall({
      cue: 'enterprise CRM evaluation', strategies: [cfg],
      cueContext: { industry: 'technology', stage: 'evaluation' }, topK: 5,
    });
    log.response('RecallOutput', `results=${r.results.length}, errors=${r.strategyErrors.length}`);
  } finally { await c.close(); }
  return log.text();
}

async function testPrime(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    log.call('prime', { entityId: 'initech', maxMemories: 20, similarityCue: 'enterprise evaluation' });
    const out = await c.prime({ entityId: 'initech', maxMemories: 20, similarityCue: 'enterprise evaluation' });
    log.response('PrimeOutput', `results=${out.results.length}, temporal=${out.temporalCount}, similarity=${out.similarityCount}`);
  } finally { await c.close(); }
  return log.text();
}

async function testPrimeWithWeights(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    const w: ScoringWeights = { wRelevance: 0.3, wRecency: 0.5, wImportance: 0.1, wReinforcement: 0.1 };
    const out = await c.prime({ entityId: 'initech', similarityCue: 'evaluation', scoringWeights: w });
    log.response('PrimeOutput', `results=${out.results.length}`);
  } finally { await c.close(); }
  return log.text();
}

async function testRevise(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    const mem = await c.remember({ content: 'Initech deal size: 200 seats', importance: 0.7, entityId: 'initech' });
    log.response('Memory', `id=${mem.id.toString('hex').slice(0, 16)}...`);

    log.call('revise', { content: 'Initech deal size expanded: 350 seats', importance: 0.95 });
    const revised = await c.revise(mem.id, {
      content: 'Initech deal size expanded: 350 seats',
      importance: 0.95,
      context: { deal_size: '350 seats', stage: 'negotiation' },
    });
    for (const l of fmtMemory(revised, '  ')) log.detail(l);
    if (revised.content !== 'Initech deal size expanded: 350 seats') throw new Error('content mismatch');
    if (revised.importance < 0.9) throw new Error('importance mismatch');
  } finally { await c.close(); }
  return log.text();
}

async function testSetPolicy(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    log.call('setPolicy', { maxSnapshotsPerMemory: 5, autoForgetThreshold: 0.01, decayHalfLifeDays: 30.0 });
    const ok = await c.setPolicy({ maxSnapshotsPerMemory: 5, autoForgetThreshold: 0.01, decayHalfLifeDays: 30.0 });
    log.response('boolean', String(ok));
    if (!ok) throw new Error('setPolicy returned false');
  } finally { await c.close(); }
  return log.text();
}

async function testSubscribeFeedClose(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    log.call('subscribe', { entityId: 'initech', confidenceThreshold: 0.3 });
    const sub = await c.subscribe({ entityId: 'initech', confidenceThreshold: 0.3 });
    log.response('Subscription', `subscription_id=${sub.subscriptionId}`);

    const feedText = 'Tell me about Initech evaluation process';
    log.call('sub.feed', { text: feedText });
    await sub.feed(feedText);
    log.response('feed', 'accepted');

    log.info('listening for pushes (3s timeout)...');
    const pushes = await sub.listen(3000);
    for (let i = 0; i < pushes.length; i++) {
      log.detail(`push[${i}]: confidence=${pushes[i].confidence?.toFixed(4)}`);
    }
    log.response('listen', `${pushes.length} pushes received`);

    log.call('sub.close');
    await sub.close();
    log.response('close', 'ok');
  } finally { await c.close(); }
  return log.text();
}

async function testForgetById(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    const mem = await c.remember({ content: 'Temporary memory for forget test', entityId: 'forget-test' });
    const countBefore = await c.count();
    const result = await c.forget({ memoryIds: [mem.id] });
    const countAfter = await c.count();
    log.response('ForgetResult', `forgotten=${result.forgottenCount}, cascade=${result.cascadeCount}, tombstone=${result.tombstoneCount}`);
    log.response('count', `${countAfter} (was ${countBefore})`);
    if (result.forgottenCount < 1) throw new Error('nothing forgotten');
    if (countAfter >= countBefore) throw new Error('count did not decrease');
  } finally { await c.close(); }
  return log.text();
}

async function testForgetByEntity(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    await c.remember({ content: 'Entity forget test 1', entityId: 'gdpr-delete' });
    await c.remember({ content: 'Entity forget test 2', entityId: 'gdpr-delete' });
    const result = await c.forget({ entityId: 'gdpr-delete' });
    log.response('ForgetResult', `forgotten=${result.forgottenCount}`);
    if (result.forgottenCount < 2) throw new Error('expected at least 2 forgotten');
  } finally { await c.close(); }
  return log.text();
}

async function testAuthNoKey(): Promise<string> {
  const log = new Log();
  const c = new HebbsClient(SERVER_ADDRESS, { apiKey: '' });
  await c.connect();
  try {
    await c.recall({ cue: 'auth test', topK: 1 });
    throw new Error('recall succeeded without auth');
  } catch (e) {
    if (e instanceof HebbsAuthenticationError) {
      log.response('HebbsAuthenticationError (expected)', (e as Error).message);
    } else if (e instanceof HebbsError) {
      log.response((e as Error).constructor.name, (e as Error).message);
    } else {
      throw e;
    }
  } finally { await c.close(); }
  return log.text();
}

async function testAuthBadKey(): Promise<string> {
  const log = new Log();
  const c = new HebbsClient(SERVER_ADDRESS, { apiKey: 'hb_invalid_key_12345' });
  await c.connect();
  try {
    await c.recall({ cue: 'auth test', topK: 1 });
    throw new Error('recall succeeded with bad key');
  } catch (e) {
    if (e instanceof HebbsAuthenticationError) {
      log.response('HebbsAuthenticationError (expected)', (e as Error).message);
    } else if (e instanceof HebbsError) {
      log.response((e as Error).constructor.name, (e as Error).message);
    } else {
      throw e;
    }
  } finally { await c.close(); }
  return log.text();
}

async function testAuthValidKey(): Promise<string> {
  const log = new Log();
  const c = new HebbsClient(SERVER_ADDRESS, { apiKey: API_KEY });
  await c.connect();
  try {
    const s = await c.health();
    log.response('HealthStatus', `serving=${s.serving}, version=${s.version}`);
    if (!s.serving) throw new Error('not serving');
  } finally { await c.close(); }
  return log.text();
}

async function testErrorNotFound(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    const fakeId = Buffer.alloc(16);
    log.call('get', { memoryId: fakeId });
    try {
      await c.get(fakeId);
      throw new Error('should have raised NotFound');
    } catch (e) {
      if (e instanceof HebbsNotFoundError) {
        log.response('HebbsNotFoundError', (e as Error).message);
      } else { throw e; }
    }
  } finally { await c.close(); }
  return log.text();
}

async function testErrorConnection(): Promise<string> {
  const log = new Log();
  const bad = new HebbsClient('localhost:19999', { apiKey: 'hb_test' });
  await bad.connect();
  try {
    await bad.health();
    throw new Error('should have raised connection error');
  } catch (e) {
    log.response((e as Error).constructor.name, (e as Error).message);
  } finally { await bad.close(); }
  return log.text();
}

async function testReflectE2e(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    const memories = [
      'ACME Corp renewed their Salesforce contract for 3 years',
      "ACME Corp's sales team grew from 10 to 25 reps this quarter",
      'ACME Corp asked about enterprise pricing tiers',
      "ACME Corp's CTO mentioned migrating to cloud-native infrastructure",
      'ACME Corp doubled their marketing budget for Q2',
      'Globex reported 40% increase in customer churn',
      'Globex is evaluating competitors to their current CRM',
      "Globex's VP of Sales expressed frustration with reporting tools",
      'TechStart signed a pilot deal for 50 seats',
      "TechStart's founder wants to scale to 500 users by Q3",
    ];
    log.info(`storing ${memories.length} memories for reflect...`);
    for (const content of memories) {
      await c.remember({ content, importance: 0.8 });
    }

    log.call('reflect');
    const result = await c.reflect();
    log.response('ReflectResult', `insights_created=${result.insightsCreated}, clusters=${result.clustersFound}`);

    log.call('insights', { maxResults: 20 });
    const insights = await c.insights({ maxResults: 20 });
    log.response('Memory[]', `${insights.length} insights`);
    for (let i = 0; i < Math.min(insights.length, 5); i++) {
      log.detail(`[${i}] kind=${insights[i].kind}, content="${trunc(insights[i].content, 70)}"`);
    }
  } finally { await c.close(); }
  return log.text();
}

async function testReflectEntityScoped(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    log.call('reflect', { entityId: 'acme' });
    const result = await c.reflect({ entityId: 'acme' });
    log.response('ReflectResult', `insights_created=${result.insightsCreated}, clusters=${result.clustersFound}`);

    log.call('insights', { entityId: 'acme', maxResults: 10 });
    const insights = await c.insights({ entityId: 'acme', maxResults: 10 });
    log.response('Memory[]', `${insights.length} insights`);
  } finally { await c.close(); }
  return log.text();
}

async function testPersistence(): Promise<string> {
  const log = new Log();
  const c = newClient(); await c.connect();
  try {
    const n = await c.count();
    log.response('count', String(n));

    const r = await c.recall({ cue: 'ACME Salesforce', topK: 3 });
    log.response('RecallOutput', `results=${r.results.length}`);
    for (let i = 0; i < Math.min(r.results.length, 3); i++) {
      log.detail(`[${i}] score=${r.results[i].score.toFixed(4)} content="${trunc(r.results[i].memory.content, 55)}"`);
    }
  } finally { await c.close(); }
  return log.text();
}

// ── Runner ─────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const NOT_SET = `${RED}NOT SET${RESET}`;
  const hebbsKeyDisplay = API_KEY ? `set (${API_KEY.slice(0, 12)}...)` : NOT_SET;
  const openaiKeyDisplay = OPENAI_KEY ? `set (${OPENAI_KEY.slice(0, 12)}...)` : NOT_SET;

  console.log('='.repeat(72));
  console.log('  HEBBS TypeScript SDK -- Production E2E Validation');
  console.log('='.repeat(72));
  console.log(`  Server:          ${SERVER_ADDRESS}`);
  console.log(`  HEBBS_API_KEY:   ${hebbsKeyDisplay}`);
  console.log(`  OPENAI_API_KEY:  ${openaiKeyDisplay}`);
  console.log(`  Embeddings:      ONNX (BGE-small-en-v1.5, local)`);
  console.log(`  Reflect:         OpenAI GPT-4o (server-side)`);
  console.log(`  SDK source:      local (npm link)`);
  console.log();

  const errors: string[] = [];
  if (!API_KEY) errors.push('HEBBS_API_KEY not set.');
  if (!OPENAI_KEY) errors.push('OPENAI_API_KEY not set. Required for reflect pipeline.');
  if (errors.length) {
    for (const e of errors) console.log(`${RED}  ERROR: ${e}${RESET}`);
    console.log();
    console.log('  export HEBBS_API_KEY="hb_<key-from-server-banner>"');
    console.log('  export OPENAI_API_KEY="sk-proj-..."');
    process.exit(1);
  }

  // Section 1
  section('Health & Connectivity');
  await runTest('health check', testHealth);
  await runTest('count', testCount);

  // Section 2 -- seed memories
  section('Remember');
  const seedClient = newClient(); await seedClient.connect();
  const seeds = [
    { content: 'Globex uses HubSpot for marketing automation', entityId: 'globex' },
    { content: 'TechStart chose Pipedrive as their sales CRM', entityId: 'techstart' },
    { content: 'Enterprise prospect Initech is evaluating our platform for 200 seats', importance: 0.9, context: { industry: 'technology', deal_size: 'enterprise', stage: 'evaluation' }, entityId: 'initech' },
  ];
  for (const s of seeds) await seedClient.remember(s);
  await seedClient.close();
  console.log(`\n  >>> seeded ${seeds.length} memories for recall tests`);

  await runTest('remember (basic, with context & entity)', testRememberBasic);
  await runTest('remember (with edges: FOLLOWED_BY)', testRememberWithEdges);

  // Section 3
  section('Get');
  await runTest('get by ID', testGet);

  // Section 4
  section('Recall -- Strategies & Weights');
  await runTest('recall: similarity (basic)', testRecallSimilarity);
  await runTest('recall: multi-strategy (similarity + temporal)', testRecallMultiStrategy);
  await runTest('recall: ScoringWeights (recency vs relevance)', testRecallScoringWeightsObject);
  section('Recall -- Advanced Strategy Config');
  await runTest('recall: RecallStrategyConfig (ef_search, per-strategy top_k)', testRecallStrategyConfig);
  await runTest('recall: mixed string + RecallStrategyConfig', testRecallMixed);
  await runTest('recall: causal (seed_memory_id, max_depth, edge_types)', testRecallCausal);
  await runTest('recall: analogical (alpha, cue_context)', testRecallAnalogical);

  // Section 5
  section('Prime');
  await runTest('prime (entity + similarity_cue)', testPrime);
  await runTest('prime (with ScoringWeights)', testPrimeWithWeights);

  // Section 6
  section('Revise');
  await runTest('revise (content, importance, context)', testRevise);

  // Section 7
  section('Set Policy');
  await runTest('set_policy (snapshots, threshold, decay)', testSetPolicy);

  // Section 8
  section('Subscribe / Feed / Close');
  await runTest('subscribe -> feed -> listen -> close', testSubscribeFeedClose);

  // Section 9
  section('Forget (GDPR Erasure)');
  await runTest('forget by ID', testForgetById);
  await runTest('forget by entity', testForgetByEntity);

  // Section 10
  section('Authentication');
  await runTest('auth: no key -> rejected', testAuthNoKey);
  await runTest('auth: bad key -> rejected', testAuthBadKey);
  await runTest('auth: explicit valid key -> accepted', testAuthValidKey);

  // Section 11
  section('Error Handling');
  await runTest('error: get non-existent ID -> NotFound', testErrorNotFound);
  await runTest('error: connect to wrong port -> connection error', testErrorConnection);

  // Section 12
  section('Reflect Pipeline (OpenAI GPT-4o)');
  await runTest('reflect: store 10 memories + trigger reflect', testReflectE2e);
  await runTest('reflect: entity-scoped (acme)', testReflectEntityScoped);

  // Section 13
  section('Data Persistence (in-session)');
  await runTest('persistence: data from earlier tests still present', testPersistence);

  // Summary
  console.log(`\n${'='.repeat(72)}`);
  console.log('  SUMMARY');
  console.log('='.repeat(72));

  const passed = RESULTS.filter((r) => r.passed).length;
  const failed = RESULTS.filter((r) => !r.passed).length;
  const totalMs = RESULTS.reduce((s, r) => s + r.durationMs, 0);

  for (const r of RESULTS) {
    const tag = r.passed ? `${GREEN}pass${RESET}` : `${RED}FAIL${RESET}`;
    console.log(`  ${tag}  ${r.name}`);
  }

  console.log();
  console.log(`  Total:  ${RESULTS.length}  |  Passed: ${GREEN}${passed}${RESET}  |  Failed: ${RED}${failed}${RESET}  |  Time: ${totalMs.toFixed(0)}ms`);

  if (failed) {
    console.log(`\n  ${RED}${failed} test(s) FAILED${RESET}`);
    for (const r of RESULTS.filter((r) => !r.passed)) {
      console.log(`\n  FAIL: ${r.name}`);
      for (const line of r.message.trim().split('\n')) {
        console.log(`        ${line}`);
      }
    }
    process.exit(1);
  } else {
    console.log(`\n  ${GREEN}All ${passed} tests passed.${RESET}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
