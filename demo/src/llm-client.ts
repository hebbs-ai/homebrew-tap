import OpenAI from 'openai';
import type { DemoConfig } from './config.js';

export interface LlmResponse {
  content: string;
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
  model: string;
  provider: string;
}

export interface LlmStats {
  totalCalls: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalLatencyMs: number;
}

export class LlmClient {
  private openai: OpenAI | null = null;
  stats: LlmStats = { totalCalls: 0, totalInputTokens: 0, totalOutputTokens: 0, totalLatencyMs: 0 };

  constructor(private config: DemoConfig) {}

  private getOpenAI(): OpenAI {
    if (!this.openai) {
      const apiKey = process.env[this.config.llm.openai.apiKeyEnv] ?? '';
      this.openai = new OpenAI({ apiKey });
    }
    return this.openai;
  }

  private async call(
    messages: { role: string; content: string }[],
    model: string,
    temperature: number,
  ): Promise<LlmResponse> {
    const client = this.getOpenAI();
    const t0 = performance.now();
    const resp = await client.chat.completions.create({
      model,
      messages: messages as OpenAI.ChatCompletionMessageParam[],
      temperature,
    });
    const elapsed = performance.now() - t0;
    const choice = resp.choices[0];
    const usage = resp.usage;

    const result: LlmResponse = {
      content: choice?.message?.content ?? '',
      inputTokens: usage?.prompt_tokens ?? 0,
      outputTokens: usage?.completion_tokens ?? 0,
      latencyMs: elapsed,
      model,
      provider: 'openai',
    };

    this.stats.totalCalls++;
    this.stats.totalInputTokens += result.inputTokens;
    this.stats.totalOutputTokens += result.outputTokens;
    this.stats.totalLatencyMs += result.latencyMs;

    return result;
  }

  async conversation(messages: { role: string; content: string }[]): Promise<LlmResponse> {
    return this.call(messages, this.config.llm.conversationModel, 0.7);
  }

  async extractMemories(messages: { role: string; content: string }[]): Promise<LlmResponse> {
    return this.call(messages, this.config.llm.extractionModel, 0.1);
  }
}

export class MockLlmClient extends LlmClient {
  private cannedConversation = 'That\'s a great question. Based on what I\'ve seen with similar companies, I\'d recommend we start with a discovery call. What\'s your biggest pain point right now?';
  private cannedExtraction = JSON.stringify({
    memories: [{ content: 'Prospect expressed interest in the product', importance: 0.7, context: { topic: 'general', stage: 'discovery' } }],
    skip_reason: null,
  });

  constructor(config?: DemoConfig) {
    super(config ?? ({} as DemoConfig));
  }

  override async conversation(): Promise<LlmResponse> {
    return { content: this.cannedConversation, inputTokens: 50, outputTokens: 30, latencyMs: 5, model: 'mock', provider: 'mock' };
  }

  override async extractMemories(): Promise<LlmResponse> {
    return { content: this.cannedExtraction, inputTokens: 40, outputTokens: 20, latencyMs: 5, model: 'mock', provider: 'mock' };
  }
}
