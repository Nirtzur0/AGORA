import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { chromium, firefox, webkit } from 'playwright';

const TOKEN_KEY = 'agent_session_jwt';
const BROWSER_TYPES = { chromium, firefox, webkit };
const VIEWPORT_TYPES = {
  desktop: { width: 1440, height: 960 },
  mobile: { width: 390, height: 844 },
};
const WORKSPACE_TABS = ['Overview', 'Team', 'Requests', 'Artifacts', 'Claims', 'Drafts', 'Tasks', 'Critiques', 'Rule checks', 'Timeline', 'Search'];
const PDF_BASE64 =
  'JVBERi0xLjMKJZOMi54gUmVwb3J0TGFiIEdlbmVyYXRlZCBQREYgZG9jdW1lbnQgaHR0cDovL3d3dy5yZXBvcnRsYWIuY29tCjEgMCBvYmoKPDwKL0YxIDIgMCBSCj4+CmVuZG9iagoyIDAgb2JqCjw8Ci9CYXNlRm9udCAvSGVsdmV0aWNhIC9FbmNvZGluZyAvV2luQW5zaUVuY29kaW5nIC9OYW1lIC9GMSAvU3VidHlwZSAvVHlwZTEgL1R5cGUgL0ZvbnQKPj4KZW5kb2JqCjMgMCBvYmoKPDwKL0NvbnRlbnRzIDcgMCBSIC9NZWRpYUJveCBbIDAgMCA2MTIgNzkyIF0gL1BhcmVudCA2IDAgUiAvUmVzb3VyY2VzIDw8Ci9Gb250IDEgMCBSIC9Qcm9jU2V0IFsgL1BERiAvVGV4dCAvSW1hZ2VCIC9JbWFnZUMgL0ltYWdlSSBdCj4+IC9Sb3RhdGUgMCAvVHJhbnMgPDwKCj4+IAogIC9UeXBlIC9QYWdlCj4+CmVuZG9iago0IDAgb2JqCjw8Ci9QYWdlTW9kZSAvVXNlTm9uZSAvUGFnZXMgNiAwIFIgL1R5cGUgL0NhdGFsb2cKPj4KZW5kb2JqCjUgMCBvYmoKPDwKL0F1dGhvciAoYW5vbnltb3VzKSAvQ3JlYXRpb25EYXRlIChEOjIwMjYwMzEwMjEyMDQyLTAyJzAwJykgL0NyZWF0b3IgKFJlcG9ydExhYiBQREYgTGlicmFyeSAtIHd3dy5yZXBvcnRsYWIuY29tKSAvS2V5d29yZHMgKCkgL01vZERhdGUgKEQ6MjAyNjAzMTAyMTIwNDItMDInMDAnKSAvUHJvZHVjZXIgKFJlcG9ydExhYiBQREYgTGlicmFyeSAtIHd3dy5yZXBvcnRsYWIuY29tKSAKICAvU3ViamVjdCAodW5zcGVjaWZpZWQpIC9UaXRsZSAodW50aXRsZWQpIC9UcmFwcGVkIC9GYWxzZQo+PgplbmRvYmoKNiAwIG9iago8PAovQ291bnQgMSAvS2lkcyBbIDMgMCBSIF0gL1R5cGUgL1BhZ2VzCj4+CmVuZG9iago3IDAgb2JqCjw8Ci9GaWx0ZXIgWyAvQVNDSUk4NURlY29kZSAvRmxhdGVEZWNvZGUgXSAvTGVuZ3RoIDE2Mgo+PgpzdHJlYW0KR2FyVzBZbXVATiY0Q2xaQFMzb1A+PSllO09HXFghSiYlUV5ZNDM5Sj5WdUFsKFVeSiQxUls2NkFkQyNJaFdZLF1BRipNJTxUIW1XbXFRZnMnLFIoY1tzRyFZKkI3SFVocDpVRWw/SCVlUmhrU0FNalRoREhpbjxlbStjNyo4PE9oPkZAa2MmUipOI2Akcl9pNS1sR2VSbzc+bSknLEUrYH4+ZW5kc3RyZWFtCmVuZG9iagp4cmVmCjAgOAowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwNzMgMDAwMDAgbiAKMDAwMDAwMDEwNCAwMDAwMCBuIAowMDAwMDAwMjExIDAwMDAwIG4gCjAwMDAwMDA0MDQgMDAwMDAgbiAKMDAwMDAwMDQ3MiAwMDAwMCBuIAowMDAwMDAwNzY4IDAwMDAwIG4gCjAwMDAwMDA4MjcgMDAwMDAgbiAKdHJhaWxlcgo8PAovSUQgCls8MTFiM2Y5YzJlMGY5YjY3MDRhYWE5NjVhN2E2NmZkYTU+PDExYjNmOWMyZTBmOWI2NzA0YWFhOTY1YTdhNjZmZGE1Pl0KJSBSZXBvcnRMYWIgZ2VuZXJhdGVkIFBERiBkb2N1bWVudCAtLSBkaWdlc3QgKGh0dHA6Ly93d3cucmVwb3J0bGFiLmNvbSkKCi9JbmZvIDUgMCBSCi9Sb290IDQgMCBSCi9TaXplIDgKPj4Kc3RhcnR4cmVmCjEwNzkKJSVFT0YK';

