import { chromium, firefox, webkit } from 'playwright';

const TOKEN_KEY = 'agent_session_jwt';
const BROWSER_TYPES = {
  chromium,
  firefox,
  webkit,
};
const VIEWPORT_TYPES = {
  desktop: { width: 1366, height: 900 },
  mobile: { width: 390, height: 844 },
};
const WORKSPACE_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'tasks', label: 'Tasks' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'artifacts', label: 'Artifacts' },
  { id: 'claims', label: 'Claims' },
  { id: 'drafts', label: 'Drafts' },
  { id: 'critiques', label: 'Critiques' },
  { id: 'rule-checks', label: 'Rule Checks' },
];

function withAuth(token, extra = {}) {
  return {
    ...extra,
    Authorization: `Bearer ${token}`,
  };
}

function makeIdempotencyKey(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function parseJsonResponse(response, context) {
  const bodyText = await response.text();
  if (!response.ok()) {
    throw new Error(`${context} failed (${response.status()}): ${bodyText}`);
  }
  try {
    return JSON.parse(bodyText);
  } catch (err) {
    throw new Error(`${context} returned non-JSON body: ${bodyText}`);
  }
}

async function createWorkspace(request, coreApi, token) {
  const response = await request.post(`${coreApi}/workspaces`, {
    headers: withAuth(token, {
      'Idempotency-Key': makeIdempotencyKey('workspace-create'),
    }),
    data: {
      name: `UI Smoke Workspace ${Date.now()}`,
      description: 'Deterministic workspace created by smoke_artifact_viewer.mjs',
    },
  });
  return parseJsonResponse(response, 'create workspace');
}

async function createLogArtifactVersion(request, coreApi, token, workspaceId) {
  const artifactResponse = await request.post(`${coreApi}/workspaces/${workspaceId}/artifacts`, {
    headers: withAuth(token, {
      'Idempotency-Key': makeIdempotencyKey('artifact-create'),
      'Content-Type': 'application/json',
    }),
    data: {
      type: 'log',
      metadata: {
        title: 'UI Smoke Log Artifact',
      },
    },
  });
  const artifact = await parseJsonResponse(artifactResponse, 'create artifact');

  const logText = [
    'Smoke run started',
    'Evidence pointer resolver should be deterministic',
    'Smoke run completed',
  ].join('\n');

  const versionResponse = await request.post(`${coreApi}/artifacts/${artifact.id}/versions`, {
    headers: withAuth(token, {
      'Idempotency-Key': makeIdempotencyKey('artifact-version-create'),
    }),
    multipart: {
      file: {
        name: 'smoke.log',
        mimeType: 'text/plain',
        buffer: Buffer.from(logText, 'utf-8'),
      },
    },
  });
  const version = await parseJsonResponse(versionResponse, 'create artifact version');

  return {
    artifact,
    version,
    location: 'log:char=0-24',
  };
}

async function createClaimAndEvidence(request, coreApi, token, workspaceId, artifactVersionId, location) {
  const claimResponse = await request.post(`${coreApi}/workspaces/${workspaceId}/claims`, {
    headers: withAuth(token, {
      'Idempotency-Key': makeIdempotencyKey('claim-create'),
      'Content-Type': 'application/json',
    }),
    data: {
      kind: 'fact',
      text: 'The smoke execution produced deterministic output.',
      confidence: 'high',
    },
  });
  const claim = await parseJsonResponse(claimResponse, 'create claim');

  const evidenceResponse = await request.post(`${coreApi}/claims/${claim.id}/evidence`, {
    headers: withAuth(token, {
      'Idempotency-Key': makeIdempotencyKey('claim-evidence-create'),
      'Content-Type': 'application/json',
    }),
    data: {
      artifact_version_id: artifactVersionId,
      location,
    },
  });
  await parseJsonResponse(evidenceResponse, 'add claim evidence');

  return claim;
}

async function createDraftWithCitation(request, coreApi, token, workspaceId, claimId, artifactVersionId, location) {
  const draftResponse = await request.post(`${coreApi}/workspaces/${workspaceId}/drafts`, {
    headers: withAuth(token, {
      'Idempotency-Key': makeIdempotencyKey('draft-create'),
      'Content-Type': 'application/json',
    }),
    data: {
      title: 'UI Smoke Draft',
    },
  });
  const draft = await parseJsonResponse(draftResponse, 'create draft');

  const content = [
    '# UI Smoke Draft',
    '',
    `This draft references a claim [[claim:${claimId}]] and citation [[cite:${artifactVersionId}|${location}]].`,
  ].join('\n');

  const versionResponse = await request.post(`${coreApi}/drafts/${draft.id}/versions`, {
    headers: withAuth(token, {
      'Idempotency-Key': makeIdempotencyKey('draft-version-create'),
      'Content-Type': 'application/json',
    }),
    data: {
      content,
    },
  });
  await parseJsonResponse(versionResponse, 'create draft version');
}

async function assertNoViewerError(page) {
  const err = page.locator('.artifact-viewer-error');
  if (await err.isVisible().catch(() => false)) {
    const text = (await err.textContent()) || '';
    throw new Error(`Artifact viewer error visible: ${text.trim()}`);
  }

  const notFoundText = page.getByText(/Error:\\s*Not Found/i);
  if (await notFoundText.isVisible().catch(() => false)) {
    throw new Error('Found "Error: Not Found" in viewer');
  }
}

async function assertWorkspaceTabsReachable(page, workspaceId) {
  for (const tab of WORKSPACE_TABS) {
    const tabButton = page.getByRole('button', { name: tab.label, exact: true }).first();
    await tabButton.scrollIntoViewIfNeeded();
    await tabButton.click();
    await page.waitForURL(`**/projects/${workspaceId}/${tab.id}`, { timeout: 20_000 });

    const activeTab = page.locator('.tab-button.active', { hasText: tab.label }).first();
    await activeTab.waitFor({ state: 'visible', timeout: 20_000 });

    const visibleError = page.locator('.error').first();
    if (await visibleError.isVisible().catch(() => false)) {
      const text = ((await visibleError.textContent()) || '').trim();
      throw new Error(`Visible workspace error while loading tab '${tab.id}': ${text}`);
    }
  }
}

async function readStoredToken(page) {
  return page.evaluate((key) => {
    return localStorage.getItem(key) || sessionStorage.getItem(key);
  }, TOKEN_KEY);
}

async function waitForProjectsRouteOrToken(page, timeoutMs) {
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    const currentUrl = page.url();
    try {
      const parsed = new URL(currentUrl);
      if (/^\/projects(?:\/|$)/.test(parsed.pathname)) {
        return;
      }
    } catch {
      // Ignore non-URL intermediate states.
    }

    const loginError = page.locator('.error-message').first();
    if (await loginError.isVisible().catch(() => false)) {
      const text = ((await loginError.textContent()) || '').trim();
      throw new Error(`Dev login failed: ${text || 'unknown login error'}`);
    }

    const token = await readStoredToken(page);
    if (token) {
      return;
    }

    await page.waitForTimeout(200);
  }

  throw new Error(`Dev login did not reach /projects or set token within ${timeoutMs}ms (url=${page.url()})`);
}

