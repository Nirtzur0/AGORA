/**
 * Configuration for Moltbook adapter service.
 * 
 * All configuration is loaded from environment variables.
 */

export interface Config {
  port: number;
  moltbookBaseUrl: string;
  moltbookAppKey: string;
  verificationCacheTtl: number; // seconds
  circuitBreakerThreshold: number; // failures before opening circuit
  circuitBreakerTimeout: number; // seconds to wait before retry
  enableDebugMode: boolean;
}

function getEnvRequired(key: string): string {
  const value = process.env[key];
  if (!value) {
    throw new Error(`Required environment variable ${key} is not set`);
  }
  return value;
}

function getEnvOptional(key: string, defaultValue: string): string {
  return process.env[key] || defaultValue;
}

export function loadConfig(): Config {
  return {
    port: parseInt(getEnvOptional('PORT', '3001'), 10),
    moltbookBaseUrl: getEnvRequired('MOLTBOOK_BASE_URL'),
    moltbookAppKey: getEnvRequired('MOLTBOOK_APP_KEY'),
    verificationCacheTtl: parseInt(getEnvOptional('VERIFICATION_CACHE_TTL', '300'), 10),
    circuitBreakerThreshold: parseInt(getEnvOptional('CIRCUIT_BREAKER_THRESHOLD', '5'), 10),
    circuitBreakerTimeout: parseInt(getEnvOptional('CIRCUIT_BREAKER_TIMEOUT', '60'), 10),
    enableDebugMode: getEnvOptional('ENABLE_DEBUG_MODE', 'false') === 'true',
  };
}
