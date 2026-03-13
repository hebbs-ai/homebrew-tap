import chalk from 'chalk';

export type Verbosity = 'quiet' | 'normal' | 'verbose';

export interface OperationRecord {
  operation: string;
  latencyMs: number;
  summary: string;
  details: string[];
  highlightColor: string;
}

export class DisplayManager {
  private records: OperationRecord[] = [];

  constructor(
    private verbosity: Verbosity = 'normal',
  ) {}

  startTurn(): void {
    this.records = [];
  }

  recordOperation(record: OperationRecord): void {
    this.records.push(record);
  }

  displaySessionHeader(entityId: string, sessionNum?: number): void {
    if (this.verbosity === 'quiet') return;
    const label = sessionNum ? `Session ${sessionNum}` : 'Session';
    console.log(chalk.cyan(`\n  ── ${label}: ${entityId} ──\n`));
  }

  displayProspectMessage(entity: string, message: string): void {
    if (this.verbosity === 'quiet') return;
    console.log(chalk.blue(`  ${entity}: `) + message);
  }

  displayAgentResponse(response: string): void {
    if (this.verbosity === 'quiet') return;
    console.log(chalk.green('  Atlas: ') + response);
  }

  displayTurn(): void {
    if (this.verbosity !== 'verbose') return;
    for (const r of this.records) {
      const color = r.highlightColor === 'green' ? chalk.green
        : r.highlightColor === 'blue' ? chalk.blue
        : r.highlightColor === 'yellow' ? chalk.yellow
        : chalk.white;
      console.log(color(`    [${r.operation}] `) + chalk.dim(`${r.latencyMs.toFixed(0)}ms `) + r.summary);
      for (const d of r.details) {
        console.log(chalk.dim(`      ${d}`));
      }
    }
  }

  displayRecordImmediate(record: OperationRecord): void {
    if (this.verbosity !== 'verbose') return;
    const color = record.highlightColor === 'green' ? chalk.green : chalk.white;
    console.log(color(`    [${record.operation}] `) + chalk.dim(`${record.latencyMs.toFixed(0)}ms `) + record.summary);
  }

  displayPrime(entityId: string, total: number, temporalCount: number, similarityCount: number, latencyMs: number): void {
    if (this.verbosity === 'quiet') return;
    console.log(chalk.cyan(`    [PRIME] `) + chalk.dim(`${latencyMs.toFixed(0)}ms `) +
      `${total} memories loaded (temporal: ${temporalCount}, similarity: ${similarityCount})`);
  }

  displayInsights(insights: { content: string }[]): void {
    if (this.verbosity !== 'verbose' || !insights.length) return;
    console.log(chalk.cyan(`    [INSIGHTS] `) + `${insights.length} insights loaded`);
  }

  displayReflect(memoriesProcessed: number, clustersFound: number, insightsCreated: number, latencyMs: number): void {
    if (this.verbosity === 'quiet') return;
    console.log(chalk.magenta(`    [REFLECT] `) + chalk.dim(`${latencyMs.toFixed(0)}ms `) +
      `processed ${memoriesProcessed} memories, ${clustersFound} clusters, ${insightsCreated} insights`);
  }

  displayForget(entityId: string, forgottenCount: number, cascadeCount: number, tombstoneCount: number, latencyMs: number): void {
    if (this.verbosity === 'quiet') return;
    console.log(chalk.red(`    [FORGET] `) + chalk.dim(`${latencyMs.toFixed(0)}ms `) +
      `${entityId}: ${forgottenCount} forgotten, ${cascadeCount} cascaded, ${tombstoneCount} tombstones`);
  }
}