function base64Url(value) {
  return Buffer.from(value).toString('base64url');
}

function withAuth(token, extra = {}) {
  return { ...extra, Authorization: `Bearer ${token}` };
}

function makeIdempotencyKey(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function createSystemToken() {
  const secret = process.env.SYSTEM_JWT_SECRET || 'system-secret-change-in-production';
  const now = Math.floor(Date.now() / 1000);
  const header = base64Url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = base64Url(
    JSON.stringify({
      sub: 'playwright-smoke',
      type: 'system',
      aud: 'agora:system-api',
      iss: 'agora-core-api',
      iat: now,
      exp: now + 3600,
    })
  );
  const body = `${header}.${payload}`;
  const signature = crypto.createHmac('sha256', secret).update(body).digest('base64url');
  return `${body}.${signature}`;
}

async function parseJsonResponse(response, context) {
  const bodyText = await response.text();
  if (!response.ok()) {
    throw new Error(`${context} failed (${response.status()}): ${bodyText}`);
  }
  try {
    return JSON.parse(bodyText);
  } catch {
    throw new Error(`${context} returned non-JSON body: ${bodyText}`);
  }
}

async function authDebugAgent(request, coreApi, identity) {
  const response = await request.post(`${coreApi}/auth/moltbook`, {
    headers: { 'X-Moltbook-Identity': identity },
  });
  return parseJsonResponse(response, `auth ${identity}`);
}

async function getStoredToken(page) {
  return page.evaluate((key) => localStorage.getItem(key) || sessionStorage.getItem(key), TOKEN_KEY);
}

async function waitForProjects(page) {
  await page.waitForFunction(
    (key) => {
      const hasToken = localStorage.getItem(key) || sessionStorage.getItem(key);
      return hasToken && window.location.pathname.startsWith('/projects');
    },
    TOKEN_KEY,
    { timeout: 20000 }
  );
}

async function createWorkspaceViaUI(page, workspaceName, description) {
  await page.getByRole('button', { name: 'New workspace' }).click();
  const dialog = page.locator('.dialog-card');
  await dialog.waitFor({ state: 'visible', timeout: 10000 });
  await dialog.getByRole('textbox', { name: 'Name', exact: true }).fill(workspaceName);
  await dialog.getByRole('textbox', { name: 'Description', exact: true }).fill(description);
  await dialog.getByRole('button', { name: 'Create workspace', exact: true }).click();
  await page.locator(`.project-card:has-text("${workspaceName}")`).waitFor({ state: 'visible', timeout: 20000 });
}

async function findWorkspaceIdByName(request, coreApi, token, workspaceName) {
  const response = await request.get(`${coreApi}/workspaces`, {
    headers: withAuth(token),
  });
  const workspaces = await parseJsonResponse(response, 'list workspaces');
  const match = workspaces.find((workspace) => workspace.name === workspaceName);
  if (!match) {
    throw new Error(`Workspace '${workspaceName}' not found after UI creation`);
  }
  return match.id;
}

async function createArtifact(request, coreApi, token, workspaceId, type, metadata) {
  const response = await request.post(`${coreApi}/workspaces/${workspaceId}/artifacts`, {
    headers: withAuth(token, { 'Idempotency-Key': makeIdempotencyKey(`artifact-${type}`) }),
    data: { type, metadata },
  });
  return parseJsonResponse(response, `create ${type} artifact`);
}

async function createArtifactVersion(request, coreApi, token, artifactId, name, mimeType, buffer) {
  const response = await request.post(`${coreApi}/artifacts/${artifactId}/versions`, {
    headers: withAuth(token, { 'Idempotency-Key': makeIdempotencyKey(`artifact-version-${artifactId}`) }),
    multipart: {
      file: { name, mimeType, buffer },
    },
  });
  return parseJsonResponse(response, `create version for ${artifactId}`);
}

async function createJoinRequest(request, coreApi, token, workspaceId, roleId) {
  const response = await request.post(`${coreApi}/workspaces/${workspaceId}/join-requests`, {
    headers: withAuth(token, { 'Idempotency-Key': makeIdempotencyKey('join-request') }),
    data: { role_id: roleId },
  });
  return parseJsonResponse(response, 'create join request');
}

async function createAssignedTask(request, coreApi, workspaceId, assigneeAgentId, artifactVersionId) {
  const token = createSystemToken();
  const response = await request.post(`${coreApi}/workspaces/${workspaceId}/tasks`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    data: {
      type: 'review_seed_artifact',
      assignee_agent_id: assigneeAgentId,
      payload: {
        objective: 'Review the seed evidence artifact and mark the task complete.',
        inputs: [{ artifact_version_id: artifactVersionId, location: 'log:char=0-27', label: 'Seed log evidence' }],
        required_outputs: ['artifact.read'],
        acceptance_criteria: ['Inspect the artifact viewer', 'Update task status through the UI'],
        priority: 'medium',
      },
    },
  });
  return parseJsonResponse(response, 'create assigned task');
}

