import { chromium } from 'playwright';

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();

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
    await page.waitForURL('**/projects', { timeout: 20_000 });

    // Wait for the Projects page to finish loading.
    await page.waitForFunction(() => {
      const loading = document.querySelector('.loading');
      const grid = document.querySelector('.projects-grid');
      const empty = document.querySelector('.empty-state');
      return !loading || grid || empty;
    }, { timeout: 20_000 });

    // If this dev identity has no projects yet, create one via the UI.
    if ((await page.locator('.project-card').count()) === 0) {
      const newProjectBtn = page.getByRole('button', { name: /\+\s*New Project/i });
      await newProjectBtn.click();

      await page.getByLabel('Project Name').fill(`Smoke Project ${Date.now()}`);
      await page.getByRole('button', { name: /Create Project/i }).click();

      await page.locator('.project-card').first().waitFor({ state: 'visible', timeout: 20_000 });
    }

    const firstProject = page.locator('.project-card').first();
    await firstProject.click();

    // Workspace routes look like /projects/:workspaceId/:tab
    await page.waitForURL('**/projects/*/*', { timeout: 20_000 });

    await page.getByRole('button', { name: 'Artifacts' }).click();

    const firstArtifact = page.locator('.artifact-item').first();
    await firstArtifact.waitFor({ state: 'visible', timeout: 20_000 });
    await firstArtifact.click();

    await page.locator('.artifact-viewer').waitFor({ state: 'visible', timeout: 20_000 });

    const err = page.locator('.artifact-viewer-error');
    if (await err.isVisible().catch(() => false)) {
      const msg = (await err.textContent()) || '';
      throw new Error(`Artifact viewer error visible: ${msg.trim()}`);
    }

    const notFoundText = page.getByText(/Error:\\s*Not Found/i);
    if (await notFoundText.isVisible().catch(() => false)) {
      throw new Error('Found "Error: Not Found" in viewer');
    }

    await page.screenshot({ path: '/tmp/agora-smoke-artifact-viewer.png', fullPage: true });

    // eslint-disable-next-line no-console
    console.log('OK: artifact viewer loaded. Screenshot: /tmp/agora-smoke-artifact-viewer.png');
  } finally {
    await browser.close();
  }
}

main().catch((e) => {
  // eslint-disable-next-line no-console
  console.error('SMOKE FAILED:', e?.stack || String(e));
  process.exitCode = 1;
});
