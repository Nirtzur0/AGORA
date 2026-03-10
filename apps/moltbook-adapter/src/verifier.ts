/**
 * Moltbook identity token verification service.
 * 
 * Handles:
 * - Identity token verification against Moltbook
 * - Short-TTL caching to reduce load
 * - Circuit breaker to prevent request storms
 * - Structured error codes
 */

import axios, { AxiosError } from 'axios';
import NodeCache from 'node-cache';
import { Config } from './config';
import { CircuitBreaker } from './circuit-breaker';

export interface VerificationResult {
  moltbook_id: string;
  name: string;
  reputation: number;
  profile_meta?: Record<string, any>;
}

export enum ErrorCode {
  INVALID_TOKEN = 'INVALID_TOKEN',
  EXPIRED_TOKEN = 'EXPIRED_TOKEN',
  UPSTREAM_UNAVAILABLE = 'UPSTREAM_UNAVAILABLE',
  CIRCUIT_OPEN = 'CIRCUIT_OPEN',
  INVALID_RESPONSE = 'INVALID_RESPONSE',
  REDIRECT_NOT_ALLOWED = 'REDIRECT_NOT_ALLOWED',
}

export class VerificationError extends Error {
  constructor(
    public readonly code: ErrorCode,
    message: string,
    public readonly retryAfter?: number
  ) {
    super(message);
    this.name = 'VerificationError';
  }
}

export class MoltbookVerifier {
  private cache: NodeCache;
  private circuitBreaker: CircuitBreaker;

  constructor(private readonly config: Config) {
    // Cache with TTL
    this.cache = new NodeCache({
      stdTTL: config.verificationCacheTtl,
      checkperiod: config.verificationCacheTtl / 2,
    });

    // Circuit breaker (timeout in seconds, convert to ms)
    this.circuitBreaker = new CircuitBreaker(
      config.circuitBreakerThreshold,
      config.circuitBreakerTimeout * 1000
    );
  }

  private buildDebugVerification(identityToken: string): VerificationResult {
    const rawSlug = identityToken.replace(/^debug-token-/, '').trim();
    const normalizedSlug = rawSlug
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 40) || 'user';

    const nameSuffix = normalizedSlug
      .split('-')
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');

    return {
      moltbook_id: `mb_debug_${normalizedSlug}`,
      name: nameSuffix ? `Debug ${nameSuffix}` : 'Debug User',
      reputation: 999,
      profile_meta: {
        role: 'debugger',
        environment: 'local',
        debug_identity: identityToken,
      },
    };
  }

  /**
   * Verify a Moltbook identity token.
   * 
   * @param identityToken - Raw Moltbook identity token
   * @returns Verification result with moltbook_id, name, reputation
   * @throws VerificationError with specific error code
   */
  async verify(identityToken: string): Promise<VerificationResult> {
    // Check cache first
    const cached = this.cache.get<VerificationResult>(identityToken);
    if (cached) {
      return cached;
    }

    // DEBUG MODE BYPASS
    if (this.config.enableDebugMode && identityToken.startsWith('debug-token-')) {
      console.log('DEBUG MODE: Bypassing Moltbook verification for debug token');
      const debugResult = this.buildDebugVerification(identityToken);
      this.cache.set(identityToken, debugResult);
      return debugResult;
    }

    // Check circuit breaker
    if (!this.circuitBreaker.canAttempt()) {
      throw new VerificationError(
        ErrorCode.CIRCUIT_OPEN,
        'Moltbook verification service is temporarily unavailable',
        this.config.circuitBreakerTimeout
      );
    }

    try {
      // Call Moltbook verification endpoint
      // Per spec: send app key as X-Moltbook-App-Key header
      const response = await axios.post(
        `${this.config.moltbookBaseUrl}/api/verify`,
        { identity_token: identityToken },
        {
          headers: {
            'X-Moltbook-App-Key': this.config.moltbookAppKey,
            'Content-Type': 'application/json',
          },
          // Critical: do not follow redirects (per spec - avoid auth header loss)
          maxRedirects: 0,
          validateStatus: (status) => status < 400 || status === 401 || status === 403,
          timeout: 10000, // 10 second timeout
        }
      );

      // Handle redirects explicitly
      if (response.status >= 300 && response.status < 400) {
        this.circuitBreaker.recordFailure();
        throw new VerificationError(
          ErrorCode.REDIRECT_NOT_ALLOWED,
          'Moltbook returned a redirect - this may indicate misconfiguration'
        );
      }

      // Handle auth failures
      if (response.status === 401 || response.status === 403) {
        this.circuitBreaker.recordSuccess(); // Not an upstream failure
        throw new VerificationError(
          ErrorCode.INVALID_TOKEN,
          'Invalid or expired identity token'
        );
      }

      // Validate response structure
      const data = response.data;
      if (!data.moltbook_id || !data.name || data.reputation === undefined) {
        this.circuitBreaker.recordFailure();
        throw new VerificationError(
          ErrorCode.INVALID_RESPONSE,
          'Moltbook returned invalid response structure'
        );
      }

      const result: VerificationResult = {
        moltbook_id: data.moltbook_id,
        name: data.name,
        reputation: data.reputation,
        profile_meta: data.profile_meta,
      };

      // Cache successful verification
      this.cache.set(identityToken, result);
      this.circuitBreaker.recordSuccess();

      return result;
    } catch (error) {
      // Re-throw VerificationError as-is
      if (error instanceof VerificationError) {
        throw error;
      }

      // Handle axios errors
      if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError;

        // Timeout or network error
        if (!axiosError.response) {
          this.circuitBreaker.recordFailure();
          throw new VerificationError(
            ErrorCode.UPSTREAM_UNAVAILABLE,
            'Moltbook verification service is unavailable',
            this.config.circuitBreakerTimeout
          );
        }

        // Server error (5xx)
        if (axiosError.response.status >= 500) {
          this.circuitBreaker.recordFailure();
          throw new VerificationError(
            ErrorCode.UPSTREAM_UNAVAILABLE,
            'Moltbook verification service error',
            this.config.circuitBreakerTimeout
          );
        }

        // Client error (4xx) that we didn't handle above
        this.circuitBreaker.recordSuccess(); // Not an upstream failure
        throw new VerificationError(
          ErrorCode.INVALID_TOKEN,
          `Verification failed: ${axiosError.response.status}`
        );
      }

      // Unknown error
      this.circuitBreaker.recordFailure();
      throw new VerificationError(
        ErrorCode.UPSTREAM_UNAVAILABLE,
        'Unexpected error during verification'
      );
    }
  }

  /**
   * Get circuit breaker state (for monitoring).
   */
  getCircuitState() {
    return this.circuitBreaker.getState();
  }

  /**
   * Get cache stats (for monitoring).
   */
  getCacheStats() {
    return this.cache.getStats();
  }
}
