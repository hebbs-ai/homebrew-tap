/**
 * Async wrapper for the HEBBS HealthService gRPC method.
 */

import type { Metadata } from '@grpc/grpc-js';
import { mapGrpcError } from '../errors.js';
import { grpcUnary, SERVING_STATUS_SERVING } from '../proto.js';
import type { HealthStatus } from '../types.js';

/* eslint-disable @typescript-eslint/no-explicit-any */

export class HealthService {
  constructor(
    private readonly stub: any,
    private readonly metadata: Metadata,
  ) {}

  async check(): Promise<HealthStatus> {
    try {
      const resp = await grpcUnary<any>((cb) =>
        this.stub.check({}, this.metadata, cb),
      );
      return {
        serving: resp.status === SERVING_STATUS_SERVING,
        version: resp.version ?? '',
        memoryCount: resp.memoryCount ?? resp.memory_count ?? 0,
        uptimeSeconds: resp.uptimeSeconds ?? resp.uptime_seconds ?? 0,
      };
    } catch (e) {
      throw mapGrpcError(e);
    }
  }
}

/* eslint-enable @typescript-eslint/no-explicit-any */
