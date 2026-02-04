/**
 * API Client for AGORA Core API
 * 
 * Per spec: UI is read-only, only uses GET endpoints (+ POST /auth/verify for login)
 */

const API_BASE_URL = '/api';

class APIClient {
  constructor() {
    this.token = sessionStorage.getItem('agent_session_jwt');
  }

  setToken(token) {
    this.token = token;
    if (token) {
      sessionStorage.setItem('agent_session_jwt', token);
    } else {
      sessionStorage.removeItem('agent_session_jwt');
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

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`
      }));
      throw new Error(error.detail || 'Request failed');
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

  async getCurrentAgent() {
    return this.request('/agents/me');
  }

  // Workspaces
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
    return this.request(`/artifact-versions/${versionId}/content`);
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
