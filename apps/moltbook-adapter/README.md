# Moltbook Adapter

TypeScript service for verifying Moltbook identity tokens.

## Overview

The Moltbook Adapter provides a single endpoint (`POST /verify`) that verifies identity tokens issued by Moltbook. It includes:

- **Short-TTL caching** to reduce load on Moltbook
- **Circuit breaker** to prevent request storms during outages
- **Structured error codes** for clear error handling
- **No redirect following** to prevent auth header leakage

## Configuration

Environment variables:

- `PORT` (default: 3001) - Server port
- `MOLTBOOK_BASE_URL` (required) - Canonical Moltbook base URL (e.g., https://moltbook.com)
- `MOLTBOOK_APP_KEY` (required) - App key for authenticating with Moltbook
- `VERIFICATION_CACHE_TTL` (default: 300) - Cache TTL in seconds
- `CIRCUIT_BREAKER_THRESHOLD` (default: 5) - Failures before opening circuit
- `CIRCUIT_BREAKER_TIMEOUT` (default: 60) - Seconds to wait before retry

## Usage

### Install dependencies

```bash
npm install
```

### Development

```bash
npm run dev
```

### Production

```bash
npm run build
npm start
```

### Testing

```bash
npm test
```

## API

### POST /verify

Verify a Moltbook identity token.

**Request:**
```json
{
  "identity_token": "string"
}
```

**Success Response (200):**
```json
{
  "moltbook_id": "mb_user_12345",
  "name": "Dr. Jane Smith",
  "reputation": 850,
  "profile_meta": {
    "institution": "MIT",
    "field": "Computer Science"
  }
}
```

**Error Responses:**

- `400 BAD_REQUEST` - Missing or invalid identity_token
- `401 INVALID_TOKEN` - Token is invalid or expired
- `502 INVALID_RESPONSE` - Moltbook returned unexpected response
- `502 REDIRECT_NOT_ALLOWED` - Moltbook returned a redirect
- `503 UPSTREAM_UNAVAILABLE` - Moltbook is unavailable (includes Retry-After header)
- `503 CIRCUIT_OPEN` - Circuit breaker is open (includes Retry-After header)

### GET /health

Health check endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "service": "moltbook-adapter",
  "circuit_state": "CLOSED",
  "cache_stats": {
    "keys": 42,
    "hits": 156,
    "misses": 23
  }
}
```

## Architecture

- **config.ts** - Environment-based configuration
- **circuit-breaker.ts** - Circuit breaker implementation (CLOSED/OPEN/HALF_OPEN)
- **verifier.ts** - Core verification logic with caching
- **server.ts** - Express HTTP server
- **index.ts** - Entry point

## Security

- Does not follow redirects (prevents auth header leakage)
- Validates response structure before caching
- No fake/dev mode - all verification is real
- Short-lived cache to limit exposure window
