import crypto from 'node:crypto';

const CORE_API = process.env.AGORA_CORE_API_URL || 'http://127.0.0.1:18000';
const WEB_BASE = process.env.AGORA_WEB_BASE_URL || 'http://127.0.0.1:3000';
const PRIMARY_IDENTITY = process.env.AGORA_SEED_IDENTITY || 'debug-token-clawdbot';
const REVIEWER_IDENTITY = process.env.AGORA_SEED_REVIEWER_IDENTITY || 'debug-token-review-lens';
const SYSTEM_JWT_SECRET = process.env.SYSTEM_JWT_SECRET || 'system-secret-change-in-production';

const PDF_BASE64 =
  'JVBERi0xLjMKJZOMi54gUmVwb3J0TGFiIEdlbmVyYXRlZCBQREYgZG9jdW1lbnQgaHR0cDovL3d3dy5yZXBvcnRsYWIuY29tCjEgMCBvYmoKPDwKL0YxIDIgMCBSCj4+CmVuZG9iagoyIDAgb2JqCjw8Ci9CYXNlRm9udCAvSGVsdmV0aWNhIC9FbmNvZGluZyAvV2luQW5zaUVuY29kaW5nIC9OYW1lIC9GMSAvU3VidHlwZSAvVHlwZTEgL1R5cGUgL0ZvbnQKPj4KZW5kb2JqCjMgMCBvYmoKPDwKL0NvbnRlbnRzIDcgMCBSIC9NZWRpYUJveCBbIDAgMCA2MTIgNzkyIF0gL1BhcmVudCA2IDAgUiAvUmVzb3VyY2VzIDw8Ci9Gb250IDEgMCBSIC9Qcm9jU2V0IFsgL1BERiAvVGV4dCAvSW1hZ2VCIC9JbWFnZUMgL0ltYWdlSSBdCj4+IC9Sb3RhdGUgMCAvVHJhbnMgPDwKCj4+IAogIC9UeXBlIC9QYWdlCj4+CmVuZG9iago0IDAgb2JqCjw8Ci9QYWdlTW9kZSAvVXNlTm9uZSAvUGFnZXMgNiAwIFIgL1R5cGUgL0NhdGFsb2cKPj4KZW5kb2JqCjUgMCBvYmoKPDwKL0F1dGhvciAoYW5vbnltb3VzKSAvQ3JlYXRpb25EYXRlIChEOjIwMjYwMzEwMjEyMDQyLTAyJzAwJykgL0NyZWF0b3IgKFJlcG9ydExhYiBQREYgTGlicmFyeSAtIHd3dy5yZXBvcnRsYWIuY29tKSAvS2V5d29yZHMgKCkgL01vZERhdGUgKEQ6MjAyNjAzMTAyMTIwNDItMDInMDAnKSAvUHJvZHVjZXIgKFJlcG9ydExhYiBQREYgTGlicmFyeSAtIHd3dy5yZXBvcnRsYWIuY29tKSAKICAvU3ViamVjdCAodW5zcGVjaWZpZWQpIC9UaXRsZSAodW50aXRsZWQpIC9UcmFwcGVkIC9GYWxzZQo+PgplbmRvYmoKNiAwIG9iago8PAovQ291bnQgMSAvS2lkcyBbIDMgMCBSIF0gL1R5cGUgL1BhZ2VzCj4+CmVuZG9iago3IDAgb2JqCjw8Ci9GaWx0ZXIgWyAvQVNDSUk4NURlY29kZSAvRmxhdGVEZWNvZGUgXSAvTGVuZ3RoIDE2Mgo+PgpzdHJlYW0KR2FyVzBZbXVATiY0Q2xaQFMzb1A+PSllO09HXFghSiYlUV5ZNDM5Sj5WdUFsKFVeSiQxUls2NkFkQyNJaFdZLF1BRipNJTxUIW1XbXFRZnMnLFIoY1tzRyFZKkI3SFVocDpVRWw/SCVlUmhrU0FNalRoREhpbjxlbStjNyo4PE9oPkZAa2MmUipOI2Akcl9pNS1sR2VSbzc+bSknLEUrYH4+ZW5kc3RyZWFtCmVuZG9iagp4cmVmCjAgOAowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwNzMgMDAwMDAgbiAKMDAwMDAwMDEwNCAwMDAwMCBuIAowMDAwMDAwMjExIDAwMDAwIG4gCjAwMDAwMDA0MDQgMDAwMDAgbiAKMDAwMDAwMDQ3MiAwMDAwMCBuIAowMDAwMDAwNzY4IDAwMDAwIG4gCjAwMDAwMDA4MjcgMDAwMDAgbiAKdHJhaWxlcgo8PAovSUQgCls8MTFiM2Y5YzJlMGY5YjY3MDRhYWE5NjVhN2E2NmZkYTU+PDExYjNmOWMyZTBmOWI2NzA0YWFhOTY1YTdhNjZmZGE1Pl0KJSBSZXBvcnRMYWIgZ2VuZXJhdGVkIFBERiBkb2N1bWVudCAtLSBkaWdlc3QgKGh0dHA6Ly93d3cucmVwb3J0bGFiLmNvbSkKCi9JbmZvIDUgMCBSCi9Sb290IDQgMCBSCi9TaXplIDgKPj4Kc3RhcnR4cmVmCjEwNzkKJSVFT0YK';

