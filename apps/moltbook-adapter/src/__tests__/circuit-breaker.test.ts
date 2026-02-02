/**
 * Unit tests for circuit breaker.
 */

import { CircuitBreaker, CircuitState } from '../circuit-breaker';

describe('CircuitBreaker', () => {
  let breaker: CircuitBreaker;

  beforeEach(() => {
    breaker = new CircuitBreaker(3, 1000); // threshold: 3, timeout: 1000ms
  });

  describe('Initial state', () => {
    it('should start in CLOSED state', () => {
      expect(breaker.getState()).toBe(CircuitState.CLOSED);
      expect(breaker.canAttempt()).toBe(true);
    });
  });

  describe('Failure handling', () => {
    it('should remain CLOSED below threshold', () => {
      breaker.recordFailure();
      expect(breaker.getState()).toBe(CircuitState.CLOSED);
      expect(breaker.canAttempt()).toBe(true);

      breaker.recordFailure();
      expect(breaker.getState()).toBe(CircuitState.CLOSED);
      expect(breaker.canAttempt()).toBe(true);
    });

    it('should OPEN after reaching threshold', () => {
      breaker.recordFailure();
      breaker.recordFailure();
      breaker.recordFailure(); // 3rd failure

      expect(breaker.getState()).toBe(CircuitState.OPEN);
      expect(breaker.canAttempt()).toBe(false);
    });

    it('should block requests when OPEN', () => {
      for (let i = 0; i < 3; i++) {
        breaker.recordFailure();
      }

      expect(breaker.canAttempt()).toBe(false);
      expect(breaker.canAttempt()).toBe(false);
    });
  });

  describe('Recovery', () => {
    it('should transition to HALF_OPEN after timeout', async () => {
      // Open the circuit
      for (let i = 0; i < 3; i++) {
        breaker.recordFailure();
      }
      expect(breaker.getState()).toBe(CircuitState.OPEN);

      // Wait for timeout
      await new Promise(resolve => setTimeout(resolve, 1100));

      // Should transition to HALF_OPEN and allow attempt
      expect(breaker.canAttempt()).toBe(true);
      expect(breaker.getState()).toBe(CircuitState.HALF_OPEN);
    });

    it('should close on successful request in HALF_OPEN', async () => {
      // Open the circuit
      for (let i = 0; i < 3; i++) {
        breaker.recordFailure();
      }

      // Wait for timeout
      await new Promise(resolve => setTimeout(resolve, 1100));
      expect(breaker.canAttempt()).toBe(true);

      // Record success
      breaker.recordSuccess();
      expect(breaker.getState()).toBe(CircuitState.CLOSED);
    });

    it('should reopen on failure in HALF_OPEN', async () => {
      // Open the circuit
      for (let i = 0; i < 3; i++) {
        breaker.recordFailure();
      }

      // Wait for timeout
      await new Promise(resolve => setTimeout(resolve, 1100));
      breaker.canAttempt(); // Move to HALF_OPEN

      // Record another failure
      breaker.recordFailure();
      expect(breaker.getState()).toBe(CircuitState.OPEN);
      expect(breaker.canAttempt()).toBe(false);
    });
  });

  describe('Success handling', () => {
    it('should reset failure count on success', () => {
      breaker.recordFailure();
      breaker.recordFailure();
      expect(breaker.getState()).toBe(CircuitState.CLOSED);

      breaker.recordSuccess();

      // Should not open even after 2 more failures (count reset)
      breaker.recordFailure();
      breaker.recordFailure();
      expect(breaker.getState()).toBe(CircuitState.CLOSED);
    });
  });

  describe('Reset', () => {
    it('should reset to initial state', () => {
      // Open the circuit
      for (let i = 0; i < 3; i++) {
        breaker.recordFailure();
      }
      expect(breaker.getState()).toBe(CircuitState.OPEN);

      // Reset
      breaker.reset();
      expect(breaker.getState()).toBe(CircuitState.CLOSED);
      expect(breaker.canAttempt()).toBe(true);
    });
  });
});