async function main() {
  const requestedBrowser = (process.env.AGORA_SMOKE_BROWSER || 'chromium').toLowerCase();
  const browserType = BROWSER_TYPES[requestedBrowser];
  if (!browserType) {
    throw new Error(
      `Unsupported AGORA_SMOKE_BROWSER='${requestedBrowser}'. ` +
      `Expected one of: ${Object.keys(BROWSER_TYPES).join(', ')}`
    );
  }

  const requestedViewport = (process.env.AGORA_SMOKE_VIEWPORT || 'desktop').toLowerCase();
  const viewport = VIEWPORT_TYPES[requestedViewport];
  if (!viewport) {
    throw new Error(
      `Unsupported AGORA_SMOKE_VIEWPORT='${requestedViewport}'. ` +
      `Expected one of: ${Object.keys(VIEWPORT_TYPES).join(', ')}`
    );
  }

  const screenshotSuffix = requestedViewport === 'desktop'
    ? requestedBrowser
    : `${requestedBrowser}-${requestedViewport}`;
  const screenshotPath = `/tmp/agora-smoke-artifact-viewer-${screenshotSuffix}.png`;

  const browser = await browserType.launch({ headless: true });
  let page;
  try {
    page = await browser.newPage({ viewport });

    const base = process.env.AGORA_WEB_BASE_URL || 'http://localhost:3000';
    const coreApi = process.env.AGORA_CORE_API_URL || 'http://localhost:8000';

    // Fail fast if the backend isn't running; otherwise the script just times out on login.
    try {
      const r = await fetch(`${coreApi}/health`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    } catch {
      throw new Error(`Core API not reachable at ${coreApi}. Start it with \`make dev-core-api\` (and infra with \`make up\`).`);
    }

    await page.goto(`${base}/login`, { waitUntil: 'domcontentloaded' });

    // Dev login button is only present in Vite dev mode.
    const devLogin = page.getByRole('button', { name: /Dev Login/i });
    if (!(await devLogin.isVisible().catch(() => false))) {
      throw new Error('Dev Login button not visible. Run `npm run dev` for apps/web.');
    }

    await devLogin.click();
    await waitForProjectsRouteOrToken(page, 20_000);

    const token = await readStoredToken(page);
    if (!token) {
      throw new Error(`Missing token in storage (${TOKEN_KEY}) after dev login`);
    }

    if (!/^\/projects(?:\/|$)/.test(new URL(page.url()).pathname)) {
      await page.goto(`${base}/projects`, { waitUntil: 'domcontentloaded' });
    }

    const workspace = await createWorkspace(page.request, coreApi, token);
    const { artifact, version, location } = await createLogArtifactVersion(page.request, coreApi, token, workspace.id);
    const claim = await createClaimAndEvidence(page.request, coreApi, token, workspace.id, version.id, location);
    await createDraftWithCitation(page.request, coreApi, token, workspace.id, claim.id, version.id, location);

    await page.goto(`${base}/projects/${workspace.id}/overview`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Claims' }).waitFor({ timeout: 20_000 });
    if (requestedViewport === 'mobile') {
      await assertWorkspaceTabsReachable(page, workspace.id);
    }

    // Claims flow: evidence drawer -> provenance drill-down artifact viewer.
    await page.getByRole('button', { name: 'Claims' }).click();
    const evidenceButton = page.getByRole('button', { name: /Evidence 1/i }).first();
    await evidenceButton.waitFor({ state: 'visible', timeout: 20_000 });
    await evidenceButton.click();
    await page.locator('.evidence-drawer').waitFor({ state: 'visible', timeout: 20_000 });
    await page.locator('.snippet-text').waitFor({ state: 'visible', timeout: 20_000 });
    await page.getByRole('button', { name: 'Open Artifact Version' }).click();
    await page.locator('.artifact-viewer').first().waitFor({ state: 'visible', timeout: 20_000 });
    await assertNoViewerError(page);

    // Drafts flow: citation chip -> evidence drawer -> provenance drill-down.
    await page.getByRole('button', { name: 'Drafts' }).click();
    const citeChip = page.locator('.cite-chip').first();
    await citeChip.waitFor({ state: 'visible', timeout: 20_000 });
    await citeChip.click();
    await page.locator('.evidence-drawer').waitFor({ state: 'visible', timeout: 20_000 });
    await page.getByRole('button', { name: 'Open Artifact Version' }).click();
    await page.locator('.artifact-viewer').first().waitFor({ state: 'visible', timeout: 20_000 });
    await assertNoViewerError(page);

    // Artifacts flow: select artifact and load viewer.
    await page.getByRole('button', { name: 'Artifacts' }).click();
    const targetArtifact = page.locator('.artifact-item').filter({ hasText: artifact.short_id }).first();
    await targetArtifact.waitFor({ state: 'visible', timeout: 20_000 });
    await targetArtifact.click();
    await page.locator('.artifact-viewer').first().waitFor({ state: 'visible', timeout: 20_000 });
    await assertNoViewerError(page);

    await page.screenshot({ path: screenshotPath, fullPage: true });

    // eslint-disable-next-line no-console
    console.log(
      `OK: UI smoke flows validated for workspace ${workspace.id} on ${requestedBrowser}/${requestedViewport}. ` +
      'Claims/drafts provenance drill-down and artifact viewer are healthy. ' +
      `Screenshot: ${screenshotPath}`
    );
  } catch (err) {
    if (page) {
      try {
        await page.screenshot({ path: screenshotPath, fullPage: true });
        // eslint-disable-next-line no-console
        console.error(`SMOKE DEBUG: failure screenshot captured at ${screenshotPath}`);
      } catch (screenshotErr) {
        // eslint-disable-next-line no-console
        console.error(`SMOKE DEBUG: failed to capture screenshot: ${screenshotErr}`);
      }

      try {
        const loginError = page.locator('.error-message').first();
        if (await loginError.isVisible().catch(() => false)) {
          const text = ((await loginError.textContent()) || '').trim();
          // eslint-disable-next-line no-console
          console.error(`SMOKE DEBUG: login error message: ${text}`);
        }
      } catch {
        // Ignore debug-only failure path errors.
      }
    }
    throw err;
  } finally {
    await browser.close();
  }
}

main().catch((e) => {
  // eslint-disable-next-line no-console
  console.error('SMOKE FAILED:', e?.stack || String(e));
  process.exitCode = 1;
});