async function fetchRoleId(request, coreApi, token, roleName) {
  const response = await request.get(`${coreApi}/workspaces/roles`, { headers: withAuth(token) });
  const roles = await parseJsonResponse(response, 'list roles');
  const match = roles.find((role) => role.name === roleName);
  if (!match) throw new Error(`Role ${roleName} not found`);
  return match.id;
}

async function fetchLatestClaimId(request, coreApi, token, workspaceId, claimText) {
  const response = await request.get(`${coreApi}/workspaces/${workspaceId}/claims`, { headers: withAuth(token) });
  const payload = await parseJsonResponse(response, 'list claims');
  const match = payload.claims.find((claim) => claim.text === claimText);
  if (!match) throw new Error(`Claim '${claimText}' not found`);
  return match.id;
}

async function assertWorkspaceTabsReachable(page, workspaceId) {
  for (const tab of WORKSPACE_TABS) {
    const tabControl = page.getByRole('tab', { name: new RegExp(`^${escapeRegExp(tab)}(?:\\s+\\d+)?$`, 'i') }).first();
    await tabControl.scrollIntoViewIfNeeded();
    await tabControl.click();
    await page.waitForURL(`**/projects/${workspaceId}/**`, { timeout: 10000 });
    await tabControl.waitFor({ state: 'visible', timeout: 10000 });
  }
}

async function openWorkspaceTab(page, label) {
  const tabControl = page.getByRole('tab', { name: new RegExp(`^${escapeRegExp(label)}(?:\\s+\\d+)?$`, 'i') }).first();
  await tabControl.scrollIntoViewIfNeeded();
  await tabControl.click();
  await tabControl.waitFor({ state: 'visible', timeout: 10000 });
}

async function selectOptionByText(selectLocator, text) {
  const options = await selectLocator.locator('option').allTextContents();
  const match = options.find((option) => option.includes(text));
  if (!match) throw new Error(`Option containing '${text}' not found. Saw: ${options.join(' | ')}`);
  await selectLocator.selectOption({ label: match });
}

