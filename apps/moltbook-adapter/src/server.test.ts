/**
 * Integration tests for Moltbook Adapter service.
 * 
 * Tests the complete /verify endpoint behavior including:
 * - Successful verification
 * - Cache hit behavior
 * - Circuit breaker opening/closing
 * - Error handling
 * - Invalid tokens
 */

import request from 'supertest';
import express from 'express';
import { createApp } from './server';
import { Config } from './config';
import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';

// Mock axios for controlled testing
const mockAxios = new MockAdapter(axios);

// Test configuration
const testConfig: Config = {
  port: 3001,
  moltbookBaseUrl: 'https://moltbook.example.com',
  moltbookAppKey: 'test-app-key-12345',
  verificationCacheTtl: 5, // 5 seconds for faster testing
  circuitBreakerThreshold: 3,
  circuitBreakerTimeout: 2, // 2 seconds
  enableDebugMode: true,
};

describe('Moltbook Adapter', () => {
  let app: express.Application;

  beforeEach(() => {
    // Reset axios mock before each test
    mockAxios.reset();
    
    // Create fresh app for each test
    app = createApp(testConfig);
  });

  afterEach(() => {
    mockAxios.reset();
  });

  describe('GET /', () => {
    it('should return service info', async () => {
      const response = await request(app).get('/');

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({
        service: 'AGORA Moltbook Adapter',
        version: '1.0.0',
      });
      expect(response.body.endpoints).toHaveProperty('verify');
    });
  });

  describe('GET /health', () => {
    it('should return health status', async () => {
      const response = await request(app).get('/health');

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({
        status: 'healthy',
        service: 'moltbook-adapter',
      });
      expect(response.body).toHaveProperty('circuit_state');
      expect(response.body).toHaveProperty('cache_stats');
    });
  });

  describe('POST /verify', () => {
    const validToken = 'valid-moltbook-token-abc123';
    const validMoltbookResponse = {
      moltbook_id: 'mb_user_12345',
      name: 'Dr. Jane Smith',
      reputation: 850,
      profile_meta: {
        institution: 'MIT',
        field: 'Computer Science',
      },
    };

    it('should successfully verify a valid token', async () => {
      // Mock Moltbook API success
      mockAxios
        .onPost('https://moltbook.example.com/api/verify')
        .reply(200, validMoltbookResponse);

      const response = await request(app)
        .post('/verify')
        .send({ identity_token: validToken });

      expect(response.status).toBe(200);
      expect(response.body).toEqual(validMoltbookResponse);

      // Verify correct headers were sent
      const requestConfig = mockAxios.history.post[0];
      expect(requestConfig.headers?.['X-Moltbook-App-Key']).toBe('test-app-key-12345');
      expect(requestConfig.headers?.['Content-Type']).toContain('application/json');
    });

    it('should return cached result on second request', async () => {
      // Mock Moltbook API (should only be called once)
      mockAxios
        .onPost('https://moltbook.example.com/api/verify')
        .replyOnce(200, validMoltbookResponse);

      // First request - hits upstream
      const response1 = await request(app)
        .post('/verify')
        .send({ identity_token: validToken });

      expect(response1.status).toBe(200);
      expect(mockAxios.history.post.length).toBe(1);

      // Second request - should hit cache
      const response2 = await request(app)
        .post('/verify')
        .send({ identity_token: validToken });

      expect(response2.status).toBe(200);
      expect(response2.body).toEqual(validMoltbookResponse);
      // No additional upstream call
      expect(mockAxios.history.post.length).toBe(1);
    });

    it('should assign distinct debug identities for different debug tokens', async () => {
      const first = await request(app)
        .post('/verify')
        .send({ identity_token: 'debug-token-clawdbot' });

      const second = await request(app)
        .post('/verify')
        .send({ identity_token: 'debug-token-smoke-reviewer' });

      expect(first.status).toBe(200);
      expect(second.status).toBe(200);
      expect(first.body.moltbook_id).toBe('mb_debug_clawdbot');
      expect(second.body.moltbook_id).toBe('mb_debug_smoke-reviewer');
      expect(first.body.moltbook_id).not.toBe(second.body.moltbook_id);
      expect(second.body.name).toBe('Debug Smoke Reviewer');
      expect(mockAxios.history.post.length).toBe(0);
    });

    it('should return 400 for missing identity_token', async () => {
      const response = await request(app)
        .post('/verify')
        .send({});

      expect(response.status).toBe(400);
      expect(response.body.error).toBe('BAD_REQUEST');
    });

    it('should return 400 for non-string identity_token', async () => {
      const response = await request(app)
        .post('/verify')
        .send({ identity_token: 12345 });

      expect(response.status).toBe(400);
      expect(response.body.error).toBe('BAD_REQUEST');
    });

    it('should return 401 for invalid token', async () => {
      mockAxios
        .onPost('https://moltbook.example.com/api/verify')
        .reply(401, { error: 'Invalid token' });

      const response = await request(app)
        .post('/verify')
        .send({ identity_token: 'invalid-token' });

      expect(response.status).toBe(401);
      expect(response.body.error).toBe('INVALID_TOKEN');
    });

    it('should return 401 for expired token', async () => {
      mockAxios
        .onPost('https://moltbook.example.com/api/verify')
        .reply(403, { error: 'Token expired' });

      const response = await request(app)
        .post('/verify')
        .send({ identity_token: 'expired-token' });

      expect(response.status).toBe(401);
      expect(response.body.error).toBe('INVALID_TOKEN');
    });

    it('should return 503 when Moltbook is unavailable', async () => {
      mockAxios
        .onPost('https://moltbook.example.com/api/verify')
        .reply(500, { error: 'Internal server error' });

      const response = await request(app)
        .post('/verify')
        .send({ identity_token: validToken });

      expect(response.status).toBe(503);
      expect(response.body.error).toBe('UPSTREAM_UNAVAILABLE');
      expect(response.headers).toHaveProperty('retry-after');
    });

    it('should return 503 when Moltbook times out', async () => {
      mockAxios
        .onPost('https://moltbook.example.com/api/verify')
        .timeout();

      const response = await request(app)
        .post('/verify')
        .send({ identity_token: validToken });

      expect(response.status).toBe(503);
      expect(response.body.error).toBe('UPSTREAM_UNAVAILABLE');
    });

    it('should return 502 when Moltbook returns invalid response', async () => {
      mockAxios
        .onPost('https://moltbook.example.com/api/verify')
        .reply(200, { invalid: 'response' }); // Missing required fields

      const response = await request(app)
        .post('/verify')
        .send({ identity_token: validToken });

      expect(response.status).toBe(502);
      expect(response.body.error).toBe('INVALID_RESPONSE');
    });

    it('should open circuit breaker after threshold failures', async () => {
      // Mock repeated failures
      mockAxios
        .onPost('https://moltbook.example.com/api/verify')
        .reply(500);

      // First 3 failures should hit upstream
      for (let i = 0; i < 3; i++) {
        const response = await request(app)
          .post('/verify')
          .send({ identity_token: `token-${i}` });

        expect(response.status).toBe(503);
        expect(response.body.error).toBe('UPSTREAM_UNAVAILABLE');
      }

      // Circuit should now be open
      const response = await request(app)
        .post('/verify')
        .send({ identity_token: 'token-after-open' });

      expect(response.status).toBe(503);
      expect(response.body.error).toBe('CIRCUIT_OPEN');
    });

    it('should reject redirect responses', async () => {
      mockAxios
        .onPost('https://moltbook.example.com/api/verify')
        .reply(301, null, { Location: 'https://other-domain.com/verify' });

      const response = await request(app)
        .post('/verify')
        .send({ identity_token: validToken });

      expect(response.status).toBe(502);
      expect(response.body.error).toBe('REDIRECT_NOT_ALLOWED');
    });
  });

  describe('Circuit Breaker Recovery', () => {
    it('should close circuit after successful request in half-open state', async () => {
      const validToken = 'valid-token';
      const validResponse = {
        moltbook_id: 'mb_user_123',
        name: 'Test User',
        reputation: 500,
      };

      // Trigger circuit breaker open
      mockAxios
        .onPost('https://moltbook.example.com/api/verify')
        .reply(500)
        .onPost('https://moltbook.example.com/api/verify')
        .reply(500)
        .onPost('https://moltbook.example.com/api/verify')
        .reply(500);

      for (let i = 0; i < 3; i++) {
        await request(app).post('/verify').send({ identity_token: `fail-${i}` });
      }

      // Circuit is now open - wait for timeout (2 seconds)
      await new Promise(resolve => setTimeout(resolve, 2100));

      // Mock successful response for recovery
      mockAxios.reset();
      mockAxios
        .onPost('https://moltbook.example.com/api/verify')
        .reply(200, validResponse);

      // Should allow one request through (half-open)
      const response = await request(app)
        .post('/verify')
        .send({ identity_token: validToken });

      expect(response.status).toBe(200);
      expect(response.body).toEqual(validResponse);

      // Circuit should be closed now, verify with health check
      const healthResponse = await request(app).get('/health');
      expect(healthResponse.body.circuit_state).toBe('CLOSED');
    });
  });

  describe('404 Handler', () => {
    it('should return 404 for unknown endpoints', async () => {
      const response = await request(app).get('/unknown');

      expect(response.status).toBe(404);
      expect(response.body.error).toBe('NOT_FOUND');
    });
  });
});
