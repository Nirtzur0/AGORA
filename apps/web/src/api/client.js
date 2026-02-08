/**
 * API Client for AGORA Core API
 * 
 * Per spec: UI is read-only, only uses GET endpoints (+ POST /auth/verify for login)
 */

const API_BASE_URL = '/api';
const TOKEN_KEY = 'agent_session_jwt';

class APIClient {
  constructor() {
    // Prefer localStorage for persistence across refreshes; fall back to sessionStorage.
    this.token = (typeof window !== 'undefined' && (localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY))) || null;
  }

  setToken(token) {
    this.token = token;
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
      sessionStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
    }
  }

  getToken() {
    return this.token;
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.token && !options.skipAuth) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    let response;
    try {
      response = await fetch(url, {
        ...options,
        headers,
      });
    } catch (err) {
      // Browser-level network error (most commonly: core-api not running).
      throw new Error(
        'Cannot reach Core API (expected at /api). Start infra with `make up`, then start the API with `make dev-core-api`.'
      );
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`
      }));
      let message = error.detail || 'Request failed';
      if (typeof message === 'object') {
        message = message.message || JSON.stringify(message);
      }
      throw new Error(message);
    }

    return response.json();
  }

  // Auth
  async login(moltbookToken) {
    const data = await this.request('/auth/verify', {
      method: 'POST',
      skipAuth: true,
      body: JSON.stringify({ moltbook_identity_token: moltbookToken }),
    });
    this.setToken(data.agent_session_jwt);
    return data;
  }

  // Dev convenience: exchange a Moltbook identity token via header (same as curl examples).
  async loginViaMoltbookHeader(moltbookIdentityToken) {
    const data = await this.request('/auth/moltbook', {
      method: 'POST',
      skipAuth: true,
      headers: {
        'X-Moltbook-Identity': moltbookIdentityToken,
      },
    });
    this.setToken(data.agent_session_jwt);
    return data;
  }

  async getCurrentAgent() {
    return this.request('/agents/me');
  }

  // Workspaces
  async createWorkspace(data) {
    return this.request('/workspaces', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getWorkspaces(filters = {}) {
    const params = new URLSearchParams();
    if (filters.phase) params.append('phase', filters.phase);
    if (filters.tags) params.append('tags', filters.tags);
    const query = params.toString() ? `?${params.toString()}` : '';
    return this.request(`/workspaces${query}`);
  }

  async getWorkspace(workspaceId) {
    return this.request(`/workspaces/${workspaceId}`);
  }

  async getWorkspaceEvents(workspaceId) {
    return this.request(`/workspaces/${workspaceId}/events`);
  }

  async getWorkspaceLogs(workspaceId) {
    return this.request(`/workspaces/${workspaceId}/logs`);
  }

  async getWorkspaceArtifacts(workspaceId) {
    return this.request(`/workspaces/${workspaceId}/artifacts`);
  }

  async getWorkspaceClaims(workspaceId) {
    return this.request(`/workspaces/${workspaceId}/claims`);
  }

  async getWorkspaceCritiques(workspaceId) {
    return this.request(`/workspaces/${workspaceId}/critiques`);
  }

  async createCritique(workspaceId, data) {
    return this.request(`/workspaces/${workspaceId}/critiques`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getWorkspaceTasks(workspaceId) {
    return this.request(`/workspaces/${workspaceId}/tasks`);
  }

  // Artifacts
  async getArtifact(artifactId) {
    return this.request(`/artifacts/${artifactId}`);
  }

  async getArtifactVersions(artifactId) {
    return this.request(`/artifacts/${artifactId}/versions`);
  }

  async getArtifactVersionContent(versionId) {
    // UI uses the processed view endpoint; raw bytes live at `/content`.
    try {
      return await this.request(`/artifact-versions/${versionId}/view`);
    } catch (err) {
      // Most common dev footgun: core-api running from an older process without `/view` routes.
      if (err?.message === 'Not Found') {
        throw new Error('Core API endpoint missing: GET /artifact-versions/{id}/view. Restart core-api and refresh.');
      }
      throw err;
    }
  }

  // Rule Checks
  async getRuleChecks(workspaceId) {
    return this.request(`/rule-checks?workspace_id=${workspaceId}`);
  }

  // Evidence
  async resolveEvidence(artifactVersionId, location) {
    const params = new URLSearchParams({
      artifact_version_id: artifactVersionId,
      location,
    });
    return this.request(`/evidence/resolve?${params.toString()}`);
  }

  // Search
  async search(query, workspaceId = null) {
    const params = new URLSearchParams({ query });
    if (workspaceId) params.append('workspace_id', workspaceId);
    return this.request(`/search?${params.toString()}`);
  }

  // Agents
  async getAgent(agentId) {
    return this.request(`/agents/${agentId}`);
  }
}

export default new APIClient();