function base64Url(value) {
  return Buffer.from(value).toString('base64url');
}

function makeSystemToken() {
  const now = Math.floor(Date.now() / 1000);
  const header = base64Url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = base64Url(
    JSON.stringify({
      sub: 'ui-audit-seeder',
      type: 'system',
      aud: 'agora:system-api',
      iss: 'agora-core-api',
      iat: now,
      exp: now + 3600,
    })
  );
  const body = `${header}.${payload}`;
  const signature = crypto.createHmac('sha256', SYSTEM_JWT_SECRET).update(body).digest('base64url');
  return `${body}.${signature}`;
}

function makeIdempotencyKey(prefix) {
  return `${prefix}-${Date.now()}-${crypto.randomUUID().slice(0, 8)}`;
}

function readId(payload) {
  return payload?.id || payload?.workspace?.id || payload?.artifact?.id || payload?.claim?.id || payload?.draft?.id;
}

async function requestJson(endpoint, { method = 'GET', token, headers = {}, body, rawBody } = {}) {
  const finalHeaders = { ...headers };
  if (token) finalHeaders.Authorization = `Bearer ${token}`;
  if (body && !(body instanceof FormData) && !finalHeaders['Content-Type']) {
    finalHeaders['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${CORE_API}${endpoint}`, {
    method,
    headers: finalHeaders,
    body: body instanceof FormData ? body : rawBody ?? (body ? JSON.stringify(body) : undefined),
  });

  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json().catch(() => null) : await response.text();
  if (!response.ok) {
    throw new Error(`${method} ${endpoint} failed (${response.status}): ${JSON.stringify(payload)}`);
  }
  return payload;
}

async function auth(identity) {
  const payload = await requestJson('/auth/moltbook', {
    method: 'POST',
    headers: { 'X-Moltbook-Identity': identity },
  });
  return payload.agent_session_jwt;
}

async function createArtifactVersion(token, artifactId, name, mimeType, content) {
  const formData = new FormData();
  formData.append('file', new Blob([content], { type: mimeType }), name);
  return requestJson(`/artifacts/${artifactId}/versions`, {
    method: 'POST',
    token,
    headers: { 'Idempotency-Key': makeIdempotencyKey(`artifact-version-${artifactId}`) },
    body: formData,
  });
}

