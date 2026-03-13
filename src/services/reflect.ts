/**
 * Async wrapper for the HEBBS ReflectService gRPC methods.
 */

import type { Metadata } from '@grpc/grpc-js';
import { mapGrpcError } from '../errors.js';
import { grpcUnary, protoToMemory } from '../proto.js';
import type { Memory, ReflectResult } from '../types.js';

/* eslint-disable @typescript-eslint/no-explicit-any */

export class ReflectService {
  constructor(
    private readonly stub: any,
    private readonly metadata: Metadata,
    private readonly tenantId?: string,
  ) {}

  async reflect(entityId?: string): Promise<ReflectResult> {
    const scope: any = {};
    if (entityId) {
      scope.entity = { entityId };
    } else {
      scope.global = {};
    }

    const req: any = { scope };
    if (this.tenantId) req.tenantId = this.tenantId;

    try {
      const resp = await grpcUnary<any>((cb) =>
        this.stub.reflect(req, this.metadata, cb),
      );
      return {
        insightsCreated: resp.insightsCreated ?? resp.insights_created ?? 0,
        clustersFound: resp.clustersFound ?? resp.clusters_found ?? 0,
        clustersProcessed:
          resp.clustersProcessed ?? resp.clusters_processed ?? 0,
        memoriesProcessed:
          resp.memoriesProcessed ?? resp.memories_processed ?? 0,
      };
    } catch (e) {
      throw mapGrpcError(e);
    }
  }

  async getInsights(
    entityId?: string,
    maxResults?: number,
  ): Promise<Memory[]> {
    const req: any = {};
    if (entityId) req.entityId = entityId;
    if (maxResults !== undefined) req.maxResults = maxResults;
    if (this.tenantId) req.tenantId = this.tenantId;

    try {
      const resp = await grpcUnary<any>((cb) =>
        this.stub.getInsights(req, this.metadata, cb),
      );
      return (resp.insights ?? []).map(protoToMemory);
    } catch (e) {
      throw mapGrpcError(e);
    }
  }
}

/* eslint-enable @typescript-eslint/no-explicit-any */