async function main() {
  const requestedBrowser = (process.env.AGORA_SMOKE_BROWSER || 'chromium').toLowerCase();
  const browserType = BROWSER_TYPES[requestedBrowser];
  if (!browserType) throw new Error(`Unsupported AGORA_SMOKE_BROWSER='${requestedBrowser}'`);

  const requestedViewport = (process.env.AGORA_SMOKE_VIEWPORT || 'desktop').toLowerCase();
  const viewport = VIEWPORT_TYPES[requestedViewport];
  if (!viewport) throw new Error(`Unsupported AGORA_SMOKE_VIEWPORT='${requestedViewport}'`);

  const screenshotSuffix = requestedViewport === 'desktop' ? requestedBrowser : `${requestedBrowser}-${requestedViewport}`;
  const screenshotPath = `/tmp/agora-smoke-console-${screenshotSuffix}.png`;
  const browser = await browserType.launch({ headless: true });
  const page = await browser.newPage({ viewport });

  const base = process.env.AGORA_WEB_BASE_URL || 'http://127.0.0.1:3000';
  const coreApi = process.env.AGORA_CORE_API_URL || 'http://127.0.0.1:18000';
  const seedWorkspaceName = `Console Smoke ${Date.now()}`;
  const seedDescription = 'Deterministic workspace created by the Playwright smoke console script.';
  const claimText = `The seeded log captured deterministic browser evidence at ${Date.now()}.`;
  const draftTitle = `Console Smoke Draft ${Date.now()}`;
  const uniqueSearchText = `smoke-search-token-${Date.now()}`;
  const logText = `Smoke log start\n${uniqueSearchText}\nSmoke log finish`;
  const codeText = 'print("sandbox smoke output")\n';

  const tempUploadPath = path.join(os.tmpdir(), `agora-console-config-${Date.now()}.json`);
  fs.writeFileSync(tempUploadPath, JSON.stringify({ smoke: true, created_at: new Date().toISOString() }, null, 2));

  try {
    await page.goto(`${base}/login`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: /Dev Login/i }).click();
    await waitForProjects(page);

    const token = await getStoredToken(page);
    if (!token) throw new Error('Missing agent token after dev login');

    const agentProfile = await parseJsonResponse(
      await page.request.get(`${coreApi}/agents/me`, { headers: withAuth(token) }),
      'get current agent'
    );

    await createWorkspaceViaUI(page, seedWorkspaceName, seedDescription);
    const workspaceId = await findWorkspaceIdByName(page.request, coreApi, token, seedWorkspaceName);

    const logArtifact = await createArtifact(page.request, coreApi, token, workspaceId, 'log', { title: 'Seed evidence log' });
    const logVersion = await createArtifactVersion(
      page.request,
      coreApi,
      token,
      logArtifact.id,
      'smoke.log',
      'text/plain',
      Buffer.from(logText, 'utf-8')
    );
    const codeArtifact = await createArtifact(page.request, coreApi, token, workspaceId, 'code', { title: 'Seed sandbox script', language: 'python' });
    await createArtifactVersion(
      page.request,
      coreApi,
      token,
      codeArtifact.id,
      'smoke.py',
      'text/x-python',
      Buffer.from(codeText, 'utf-8')
    );
    const pdfArtifact = await createArtifact(page.request, coreApi, token, workspaceId, 'pdf', { title: 'Seed PDF' });
    await createArtifactVersion(
      page.request,
      coreApi,
      token,
      pdfArtifact.id,
      'smoke.pdf',
      'application/pdf',
      Buffer.from(PDF_BASE64, 'base64')
    );

    const secondaryAuth = await authDebugAgent(page.request, coreApi, 'debug-token-smoke-reviewer');
    const reviewerRoleId = await fetchRoleId(page.request, coreApi, token, 'Method Reviewer');
    await createJoinRequest(page.request, coreApi, secondaryAuth.agent_session_jwt, workspaceId, reviewerRoleId);
    await createAssignedTask(page.request, coreApi, workspaceId, agentProfile.agent_id, logVersion.id);

    await page.goto(`${base}/projects/${workspaceId}/overview`, { waitUntil: 'domcontentloaded' });
    await page.getByText(seedWorkspaceName).waitFor({ state: 'visible', timeout: 20000 });
    await assertWorkspaceTabsReachable(page, workspaceId);

    await openWorkspaceTab(page, 'Team');
    await page.getByRole('button', { name: 'Approve' }).click();
    await page.getByText('Join request approved').waitFor({ state: 'visible', timeout: 20000 });

    await openWorkspaceTab(page, 'Artifacts');
    const createArtifactSection = page.locator('.section-card').filter({ hasText: 'Create artifact record' });
    await createArtifactSection.getByRole('combobox').selectOption('config');
    await createArtifactSection.getByPlaceholder('Title').fill('UI-created config');
    await createArtifactSection.getByPlaceholder('Metadata notes').fill('Created from smoke UI');
    await createArtifactSection.getByRole('button', { name: 'Create artifact' }).click();
    await page.getByText('Artifact created').waitFor({ state: 'visible', timeout: 20000 });

    const uploadSection = page.locator('.section-card').filter({ hasText: 'Upload new version' });
    await selectOptionByText(uploadSection.getByRole('combobox'), 'UI-created config');
    await uploadSection.locator('input[type="file"]').setInputFiles(tempUploadPath);
    await uploadSection.getByRole('button', { name: 'Upload version' }).click();
    await page.getByText('Artifact version uploaded').waitFor({ state: 'visible', timeout: 20000 });

    await page.locator('.artifact-summary-card', { hasText: 'Seed evidence log' }).click();
    await page.locator('.artifact-viewer').waitFor({ state: 'visible', timeout: 20000 });

    await openWorkspaceTab(page, 'Claims');
    const claimsCreateSection = page.locator('.section-card').filter({ hasText: 'Create claim' });
    await claimsCreateSection.getByPlaceholder('State the claim in one grounded sentence').fill(claimText);
    await claimsCreateSection.getByRole('button', { name: 'Create claim' }).click();
    await page.getByText('Claim created').waitFor({ state: 'visible', timeout: 20000 });

    const evidenceSection = page.locator('.section-card').filter({ hasText: 'Attach evidence pointer' });
    await evidenceSection.getByRole('combobox').nth(0).selectOption({ index: 1 });
    await selectOptionByText(evidenceSection.getByRole('combobox').nth(1), logArtifact.short_id || 'Log');
    await evidenceSection.getByPlaceholder('Location pointer, e.g. pdf:p=1#char=0-10').fill('log:char=0-27');
    await evidenceSection.getByRole('button', { name: 'Add evidence' }).click();
    await page.getByText('Evidence added to claim').waitFor({ state: 'visible', timeout: 20000 });
    await page.getByRole('button', { name: /log:char=0-27/i }).first().click();
    await page.locator('.evidence-drawer').waitFor({ state: 'visible', timeout: 10000 });
    await page.getByRole('button', { name: 'Open Artifact Version' }).click();
    await page.locator('.provenance-card .artifact-viewer').waitFor({ state: 'visible', timeout: 10000 });
    await page.getByRole('button', { name: 'Close' }).click();

    const claimId = await fetchLatestClaimId(page.request, coreApi, token, workspaceId, claimText);

    await openWorkspaceTab(page, 'Drafts');
    const createDraftSection = page.locator('.section-card').filter({ hasText: 'Create draft' });
    await createDraftSection.getByPlaceholder('Draft title').fill(draftTitle);
    await createDraftSection
      .getByPlaceholder('Initial markdown (optional)')
      .fill(`# ${draftTitle}\n\nClaim ref [[claim:${claimId}]] and cite [[cite:${logVersion.id}|log:char=0-27]].`);
    await createDraftSection.getByRole('button', { name: 'Create draft' }).click();
    await page.getByText('Draft created').waitFor({ state: 'visible', timeout: 20000 });
    await page.getByRole('button', { name: /Citation · log:char=0-27/i }).click();
    await page.locator('.evidence-drawer').waitFor({ state: 'visible', timeout: 10000 });
    await page.getByRole('button', { name: 'Open Artifact Version' }).click();
    await page.locator('.provenance-card .artifact-viewer').waitFor({ state: 'visible', timeout: 10000 });
    await page.getByRole('button', { name: 'Close' }).click();

    await openWorkspaceTab(page, 'Requests');
    const pdfRequestSection = page.locator('.section-card').filter({ hasText: 'Request PDF ingestion' });
    await selectOptionByText(pdfRequestSection.getByRole('combobox'), pdfArtifact.short_id || 'Pdf');
    await pdfRequestSection.getByRole('button', { name: 'Request PDF ingest' }).click();
    await page.getByText(/PDF ingestion requested|Literature grounding workflow started/i).waitFor({ state: 'visible', timeout: 30000 });

    const repoSection = page.locator('.section-card').filter({ hasText: 'Request repository ingest' });
    await repoSection.getByPlaceholder('Repository URL').fill('https://github.com/octocat/Hello-World.git');
    await repoSection.getByRole('button', { name: 'Request repo ingest' }).click();
    await page.getByText(/Repository ingest requested|Repository ingested/i).waitFor({ state: 'visible', timeout: 60000 });

    const sandboxSection = page.locator('.section-card').filter({ hasText: 'Run sandbox' });
    await selectOptionByText(sandboxSection.getByRole('combobox').nth(0), codeArtifact.short_id || 'Code');
    await sandboxSection.getByRole('button', { name: 'Run sandbox' }).click();
    await page.getByText(/Sandbox run requested|Sandbox execution completed/i).waitFor({ state: 'visible', timeout: 60000 });

    const ruleCheckSection = page.locator('.section-card').filter({ hasText: 'Run rule check' });
    await ruleCheckSection.getByRole('combobox').selectOption({ index: 1 });
    await ruleCheckSection.getByRole('button', { name: 'Run rule check' }).click();
    await page.getByText('Rule check requested').waitFor({ state: 'visible', timeout: 30000 });

    await openWorkspaceTab(page, 'Tasks');
    const taskCard = page.locator('.list-card').filter({ hasText: 'review_seed_artifact' }).first();
    await taskCard.getByRole('combobox').nth(0).selectOption('completed');
    await taskCard.getByPlaceholder('Notes or blockers').fill('Verified in the browser console.');
    await taskCard.getByRole('button', { name: 'Update task' }).click();
    await page.getByText('Task updated').waitFor({ state: 'visible', timeout: 20000 });

    await page.evaluate(
      ([key, nextToken]) => {
        localStorage.setItem(key, nextToken);
        sessionStorage.setItem(key, nextToken);
      },
      [TOKEN_KEY, secondaryAuth.agent_session_jwt]
    );
    await page.goto(`${base}/projects/${workspaceId}/critiques`, { waitUntil: 'domcontentloaded' });
    await page.getByText(seedWorkspaceName).waitFor({ state: 'visible', timeout: 20000 });

    const critiqueSection = page.locator('.section-card').filter({ hasText: 'Create critique' });
    await critiqueSection.getByRole('combobox').nth(0).selectOption('claim');
    await critiqueSection.getByRole('combobox').nth(1).selectOption({ index: 1 });
    await critiqueSection.getByRole('combobox').nth(2).selectOption('major');
    await critiqueSection.getByPlaceholder('Describe the issue, request, or review finding').fill('Seeded critique from Playwright smoke.');
    await critiqueSection.getByRole('button', { name: 'Create critique' }).click();
    await page.getByText('Critique created').waitFor({ state: 'visible', timeout: 20000 });

    const critiqueCard = page.locator('.list-card').filter({ hasText: 'Seeded critique from Playwright smoke.' }).first();
    await critiqueCard.getByRole('combobox').nth(0).selectOption('resolved');
    await critiqueCard.getByRole('combobox').nth(1).selectOption('accepted_fix');
    await critiqueCard.getByPlaceholder('Resolution rationale').fill('Resolved during smoke validation.');
    await critiqueCard.getByRole('button', { name: 'Update critique' }).click();
    await page.getByText('Critique updated').waitFor({ state: 'visible', timeout: 20000 });

    await openWorkspaceTab(page, 'Rule checks');
    await page.locator('.list-card').first().waitFor({ state: 'visible', timeout: 20000 });

    await openWorkspaceTab(page, 'Timeline');
    await page.locator('.timeline-card').first().waitFor({ state: 'visible', timeout: 20000 });

    await openWorkspaceTab(page, 'Search');
    const searchSection = page.locator('.section-card').filter({ hasText: 'Search artifact content' });
    await searchSection.getByPlaceholder('Search PDF text, repo content, logs, and more').fill(uniqueSearchText);
    await searchSection.getByRole('button', { name: 'Search workspace' }).click();
    const searchResultCard = page.locator('.list-card').filter({ hasText: 'Rank' }).first();
    await searchResultCard.waitFor({ state: 'visible', timeout: 20000 });
    await searchResultCard.getByRole('button', { name: 'Open artifact version' }).click();
    await page.locator('.provenance-card .artifact-viewer').waitFor({ state: 'visible', timeout: 20000 });

    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`OK: console smoke validated on ${requestedBrowser}/${requestedViewport}. Screenshot: ${screenshotPath}`);
  } catch (error) {
    try {
      await page.screenshot({ path: screenshotPath, fullPage: true });
      console.error(`SMOKE DEBUG: failure screenshot captured at ${screenshotPath}`);
    } catch (screenshotError) {
      console.error(`SMOKE DEBUG: screenshot capture failed: ${screenshotError}`);
    }
    throw error;
  } finally {
    fs.rmSync(tempUploadPath, { force: true });
    await browser.close();
  }
}

main().catch((error) => {
  console.error('SMOKE FAILED:', error?.stack || String(error));
  process.exitCode = 1;
});
