/**
 * HEBBS SDK exception hierarchy, mapped from gRPC status codes.
 */

import { status as GrpcStatus, type ServiceError } from '@grpc/grpc-js';

export class HebbsError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'HebbsError';
  }
}

export class HebbsConnectionError extends HebbsError {
  constructor(message: string) {
    super(message);
    this.name = 'HebbsConnectionError';
  }
}

export class HebbsTimeoutError extends HebbsError {
  constructor(message: string) {
    super(message);
    this.name = 'HebbsTimeoutError';
  }
}

export class HebbsNotFoundError extends HebbsError {
  constructor(message: string) {
    super(message);
    this.name = 'HebbsNotFoundError';
  }
}

export class HebbsUnavailableError extends HebbsError {
  constructor(message: string) {
    super(message);
    this.name = 'HebbsUnavailableError';
  }
}

export class HebbsInvalidArgumentError extends HebbsError {
  constructor(message: string) {
    super(message);
    this.name = 'HebbsInvalidArgumentError';
  }
}

export class HebbsInternalError extends HebbsError {
  constructor(message: string) {
    super(message);
    this.name = 'HebbsInternalError';
  }
}

export class HebbsAuthenticationError extends HebbsError {
  constructor(message: string) {
    super(message);
    this.name = 'HebbsAuthenticationError';
  }
}

export class HebbsPermissionDeniedError extends HebbsError {
  constructor(message: string) {
    super(message);
    this.name = 'HebbsPermissionDeniedError';
  }
}

export class HebbsRateLimitError extends HebbsError {
  constructor(message: string) {
    super(message);
    this.name = 'HebbsRateLimitError';
  }
}

const STATUS_MAP: Record<number, new (msg: string) => HebbsError> = {
  [GrpcStatus.UNAVAILABLE]: HebbsUnavailableError,
  [GrpcStatus.DEADLINE_EXCEEDED]: HebbsTimeoutError,
  [GrpcStatus.NOT_FOUND]: HebbsNotFoundError,
  [GrpcStatus.INVALID_ARGUMENT]: HebbsInvalidArgumentError,
  [GrpcStatus.INTERNAL]: HebbsInternalError,
  [GrpcStatus.UNAUTHENTICATED]: HebbsAuthenticationError,
  [GrpcStatus.PERMISSION_DENIED]: HebbsPermissionDeniedError,
  [GrpcStatus.RESOURCE_EXHAUSTED]: HebbsRateLimitError,
};

/**
 * Convert a gRPC ServiceError into the appropriate HebbsError subclass.
 */
export function mapGrpcError(err: unknown): HebbsError {
  if (err instanceof HebbsError) return err;

  const svcErr = err as ServiceError;
  if (svcErr.code !== undefined && svcErr.code !== null) {
    const details = svcErr.details || svcErr.message || String(err);
    const Cls = STATUS_MAP[svcErr.code];
    if (Cls) return new Cls(details);
    return new HebbsError(details);
  }

  return new HebbsError(String(err));
}
