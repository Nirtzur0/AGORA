/**
 * Moltbook Adapter HTTP Server
 * 
 * Provides POST /verify endpoint for identity token verification.
 */

import express, { Request, Response, NextFunction } from 'express';
import { Config } from './config';
import { MoltbookVerifier, VerificationError, ErrorCode } from './verifier';

export function createApp(config: Config): express.Application {
  const app = express();
  const verifier = new MoltbookVerifier(config);

  // Parse JSON bodies
  app.use(express.json());

  // Request logging
  app.use((req, _res, next) => {
    console.log(`${new Date().toISOString()} ${req.method} ${req.path}`);
    next();
  });

  /**
   * POST /verify
   * 
   * Verify a Moltbook identity token.
   * 
   * Request body:
   *   { identity_token: string }
   * 
   * Success response (200):
   *   { moltbook_id, name, reputation, profile_meta? }
   * 
   * Error responses:
   *   401: Invalid/expired token
   *   503: Upstream unavailable (with Retry-After header)
   */
  app.post('/verify', async (req: Request, res: Response) => {
    try {
      const { identity_token } = req.body;

      if (!identity_token || typeof identity_token !== 'string') {
        return res.status(400).json({
          error: 'BAD_REQUEST',
          message: 'identity_token is required and must be a string',
        });
      }

      const result = await verifier.verify(identity_token);

      return res.status(200).json(result);
    } catch (error) {
      if (error instanceof VerificationError) {
        // Map error codes to HTTP status
        switch (error.code) {
          case ErrorCode.INVALID_TOKEN:
          case ErrorCode.EXPIRED_TOKEN:
            return res.status(401).json({
              error: error.code,
              message: error.message,
            });

          case ErrorCode.UPSTREAM_UNAVAILABLE:
          case ErrorCode.CIRCUIT_OPEN:
            // Include Retry-After header per spec
            if (error.retryAfter) {
              res.set('Retry-After', error.retryAfter.toString());
            }
            return res.status(503).json({
              error: error.code,
              message: error.message,
            });

          case ErrorCode.REDIRECT_NOT_ALLOWED:
          case ErrorCode.INVALID_RESPONSE:
            return res.status(502).json({
              error: error.code,
              message: error.message,
            });

          default:
            return res.status(500).json({
              error: 'INTERNAL_ERROR',
              message: 'Unexpected verification error',
            });
        }
      }

      // Unknown error
      console.error('Unexpected error:', error);
      return res.status(500).json({
        error: 'INTERNAL_ERROR',
        message: 'An unexpected error occurred',
      });
    }
  });

  /**
   * GET /health
   * 
   * Health check endpoint.
   */
  app.get('/health', (_req: Request, res: Response) => {
    res.status(200).json({
      status: 'healthy',
      service: 'moltbook-adapter',
      circuit_state: verifier.getCircuitState(),
      cache_stats: verifier.getCacheStats(),
    });
  });

  /**
   * GET /
   * 
   * Root endpoint with service info.
   */
  app.get('/', (_req: Request, res: Response) => {
    res.status(200).json({
      service: 'AGORA Moltbook Adapter',
      version: '1.0.0',
      endpoints: {
        verify: 'POST /verify',
        health: 'GET /health',
      },
    });
  });

  // 404 handler
  app.use((_req: Request, res: Response) => {
    res.status(404).json({
      error: 'NOT_FOUND',
      message: 'Endpoint not found',
    });
  });

  // Error handler
  app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
    console.error('Unhandled error:', err);
    res.status(500).json({
      error: 'INTERNAL_ERROR',
      message: 'An unexpected error occurred',
    });
  });

  return app;
}
