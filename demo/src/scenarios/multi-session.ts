import type { HebbsClient } from '@hebbs/sdk';
import { Scenario } from './base.js';
import type { SalesAgent } from '../agent.js';

const ENTITY = 'delta_corp';

const SESSIONS: string[][] = [
  [
    "Hi, I'm Raj Patel, CTO at Delta Corp. We're a fintech startup with about 50 engineers.",
    "We're building a real-time fraud detection platform and need persistent memory for our ML pipeline.",
    "Current architecture stores embeddings in Pinecone but we're hitting consistency issues at scale.",
  ],
  [
    'Following up from our first call. I discussed HEBBS with my team.',
    'Our lead ML engineer asked about the causal graph. Can memories form directed edges automatically?',
    "What's the write throughput like? We're ingesting about 10K events per second during peak.",
  ],
  [
    'Good news -- the team is excited after reviewing the architecture doc.',
    'We ran your benchmark suite against our Pinecone setup. HEBBS was 3x faster on recall.',
    'Raj wants to start a PoC. Can we get a trial license for the embedded engine?',
  ],
  [
    "We've been running the PoC for a week. Causal recall is a game-changer for fraud chains.",
    'One issue: memory compaction is taking longer than expected during off-peak batch runs.',
    'Compliance needs clarification on data residency. SOC2 and PCI-DSS regulated.',
  ],
  [
    "We're ready to move forward. PoC results convinced leadership -- 40% faster fraud detection.",
    'Budget approved. 100-seat license to start, scale from there.',
    'Can we schedule technical onboarding for next week? Want to go live before end of quarter.',
  ],
];

export class MultiSessionScenario extends Scenario {
  readonly name = 'multi_session';
  readonly description = 'Five-session relationship validating temporal recall, prime, and memory growth';

  protected async execute(hebbs: HebbsClient, agent: SalesAgent): Promise<void> {
    await this.cleanupEntities(hebbs, [ENTITY]);
    const countsAfterSession: number[] = [];

    for (let si = 0; si < SESSIONS.length; si++) {
      await agent.startSession(ENTITY, si + 1);
      for (const msg of SESSIONS[si]) {
        await agent.processTurn(msg, ['similarity', 'temporal']);
      }
      await agent.endSession();

      const check = await hebbs.recall({
        cue: 'delta corp fintech fraud detection',
        strategies: ['temporal'],
        topK: 200,
        entityId: ENTITY,
      });
      countsAfterSession.push(check.results.length);
    }

    for (let i = 1; i < countsAfterSession.length; i++) {
      this.assertGte(
        `memory_growth_session_${i + 1}`,
        countsAfterSession[i],
        countsAfterSession[i - 1],
        `Session ${i + 1} count (${countsAfterSession[i]}) should be >= session ${i} (${countsAfterSession[i - 1]})`,
      );
    }

    this.assertGte('total_memories_after_all_sessions', countsAfterSession.at(-1) ?? 0, 10);

    const temporal = await hebbs.recall({
      cue: 'Delta Corp engagement history',
      strategies: ['temporal'],
      topK: 20,
      entityId: ENTITY,
    });
    this.assertNotEmpty('temporal_recall_returns_results', temporal.results);

    const primeOut = await hebbs.prime({ entityId: ENTITY, maxMemories: 50 });
    this.assertNotEmpty('prime_returns_accumulated_context', primeOut.results);
    this.assertGte('prime_result_count', primeOut.results.length, 3);
  }
}
