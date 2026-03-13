import { describe, it, expect } from 'vitest';
import { status as GrpcStatus } from '@grpc/grpc-js';
import {
  HebbsError,
  HebbsConnectionError,
  HebbsTimeoutError,
  HebbsNotFoundError,
  HebbsUnavailableError,
  HebbsInvalidArgumentError,
  HebbsInternalError,
  HebbsAuthenticationError,
  HebbsPermissionDeniedError,
  HebbsRateLimitError,
} from '../../src/errors.js';
import { mapGrpcError } from '../../src/errors.js';

describe('Error hierarchy', () => {
  it('all errors extend HebbsError', () => {
    const errors = [
      new HebbsConnectionError('conn'),
      new HebbsTimeoutError('timeout'),
      new HebbsNotFoundError('not found'),
      new HebbsUnavailableError('unavailable'),
      new HebbsInvalidArgumentError('invalid'),
      new HebbsInternalError('internal'),
      new HebbsAuthenticationError('auth'),
      new HebbsPermissionDeniedError('denied'),
      new HebbsRateLimitError('rate limit'),
    ];

    for (const err of errors) {
      expect(err).toBeInstanceOf(HebbsError);
      expect(err).toBeInstanceOf(Error);
      expect(err.message).toBeTruthy();
    }
  });

  it('each error has correct name', () => {
    expect(new HebbsError('test').name).toBe('HebbsError');
    expect(new HebbsConnectionError('test').name).toBe('HebbsConnectionError');
    expect(new HebbsTimeoutError('test').name).toBe('HebbsTimeoutError');
    expect(new HebbsNotFoundError('test').name).toBe('HebbsNotFoundError');
    expect(new HebbsUnavailableError('test').name).toBe('HebbsUnavailableError');
    expect(new HebbsInvalidArgumentError('test').name).toBe('HebbsInvalidArgumentError');
    expect(new HebbsInternalError('test').name).toBe('HebbsInternalError');
    expect(new HebbsAuthenticationError('test').name).toBe('HebbsAuthenticationError');
    expect(new HebbsPermissionDeniedError('test').name).toBe('HebbsPermissionDeniedError');
    expect(new HebbsRateLimitError('test').name).toBe('HebbsRateLimitError');
  });
});

describe('mapGrpcError', () => {
  function fakeGrpcError(code: number, details: string): unknown {
    return { code, details, message: details };
  }

  it('maps UNAVAILABLE to HebbsUnavailableError', () => {
    const err = mapGrpcError(fakeGrpcError(GrpcStatus.UNAVAILABLE, 'server down'));
    expect(err).toBeInstanceOf(HebbsUnavailableError);
    expect(err.message).toBe('server down');
  });

  it('maps DEADLINE_EXCEEDED to HebbsTimeoutError', () => {
    const err = mapGrpcError(fakeGrpcError(GrpcStatus.DEADLINE_EXCEEDED, 'timeout'));
    expect(err).toBeInstanceOf(HebbsTimeoutError);
  });

  it('maps NOT_FOUND to HebbsNotFoundError', () => {
    const err = mapGrpcError(fakeGrpcError(GrpcStatus.NOT_FOUND, 'memory not found'));
    expect(err).toBeInstanceOf(HebbsNotFoundError);
  });

  it('maps INVALID_ARGUMENT to HebbsInvalidArgumentError', () => {
    const err = mapGrpcError(fakeGrpcError(GrpcStatus.INVALID_ARGUMENT, 'bad input'));
    expect(err).toBeInstanceOf(HebbsInvalidArgumentError);
  });

  it('maps INTERNAL to HebbsInternalError', () => {
    const err = mapGrpcError(fakeGrpcError(GrpcStatus.INTERNAL, 'server error'));
    expect(err).toBeInstanceOf(HebbsInternalError);
  });

  it('maps UNAUTHENTICATED to HebbsAuthenticationError', () => {
    const err = mapGrpcError(fakeGrpcError(GrpcStatus.UNAUTHENTICATED, 'no key'));
    expect(err).toBeInstanceOf(HebbsAuthenticationError);
  });

  it('maps PERMISSION_DENIED to HebbsPermissionDeniedError', () => {
    const err = mapGrpcError(fakeGrpcError(GrpcStatus.PERMISSION_DENIED, 'forbidden'));
    expect(err).toBeInstanceOf(HebbsPermissionDeniedError);
  });

  it('maps RESOURCE_EXHAUSTED to HebbsRateLimitError', () => {
    const err = mapGrpcError(fakeGrpcError(GrpcStatus.RESOURCE_EXHAUSTED, 'rate limited'));
    expect(err).toBeInstanceOf(HebbsRateLimitError);
  });

  it('maps unknown gRPC codes to base HebbsError', () => {
    const err = mapGrpcError(fakeGrpcError(GrpcStatus.ABORTED, 'aborted'));
    expect(err).toBeInstanceOf(HebbsError);
    expect(err.message).toBe('aborted');
  });

  it('passes through HebbsError instances unchanged', () => {
    const original = new HebbsNotFoundError('original');
    const mapped = mapGrpcError(original);
    expect(mapped).toBe(original);
  });

  it('wraps unknown errors as HebbsError', () => {
    const err = mapGrpcError(new Error('generic'));
    expect(err).toBeInstanceOf(HebbsError);
    expect(err.message).toContain('generic');
  });

  it('wraps string errors', () => {
    const err = mapGrpcError('string error');
    expect(err).toBeInstanceOf(HebbsError);
    expect(err.message).toBe('string error');
  });
});
