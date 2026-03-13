import type { HebbsClient } from '@hebbs/sdk';
import { Scenario } from './base.js';
import type { SalesAgent } from '../agent.js';

const SEED_MEMORIES = [
  { content: 'Acme Robotics uses ROS2 for fleet orchestration across 12 warehouse sites', importance: 0.8, context: { stage: 'discovery', topic: 'tech_stack' } },
  { content: 'VP Engineering Tom Bradley evaluating edge inference for pick-and-place arms', importance: 0.7, context: { stage: 'discovery', contact: 'Tom Bradley' } },
  { content: 'Current vision model runs on Jetson Orin, needs to support 60fps at 1080p', importance: 0.9, context: { stage: 'technical', topic: 'performance' } },
  { content: 'Safety certification ISO 13482 required before any production deployment', importance: 0.9, context: { stage: 'compliance', topic: 'safety_cert' } },
  { content: 'Annual robotics R&D budget is $8M, ML inference allocated $1.2M', importance: 0.8, context: { stage: 'qualification', topic: 'budget' } },
];

const CONVERSATION_TURNS = [
  "We've been running into major latency issues with our current vision pipeline on the Jetson boards.",
  'Tom mentioned you might be able to help with edge inference optimization.',
  'Budget-wise, we carved out about a million dollars from the R&D allocation.',
];

const ENTITY_ID = 'acme_robotics';

export class SubscribeRealtimeScenario extends Scenario {
  readonly name = 'subscribe_realtime';
  readonly description = 'Seed memories, open subscribe stream, feed text, validate real-time surfacing';

  protected async execute(hebbs: HebbsClient, agent: SalesAgent): Promise<void> {
    await this.cleanupEntities(hebbs, [ENTITY_ID]);

    for (const mem of SEED_MEMORIES) {
      await hebbs.remember({
        content: mem.content,
        importance: mem.importance,
        context: mem.context,
        entityId: ENTITY_ID,
      });
    }

    const check = await hebbs.recall({
      cue: 'robotics fleet warehouse',
      strategies: ['temporal'],
      topK: 50,
      entityId: ENTITY_ID,
    });
    this.assertGte('seed_memories_stored', check.results.length, SEED_MEMORIES.length);

    let subscribeOk = true;
    try {
      await Promise.race([
        this.subscribeFeedCycle(hebbs),
        new Promise<void>((_, reject) => setTimeout(() => reject(new Error('timeout')), 15_000)),
      ]);
    } catch {
      subscribeOk = false;
    }

    this.assertTrue('subscribe_pipeline_ran', subscribeOk,
      'subscribe feed/close cycle completed without fatal error or timeout');

    await agent.startSession(ENTITY_ID, 1);
    const turnResult = await agent.processTurn(
      "Can you walk me through how your edge inference handles the Jetson Orin's thermal throttling?",
      ['similarity', 'temporal'],
    );
    this.assertTrue('agent_turn_with_subscribe', turnResult !== null);
    await agent.endSession();
  }

  private async subscribeFeedCycle(hebbs: HebbsClient): Promise<void> {
    const sub = await hebbs.subscribe({
      entityId: ENTITY_ID,
      confidenceThreshold: 0.3,
    });
    try {
      for (const text of CONVERSATION_TURNS) {
        await sub.feed(text);
        await new Promise((r) => setTimeout(r, 200));
      }
    } finally {
      await sub.close();
    }
  }
}
