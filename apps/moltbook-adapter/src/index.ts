/**
 * Moltbook Adapter Entry Point
 */

import dotenv from 'dotenv';
import { loadConfig } from './config';
import { createApp } from './server';

// Load environment variables
dotenv.config();

async function main() {
  try {
    // Load configuration
    const config = loadConfig();
    console.log('Configuration loaded:');
    console.log(`  Port: ${config.port}`);
    console.log(`  Moltbook Base URL: ${config.moltbookBaseUrl}`);
    console.log(`  Cache TTL: ${config.verificationCacheTtl}s`);
    console.log(`  Circuit Breaker Threshold: ${config.circuitBreakerThreshold}`);

    // Create and start server
    const app = createApp(config);

    app.listen(config.port, () => {
      console.log(`\n✓ Moltbook Adapter listening on port ${config.port}`);
      console.log(`  Health check: http://localhost:${config.port}/health`);
      console.log(`  Verify endpoint: http://localhost:${config.port}/verify\n`);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

main();
