import type { Scenario } from './base.js';
import { DiscoveryCallScenario } from './discovery-call.js';
import { MultiSessionScenario } from './multi-session.js';
import { SubscribeRealtimeScenario } from './subscribe-realtime.js';

export { Scenario, type ScenarioResult, type Assertion } from './base.js';
export { DiscoveryCallScenario } from './discovery-call.js';
export { MultiSessionScenario } from './multi-session.js';
export { SubscribeRealtimeScenario } from './subscribe-realtime.js';

export const ALL_SCENARIOS: Record<string, new (...args: ConstructorParameters<typeof DiscoveryCallScenario>) => Scenario> = {
  discovery_call: DiscoveryCallScenario,
  multi_session: MultiSessionScenario,
  subscribe_realtime: SubscribeRealtimeScenario,
};