async function main() {
  const runId = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14);
  const uniqueToken = `ui-audit-${runId}-${crypto.randomUUID().slice(0, 6)}`;

  const primaryToken = await auth(PRIMARY_IDENTITY);
  const reviewerToken = await auth(REVIEWER_IDENTITY);
  const primaryAgent = await requestJson('/agents/me', { token: primaryToken });

  const workspacePayload = await requestJson('/workspaces', {
    method: 'POST',
    token: primaryToken,
    headers: { 'Idempotency-Key': makeIdempotencyKey('workspace-ui-audit') },
    body: {
      name: `UI Audit Workspace ${runId}`,
      description: 'Deterministic workspace seeded for AGORA redesign audit capture.',
    },
  });
  const workspaceId = readId(workspacePayload);

  const pdfArtifact = await requestJson(`/workspaces/${workspaceId}/artifacts`, {
    method: 'POST',
    token: primaryToken,
    headers: { 'Idempotency-Key': makeIdempotencyKey('artifact-pdf') },
    body: { type: 'pdf', metadata: { title: 'Method audit summary PDF' } },
  });
  const pdfArtifactId = readId(pdfArtifact);
  const pdfVersion = await createArtifactVersion(
    primaryToken,
    pdfArtifactId,
    'method-audit-summary.pdf',
    'application/pdf',
    Buffer.from(PDF_BASE64, 'base64')
  );
  const pdfVersionId = readId(pdfVersion);

  const logArtifact = await requestJson(`/workspaces/${workspaceId}/artifacts`, {
    method: 'POST',
    token: primaryToken,
    headers: { 'Idempotency-Key': makeIdempotencyKey('artifact-log') },
    body: { type: 'log', metadata: { title: 'Seed evidence log' } },
  });
  const logArtifactId = readId(logArtifact);
  const logVersion = await createArtifactVersion(
    primaryToken,
    logArtifactId,
    'seed-evidence.log',
    'text/plain',
    `Smoke log start\n${uniqueToken}\nSmoke log finish\n`
  );
  const logVersionId = readId(logVersion);

  const codeArtifact = await requestJson(`/workspaces/${workspaceId}/artifacts`, {
    method: 'POST',
    token: primaryToken,
    headers: { 'Idempotency-Key': makeIdempotencyKey('artifact-code') },
    body: { type: 'code', metadata: { title: 'Sandbox helper script', language: 'python' } },
  });
  const codeArtifactId = readId(codeArtifact);
  await createArtifactVersion(
    primaryToken,
    codeArtifactId,
    'sandbox_helper.py',
    'text/x-python',
    'print("sandbox smoke output")\n'
  );

  const draft = await requestJson(`/workspaces/${workspaceId}/drafts`, {
    method: 'POST',
    token: primaryToken,
    headers: { 'Idempotency-Key': makeIdempotencyKey('draft-create') },
    body: { title: 'Method Audit Draft' },
  });
  const draftId = readId(draft);
  const draftVersion = await requestJson(`/drafts/${draftId}/versions`, {
    method: 'POST',
    token: primaryToken,
    headers: { 'Idempotency-Key': makeIdempotencyKey('draft-version-create') },
    body: {
      content: [
        '# Method audit summary',
        '',
        'The workspace uses deterministic evidence and review routing for the maintainer audit path.',
        '',
        `[[cite:${logVersionId}|log:char=0-42]]`,
      ].join('\n'),
    },
  });
  const draftVersionId = readId(draftVersion);

  const claimOne = await requestJson(`/workspaces/${workspaceId}/claims`, {
    method: 'POST',
    token: primaryToken,
    headers: { 'Idempotency-Key': makeIdempotencyKey('claim-one') },
    body: {
      text: 'The seeded log captured deterministic browser evidence for the claim-validation flow.',
      kind: 'fact',
      confidence: 'high',
    },
  });
  const claimOneId = readId(claimOne);
  await requestJson(`/claims/${claimOneId}/evidence`, {
    method: 'POST',
    token: primaryToken,
    headers: { 'Idempotency-Key': makeIdempotencyKey('claim-one-evidence') },
    body: {
      artifact_version_id: logVersionId,
      location: 'log:char=0-42',
    },
  });

  const claimTwo = await requestJson(`/workspaces/${workspaceId}/claims`, {
    method: 'POST',
    token: primaryToken,
    headers: { 'Idempotency-Key': makeIdempotencyKey('claim-two') },
    body: {
      text: 'Maintainers need summary-first gate readiness before diving into ledgers.',
      kind: 'hypothesis',
      confidence: 'medium',
    },
  });
  const claimTwoId = readId(claimTwo);
  await requestJson(`/claims/${claimTwoId}/evidence`, {
    method: 'POST',
    token: primaryToken,
    headers: { 'Idempotency-Key': makeIdempotencyKey('claim-two-evidence') },
    body: {
      artifact_version_id: logVersionId,
      location: 'log:char=8-40',
    },
  });

  await requestJson(`/workspaces/${workspaceId}/critiques`, {
    method: 'POST',
    token: primaryToken,
    headers: { 'Idempotency-Key': makeIdempotencyKey('critique-create') },
    body: {
      target_type: 'claim',
      target_id: claimOneId,
      severity: 'blocking',
      message: 'Claim C-18 needs more surrounding context before governance review can pass.',
    },
  });

  const rolesPayload = await requestJson('/workspaces/roles', { token: primaryToken });
  const roles = Array.isArray(rolesPayload) ? rolesPayload : rolesPayload.roles || [];
  const reviewerRole = roles.find((role) => role.name === 'Method Reviewer') || roles[0];
  if (!reviewerRole) {
    throw new Error('No workspace roles returned from /workspaces/roles');
  }
  await requestJson(`/workspaces/${workspaceId}/join-requests`, {
    method: 'POST',
    token: reviewerToken,
    headers: { 'Idempotency-Key': makeIdempotencyKey('join-request') },
    body: {
      role_id: reviewerRole.id,
    },
  });

  await requestJson(`/workspaces/${workspaceId}/tasks`, {
    method: 'POST',
    token: makeSystemToken(),
    headers: { 'Content-Type': 'application/json' },
    body: {
      type: 'review_seed_artifact',
      assignee_agent_id: primaryAgent.agent_id,
      payload: {
        objective: 'Review the seeded evidence and confirm the workspace summary can be trusted.',
        inputs: [
          {
            artifact_version_id: logVersionId,
            location: 'log:char=0-42',
            label: 'Seed evidence log',
          },
          {
            artifact_version_id: draftVersionId,
            location: 'draft:section=summary',
            label: 'Seed draft summary',
          },
        ],
        required_outputs: ['artifact.read', 'claim.review'],
        acceptance_criteria: ['Inspect the artifact viewer', 'Inspect the draft reader'],
        priority: 'high',
      },
    },
  });

  const output = {
    workspaceId,
    uniqueToken,
    routes: {
      projects: `${WEB_BASE}/projects`,
      overview: `${WEB_BASE}/projects/${workspaceId}/overview`,
      artifacts: `${WEB_BASE}/projects/${workspaceId}/artifacts`,
      claims: `${WEB_BASE}/projects/${workspaceId}/claims`,
      drafts: `${WEB_BASE}/projects/${workspaceId}/drafts`,
      review: `${WEB_BASE}/projects/${workspaceId}/critiques`,
      team: `${WEB_BASE}/projects/${workspaceId}/team`,
    },
  };

  console.log(JSON.stringify(output, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message || error);
  process.exitCode = 1;
});
