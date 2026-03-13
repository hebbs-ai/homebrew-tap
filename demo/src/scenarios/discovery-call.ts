import type { HebbsClient } from '@hebbs/sdk';
import { Scenario } from './base.js';
import type { SalesAgent } from '../agent.js';

const ENTITY = 'acme_corp';

const TURNS = [
  "Hi, I'm Sarah Chen, VP of Engineering at Acme Corp. We have about 200 developers across three offices.",
  'Our biggest pain point is knowledge silos. Teams in Berlin, Austin, and Singapore keep re-solving the same problems.',
  'We tried Confluence and Notion but adoption dropped off after a few months.',
  'What we really need is something that captures knowledge passively -- without forcing engineers to write things down.',
  'We\'re also dealing with high attrition. When senior engineers leave, all their context walks out the door.',
  'Budget-wise, we have about $150K allocated for developer tooling this quarter.',
  "Integration is critical. We're all-in on GitHub, Slack, and Linear.",
  "Our CTO, Marcus, is the final decision-maker. He's very data-driven.",
  'Timeline is aggressive. We\'re hoping to pilot with one team in Q2 and roll out by end of Q3.',
  'Can you send over a technical architecture doc? Marcus will want to review data residency.',
];

export class DiscoveryCallScenario extends Scenario {
  readonly name = 'discovery_call';
  readonly description = 'Single-session discovery call validating memory formation and similarity recall';

  protected async execute(hebbs: HebbsClient, agent: SalesAgent): Promise<void> {
    await this.cleanupEntities(hebbs, [ENTITY]);
    await agent.startSession(ENTITY, 1);

    const turnResults = [];
    for (let i = 0; i < TURNS.length; i++) {
      const strategies = i >= 3 ? ['similarity'] : undefined;
      const result = await agent.processTurn(TURNS[i], strategies);
      turnResults.push(result);
    }
    await agent.endSession();

    const lateRecalls = turnResults.slice(5).reduce((s, t) => s + t.memoriesRecalled, 0);
    this.assertGte('recall_active_mid_conversation', lateRecalls, 1,
      `Expected recalls in later turns, got ${lateRecalls}`);

    const recallOut = await hebbs.recall({
      cue: 'engineering team knowledge management',
      strategies: ['similarity'],
      topK: 10,
      entityId: ENTITY,
    });
    this.assertNotEmpty('similarity_recall_returns_results', recallOut.results);

    const withContext = recallOut.results.filter((r) =>
      r.memory.context && Object.keys(r.memory.context).length > 0,
    ).length;
    this.assertGte('memories_have_context_metadata', withContext, 1);

    const entityScoped = recallOut.results.filter((r) => r.memory.entityId === ENTITY);
    this.assertNotEmpty('recall_has_entity_memories', entityScoped);

    this.assertTrue('no_strategy_errors', recallOut.strategyErrors.length === 0);

    const finalRecall = await hebbs.recall({
      cue: 'acme corp engineering knowledge',
      strategies: ['temporal'],
      topK: 100,
      entityId: ENTITY,
    });
    const entityMems = finalRecall.results.filter((r) => r.memory.entityId === ENTITY);
    this.assertGte('total_memory_count', entityMems.length, 5,
      `Expected at least 5 memories, got ${entityMems.length}`);
  }
}
