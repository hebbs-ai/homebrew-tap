import { HebbsClient } from '@hebbs/sdk';
import type { DemoConfig } from '../config.js';
import { DisplayManager, type Verbosity } from '../display.js';
import { SalesAgent } from '../agent.js';

export interface Assertion {
  name: string;
  passed: boolean;
  message: string;
}

export interface ScenarioResult {
  name: string;
  passed: boolean;
  assertions: Assertion[];
  elapsedMs: number;
  error?: string;
}

export abstract class Scenario {
  abstract readonly name: string;
  abstract readonly description: string;
  protected assertions: Assertion[] = [];

  constructor(
    protected config: DemoConfig,
    protected verbosity: Verbosity = 'normal',
    protected useMockLlm = true,
  ) {}

  protected assertTrue(name: string, condition: boolean, message = ''): void {
    this.assertions.push({ name, passed: condition, message });
  }

  protected assertGte(name: string, actual: number, minimum: number, message = ''): void {
    this.assertions.push({
      name,
      passed: actual >= minimum,
      message: message || `expected >= ${minimum}, got ${actual}`,
    });
  }

  protected assertNotEmpty(name: string, collection: unknown[], message = ''): void {
    this.assertions.push({
      name,
      passed: collection.length > 0,
      message: message || 'expected non-empty collection',
    });
  }

  protected async setup(): Promise<[HebbsClient, SalesAgent]> {
    const hebbs = new HebbsClient(this.config.hebbs.address);
    await hebbs.connect();
    const display = new DisplayManager(this.verbosity);
    const agent = new SalesAgent(this.config, hebbs, display, this.useMockLlm);
    return [hebbs, agent];
  }

  protected async cleanupEntities(hebbs: HebbsClient, entityIds: string[]): Promise<void> {
    for (const eid of entityIds) {
      try { await hebbs.forget({ entityId: eid }); } catch { /* ignore */ }
    }
  }

  async run(): Promise<ScenarioResult> {
    this.assertions = [];
    const t0 = performance.now();

    let hebbs: HebbsClient;
    let agent: SalesAgent;
    try {
      [hebbs, agent] = await this.setup();
    } catch (e) {
      return { name: this.name, passed: false, assertions: [], elapsedMs: 0, error: `Setup failed: ${e}` };
    }

    try {
      await this.execute(hebbs, agent);
    } catch (e) {
      this.assertions.push({ name: 'scenario_execution', passed: false, message: `Exception: ${e}` });
    } finally {
      try { await hebbs.close(); } catch { /* ignore */ }
    }

    const elapsed = performance.now() - t0;
    return {
      name: this.name,
      passed: this.assertions.every((a) => a.passed),
      assertions: [...this.assertions],
      elapsedMs: elapsed,
    };
  }

  protected abstract execute(hebbs: HebbsClient, agent: SalesAgent): Promise<void>;
}
