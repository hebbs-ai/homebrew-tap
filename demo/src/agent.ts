import type { HebbsClient, RecallResult } from '@hebbs/sdk';
import type { DemoConfig } from './config.js';
import type { DisplayManager } from './display.js';
import { LlmClient, MockLlmClient, type LlmResponse } from './llm-client.js';
import { MemoryManager } from './memory-manager.js';

const SYSTEM_SALES_AGENT = `You are "Atlas", the AI Sales Intelligence Agent for HEBBS -- a cognitive memory engine for AI applications. You are having a live demo conversation with a prospective customer.

About HEBBS:
- Embedded, Rust-powered memory engine with sub-millisecond recall latency
- Four recall strategies: Similarity, Temporal, Causal, Analogical
- Key operations: remember, recall, reflect, forget, subscribe, prime
- Ships as a native library or gRPC server

Your personality:
- Professional but warm; consultative
- Reference past interactions naturally
- Keep responses concise (2-4 sentences)
- Ask one question per response`;

export interface TurnResult {
  prospectMessage: string;
  agentResponse: string;
  memoriesCreated: number;
  memoriesRecalled: number;
  turnLatencyMs: number;
}

export interface HebbsSessionStats {
  turns: number;
  memoriesCreated: number;
  memoriesRecalled: number;
  primedMemories: number;
  subscribePushes: number;
  reflectRuns: number;
  forgetRuns: number;
  recallCalls: number;
  rememberCalls: number;
}

export class SalesAgent {
  private currentEntity: string | null = null;
  private sessionHistory: { role: string; content: string }[] = [];
  private pendingExtractions: Promise<unknown>[] = [];
  readonly hebbsStats: HebbsSessionStats = {
    turns: 0, memoriesCreated: 0, memoriesRecalled: 0, primedMemories: 0,
    subscribePushes: 0, reflectRuns: 0, forgetRuns: 0, recallCalls: 0, rememberCalls: 0,
  };

  readonly llmClient: LlmClient;
  readonly memoryManager: MemoryManager;

  constructor(
    private config: DemoConfig,
    private hebbs: HebbsClient,
    private display: DisplayManager,
    useMockLlm = false,
  ) {
    this.llmClient = useMockLlm ? new MockLlmClient(config) : new LlmClient(config);
    this.memoryManager = new MemoryManager(hebbs, this.llmClient, display);
  }

  async startSession(entityId: string, sessionNum?: number): Promise<string> {
    this.currentEntity = entityId;
    this.sessionHistory = [];
    this.display.displaySessionHeader(entityId, sessionNum);

    const [context, primed] = await this.memoryManager.primeSession(entityId);
    this.hebbsStats.primedMemories += primed.length;

    return context;
  }

  async flushPending(): Promise<number> {
    if (!this.pendingExtractions.length) return 0;
    const results = await Promise.allSettled(this.pendingExtractions);
    this.pendingExtractions = [];
    let total = 0;
    for (const r of results) {
      if (r.status === 'fulfilled' && Array.isArray(r.value)) {
        total += r.value.length;
      }
    }
    this.hebbsStats.memoriesCreated += total;
    this.hebbsStats.rememberCalls += total;
    return total;
  }

  async endSession(): Promise<void> {
    await this.flushPending();
    this.sessionHistory = [];
    this.currentEntity = null;
  }

  async processTurn(
    prospectMessage: string,
    recallStrategies: string[] = ['similarity'],
  ): Promise<TurnResult> {
    await this.flushPending();
    const t0 = performance.now();
    this.display.startTurn();
    const entity = this.currentEntity;

    this.display.displayProspectMessage(entity ?? 'Prospect', prospectMessage);

    const [recalledContext, recallResults] = await this.memoryManager.recallContext(
      prospectMessage, entity ?? undefined, recallStrategies,
    );

    let insightsStr = '';
    try {
      const insights = await this.hebbs.insights({ entityId: entity ?? undefined });
      if (insights.length) {
        insightsStr = insights.map((i) => `- ${i.content}`).join('\n');
      }
    } catch {
      // swallow
    }

    const messages = this.buildConversationPrompt(
      prospectMessage, recalledContext, entity, insightsStr,
    );

    const llmResp = await this.llmClient.conversation(messages);

    this.sessionHistory.push({ role: 'user', content: prospectMessage });
    this.sessionHistory.push({ role: 'assistant', content: llmResp.content });

    this.display.displayTurn();
    this.display.displayAgentResponse(llmResp.content);

    const extractionPromise = this.memoryManager.extractAndRemember(
      prospectMessage, llmResp.content, entity ?? undefined, recalledContext, true,
    );
    this.pendingExtractions.push(extractionPromise);

    const elapsed = performance.now() - t0;
    this.hebbsStats.turns++;
    this.hebbsStats.memoriesRecalled += recallResults.length;
    this.hebbsStats.recallCalls++;

    return {
      prospectMessage,
      agentResponse: llmResp.content,
      memoriesCreated: 0,
      memoriesRecalled: recallResults.length,
      turnLatencyMs: elapsed,
    };
  }

  private buildConversationPrompt(
    prospectMessage: string,
    recalledContext: string,
    entityId: string | null,
    insights: string,
  ): { role: string; content: string }[] {
    const messages: { role: string; content: string }[] = [
      { role: 'system', content: SYSTEM_SALES_AGENT },
    ];

    let contextBlock = '';
    if (recalledContext) contextBlock += `\n\n--- RECALLED MEMORIES ---\n${recalledContext}`;
    if (insights) contextBlock += `\n\n--- INSTITUTIONAL INSIGHTS ---\n${insights}`;
    if (entityId) contextBlock += `\n\nCurrent prospect entity: ${entityId}`;

    if (contextBlock) {
      messages.push({
        role: 'system',
        content: `The following context was retrieved from your memory system. Use it naturally.${contextBlock}`,
      });
    }

    for (const turn of this.sessionHistory) {
      messages.push(turn);
    }

    messages.push({ role: 'user', content: prospectMessage });
    return messages;
  }

  async runReflect(entityId?: string): Promise<void> {
    const t0 = performance.now();
    try {
      const result = await this.hebbs.reflect({ entityId });
      this.hebbsStats.reflectRuns++;
      this.display.displayReflect(
        result.memoriesProcessed, result.clustersFound, result.insightsCreated,
        performance.now() - t0,
      );
    } catch (e) {
      console.warn('reflect() failed:', e);
    }
  }

  async runForget(entityId: string): Promise<void> {
    const t0 = performance.now();
    try {
      const result = await this.hebbs.forget({ entityId });
      this.hebbsStats.forgetRuns++;
      this.display.displayForget(
        entityId, result.forgottenCount, result.cascadeCount, result.tombstoneCount,
        performance.now() - t0,
      );
    } catch (e) {
      console.warn('forget() failed:', e);
    }
  }
}
