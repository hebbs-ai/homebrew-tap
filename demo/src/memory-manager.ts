import type { HebbsClient, Memory, RecallResult } from '@hebbs/sdk';
import type { LlmClient, LlmResponse } from './llm-client.js';
import type { DisplayManager, OperationRecord } from './display.js';

const EXTRACTION_SYSTEM = `You are a memory extraction system for a sales intelligence agent. Analyze the conversation and respond with valid JSON:
{
  "memories": [{ "content": "fact", "importance": 0.0-1.0, "context": { "topic": "..." }, "edge_to_previous": false }],
  "skip_reason": null
}
Extract 0-3 memories. Only important facts. importance 0.9+ for deal-critical, 0.7-0.9 for preferences.`;

interface ExtractedMemory {
  content: string;
  importance: number;
  context: Record<string, unknown>;
}

export class MemoryManager {
  totalRememberMs = 0;
  totalRecallMs = 0;
  totalPrimeMs = 0;
  rememberBatches = 0;
  recallBatches = 0;
  primeCalls = 0;

  constructor(
    private hebbs: HebbsClient,
    private llm: LlmClient,
    private display: DisplayManager,
  ) {}

  async extractAndRemember(
    prospectMessage: string,
    agentResponse: string,
    entityId?: string,
    recalledContext = '',
    immediateDisplay = false,
  ): Promise<Memory[]> {
    const extracted = await this.extract(prospectMessage, agentResponse, entityId, recalledContext);
    if (!extracted.length) return [];

    const stored: Memory[] = [];
    const t0 = performance.now();

    for (const mem of extracted) {
      try {
        const result = await this.hebbs.remember({
          content: mem.content,
          importance: mem.importance,
          context: mem.context,
          entityId,
        });
        stored.push(result);
      } catch (e) {
        console.warn('remember() failed:', e);
      }
    }

    const elapsed = performance.now() - t0;
    this.totalRememberMs += elapsed;
    this.rememberBatches++;

    if (stored.length) {
      const record: OperationRecord = {
        operation: 'REMEMBER',
        latencyMs: elapsed,
        summary: `${stored.length} memory stored (importance: ${stored[0].importance.toFixed(1)})`,
        details: stored.map((m) => `content: "${m.content.slice(0, 60)}${m.content.length > 60 ? '...' : ''}"`),
        highlightColor: 'green',
      };
      if (immediateDisplay) {
        this.display.displayRecordImmediate(record);
      } else {
        this.display.recordOperation(record);
      }
    }

    return stored;
  }

  private async extract(
    prospectMessage: string,
    agentResponse: string,
    entityId?: string,
    recalledContext = '',
  ): Promise<ExtractedMemory[]> {
    let turnText = `Prospect: ${prospectMessage}\nAgent: ${agentResponse}`;
    if (entityId) turnText = `[Entity: ${entityId}]\n${turnText}`;
    if (recalledContext) turnText += `\n\n--- Already stored ---\n${recalledContext}`;

    const messages = [
      { role: 'system', content: EXTRACTION_SYSTEM },
      { role: 'user', content: turnText },
    ];

    let resp: LlmResponse;
    try {
      resp = await this.llm.extractMemories(messages);
    } catch {
      return [];
    }

    return this.parseExtraction(resp.content);
  }

  private parseExtraction(raw: string): ExtractedMemory[] {
    let cleaned = raw.trim();
    if (cleaned.startsWith('```')) {
      const lines = cleaned.split('\n').filter((l) => !l.trim().startsWith('```'));
      cleaned = lines.join('\n');
    }

    let data: Record<string, unknown>;
    try {
      data = JSON.parse(cleaned);
    } catch {
      const start = cleaned.indexOf('{');
      const end = cleaned.lastIndexOf('}') + 1;
      if (start >= 0 && end > start) {
        try {
          data = JSON.parse(cleaned.slice(start, end));
        } catch {
          return [];
        }
      } else {
        return [];
      }
    }

    const memories: ExtractedMemory[] = [];
    for (const m of (data['memories'] as Record<string, unknown>[]) ?? []) {
      const content = String(m['content'] ?? '').trim();
      if (!content) continue;
      const importance = Math.max(0, Math.min(1, Number(m['importance'] ?? 0.5)));
      const context = typeof m['context'] === 'object' && m['context'] !== null ? (m['context'] as Record<string, unknown>) : {};
      memories.push({ content, importance, context });
    }

    return memories;
  }

  async recallContext(
    cue: string,
    entityId?: string,
    strategies: string[] = ['similarity'],
    topK = 10,
  ): Promise<[string, RecallResult[]]> {
    const t0 = performance.now();
    let results: RecallResult[] = [];

    try {
      const recallOut = await this.hebbs.recall({
        cue,
        strategies,
        topK,
        entityId,
      });
      results = recallOut.results;
    } catch (e) {
      console.warn('recall() failed:', e);
    }

    const elapsed = performance.now() - t0;
    this.totalRecallMs += elapsed;
    this.recallBatches++;

    if (results.length) {
      const details = results.slice(0, 10).map((r) => {
        const score = r.score.toFixed(2);
        const content = r.memory.content.slice(0, 55);
        return `${score}  "${content}"`;
      });
      details.unshift(`HEBBS server: ${elapsed.toFixed(1)}ms`);

      this.display.recordOperation({
        operation: 'RECALL',
        latencyMs: elapsed,
        summary: `${results.length} memories retrieved (strategy: ${strategies.map((s) => s.charAt(0).toUpperCase() + s.slice(1)).join('+')})`,
        details,
        highlightColor: 'blue',
      });
    }

    const contextLines = results.map((r) => {
      let line = `- [${r.memory.kind}] ${r.memory.content}`;
      if (r.memory.context && Object.keys(r.memory.context).length) {
        const parts = Object.entries(r.memory.context).slice(0, 3).map(([k, v]) => `${k}=${v}`);
        line += ` (${parts.join(', ')})`;
      }
      return line;
    });

    return [contextLines.join('\n'), results];
  }

  async primeSession(entityId: string, similarityCue?: string): Promise<[string, RecallResult[]]> {
    const t0 = performance.now();

    let results: RecallResult[] = [];
    let temporalCount = 0;
    let similarityCount = 0;

    try {
      const primeOut = await this.hebbs.prime({
        entityId,
        maxMemories: 50,
        similarityCue,
      });
      results = primeOut.results;
      temporalCount = primeOut.temporalCount;
      similarityCount = primeOut.similarityCount;
    } catch (e) {
      console.warn('prime() failed:', e);
    }

    const elapsed = performance.now() - t0;
    this.totalPrimeMs += elapsed;
    this.primeCalls++;

    this.display.displayPrime(entityId, results.length, temporalCount, similarityCount, elapsed);

    let insights: { content: string }[] = [];
    try {
      insights = await this.hebbs.insights({ entityId, maxResults: 10 });
    } catch {
      // swallow
    }
    this.display.displayInsights(insights);

    const contextLines = results.map((r) => `- [${r.memory.kind}] ${r.memory.content}`);
    for (const ins of insights) {
      contextLines.push(`- [insight] ${ins.content}`);
    }

    return [contextLines.join('\n'), results];
  }
}
