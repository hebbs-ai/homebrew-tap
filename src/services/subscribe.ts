/**
 * Async wrapper for the HEBBS SubscribeService gRPC methods.
 */

import type { Metadata } from '@grpc/grpc-js';
import { mapGrpcError } from '../errors.js';
import { grpcUnary, protoToMemory } from '../proto.js';
import type { SubscribePush } from '../types.js';

/* eslint-disable @typescript-eslint/no-explicit-any */

/**
 * Handle for an active HEBBS subscription stream.
 *
 * Use as an async iterator to receive pushes, and call feed() to send text.
 *
 * ```ts
 * const sub = await client.subscribe({ entityId: 'user-123' });
 * await sub.feed('Tell me about user preferences');
 * for await (const push of sub) {
 *   console.log(push.memory.content);
 * }
 * await sub.close();
 * ```
 */
export class Subscription implements AsyncIterable<SubscribePush> {
  private closed = false;

  constructor(
    private readonly _subscriptionId: number,
    private readonly stream: AsyncGenerator<SubscribePush>,
    private readonly feedStub: any,
    private readonly metadata: Metadata,
    private readonly grpcCall: any,
    private readonly tenantId?: string,
  ) {}

  get subscriptionId(): number {
    return this._subscriptionId;
  }

  async feed(text: string): Promise<void> {
    const req: any = {
      subscriptionId: this._subscriptionId,
      text,
    };
    if (this.tenantId) req.tenantId = this.tenantId;

    try {
      await grpcUnary<any>((cb) => this.feedStub.feed(req, this.metadata, cb));
    } catch (e) {
      throw mapGrpcError(e);
    }
  }

  async close(): Promise<void> {
    if (this.closed) return;
    this.closed = true;

    const req: any = { subscriptionId: this._subscriptionId };
    if (this.tenantId) req.tenantId = this.tenantId;

    try {
      await grpcUnary<any>((cb) =>
        this.feedStub.closeSubscription(req, this.metadata, cb),
      );
    } catch {
      // Best-effort close, swallow errors
    }

    if (this.grpcCall && typeof this.grpcCall.cancel === 'function') {
      this.grpcCall.cancel();
    }
  }

  /**
   * Collect pushes for up to `timeoutMs` milliseconds.
   *
   * Returns as soon as the stream ends, the timeout expires, or
   * `maxPushes` have been collected (whichever comes first).
   */
  async listen(timeoutMs: number = 5000, maxPushes?: number): Promise<SubscribePush[]> {
    const pushes: SubscribePush[] = [];
    const deadline = Date.now() + timeoutMs;
    const iter = this.stream;

    while (maxPushes === undefined || pushes.length < maxPushes) {
      const remaining = deadline - Date.now();
      if (remaining <= 0) break;

      const result = await Promise.race([
        iter.next(),
        new Promise<{ done: true; value: undefined }>((resolve) =>
          setTimeout(() => resolve({ done: true, value: undefined }), remaining),
        ),
      ]);

      if (result.done) break;
      pushes.push(result.value);
    }

    return pushes;
  }

  [Symbol.asyncIterator](): AsyncIterator<SubscribePush> {
    return this.stream;
  }
}

export class SubscribeService {
  constructor(
    private readonly stub: any,
    private readonly metadata: Metadata,
    private readonly tenantId?: string,
  ) {}

  async subscribe(
    entityId?: string,
    confidenceThreshold: number = 0.5,
  ): Promise<Subscription> {
    const req: any = { confidenceThreshold };
    if (entityId) req.entityId = entityId;
    if (this.tenantId) req.tenantId = this.tenantId;

    let grpcCall: any;
    let subId: number;

    try {
      grpcCall = this.stub.subscribe(req, this.metadata);
      const handshake = await new Promise<any>((resolve, reject) => {
        let resolved = false;
        grpcCall.on('data', (msg: any) => {
          if (!resolved) {
            resolved = true;
            resolve(msg);
          }
        });
        grpcCall.on('error', (err: any) => {
          if (!resolved) {
            resolved = true;
            reject(err);
          }
        });
        grpcCall.on('end', () => {
          if (!resolved) {
            resolved = true;
            reject(new Error('Stream ended before handshake'));
          }
        });
      });

      subId =
        handshake.subscriptionId ?? handshake.subscription_id ?? 0;
    } catch (e) {
      throw mapGrpcError(e);
    }

    const metadata = this.metadata;
    const dataStream = createDataStream(grpcCall);

    return new Subscription(
      subId,
      dataStream,
      this.stub,
      metadata,
      grpcCall,
      this.tenantId,
    );
  }
}

async function* createDataStream(
  grpcCall: any,
): AsyncGenerator<SubscribePush> {
  const buffer: any[] = [];
  let resolve: (() => void) | null = null;
  let done = false;
  let streamError: Error | null = null;

  grpcCall.on('data', (msg: any) => {
    if (msg.memory) {
      buffer.push(msg);
      if (resolve) {
        const r = resolve;
        resolve = null;
        r();
      }
    }
  });

  grpcCall.on('error', (err: any) => {
    streamError = err;
    done = true;
    if (resolve) {
      const r = resolve;
      resolve = null;
      r();
    }
  });

  grpcCall.on('end', () => {
    done = true;
    if (resolve) {
      const r = resolve;
      resolve = null;
      r();
    }
  });

  while (true) {
    if (buffer.length > 0) {
      const msg = buffer.shift()!;
      yield {
        subscriptionId: msg.subscriptionId ?? msg.subscription_id ?? 0,
        memory: protoToMemory(msg.memory),
        confidence: msg.confidence ?? 0,
        pushTimestampUs: msg.pushTimestampUs ?? msg.push_timestamp_us ?? 0,
        sequenceNumber: msg.sequenceNumber ?? msg.sequence_number ?? 0,
      };
      continue;
    }

    if (done) {
      if (streamError) throw mapGrpcError(streamError);
      return;
    }

    await new Promise<void>((r) => {
      resolve = r;
    });
  }
}

/* eslint-enable @typescript-eslint/no-explicit-any */
