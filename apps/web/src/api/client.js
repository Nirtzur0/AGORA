import {
  asArray,
  normalizeArtifact,
  normalizeClaim,
  normalizeCritique,
  normalizeRuleCheck,
  normalizeSearchResponse,
  normalizeTask,
} from './normalizers';

const API_BASE_URL = '/api';
const TOKEN_KEY = 'agent_session_jwt';

function makeIdempotencyKey(prefix = 'agora') {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

class APIClient {
  constructor() {
    this.token =
      (typeof window !== 'undefined' &&
        (localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY))) ||
      null;
  }

  setToken(token) {
    this.token = token;
    if (typeof window === 'undefined') return;

    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
      sessionStorage.setItem(TOKEN_KEY, token);
      return;
    }

    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
  }

  getToken() {
    return this.token;
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers = { ...(options.headers || {}) };

    if (this.token && !options.skipAuth) {
      headers.Authorization = `Bearer ${this.token}`;
    }

    const shouldUseJson =
      options.json !== undefined && !(options.body instanceof FormData) && !options.rawBody;
    if (shouldUseJson && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    if (options.idempotent) {
      headers['Idempotency-Key'] = options.idempotencyKey || makeIdempotencyKey(options.idempotencyPrefix);
    }

    let body;
    if (options.body instanceof FormData) {
      body = options.body;
      delete headers['Content-Type'];
    } else if (options.rawBody !== undefined) {
      body = options.rawBody;
    } else if (shouldUseJson) {
      body = JSON.stringify(options.json);
    } else {
      body = options.body;
    }

    let response;
    try {
      response = await fetch(url, {
        method: options.method || 'GET',
        headers,
        body,
      });
    } catch (error) {
      throw new Error(
        'Cannot reach Core API (expected at /api). Start infra with `make up`, then start the API with `make dev-core-api`.'
      );
    }

    const contentType = response.headers.get('content-type') || '';
    let payload = null;

    if (contentType.includes('application/json')) {
      payload = await response.json().catch(() => null);
    } else if (!contentType.startsWith('application/octet-stream') && response.status !== 204) {
      payload = await response.text().catch(() => null);
    }

    if (!response.ok) {
      const detail = payload?.detail ?? payload?.message ?? payload;
      if (typeof detail === 'object' && detail !== null) {
        throw new Error(detail.message || JSON.stringify(detail));
      }
      throw new Error(detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    if (contentType.startsWith('application/octet-stream')) {
      return response;
    }

    return payload;
  }

  async mutate(endpoint, options = {}) {
    return this.request(endpoint, {
      ...options,
      idempotent: options.idempotent ?? true,
    });
  }

  async login(moltbookToken) {
    const data = await this.request('/auth/verify', {
      method: 'POST',
      skipAuth: true,
      json: { moltbook_identity_token: moltbookToken },
    });
    this.setToken(data.agent_session_jwt);
    return data;
  }

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

  async getRoles() {
    return asArray(await this.request('/workspaces/roles'));
  }

  async createWorkspace(data) {
    return this.mutate('/workspaces', {
      method: 'POST',
      json: data,
      idempotencyPrefix: 'workspace-create',
    });
  }

  async getWorkspaces(phase) {
    const query = phase ? `?phase=${encodeURIComponent(phase)}` : '';
    return asArray(await this.request(`/workspaces${query}`));
  }

  async getWorkspace(workspaceId) {
    return this.request(`/workspaces/${workspaceId}`);
  }

  async updateWorkspace(workspaceId, description) {
    return this.mutate(`/workspaces/${workspaceId}`, {
      method: 'PATCH',
      json: { description },
      idempotencyPrefix: 'workspace-update',
    });
  }

  async getWorkspaceJoinRequests(workspaceId, params = {}) {
    const query = new URLSearchParams();
    if (params.status) query.set('status', params.status);
    if (params.agentId) query.set('agent_id', params.agentId);
    const suffix = query.toString() ? `?${query.toString()}` : '';
    return asArray(await this.request(`/workspaces/${workspaceId}/join-requests${suffix}`));
  }

  async createJoinRequest(workspaceId, roleId) {
    return this.mutate(`/workspaces/${workspaceId}/join-requests`, {
      method: 'POST',
      json: { role_id: roleId },
      idempotencyPrefix: 'join-request-create',
    });
  }

  async reviewJoinRequest(workspaceId, requestId, approve, reason) {
    return this.mutate(`/workspaces/${workspaceId}/join-requests/${requestId}/review`, {
      method: 'POST',
      json: { approve, reason },
      idempotencyPrefix: 'join-request-review',
    });
  }

  async getPhaseStatus(workspaceId) {
    return this.request(`/workspaces/${workspaceId}/phase`);
  }

  async getGateStatus(workspaceId) {
    return this.request(`/workspaces/${workspaceId}/gate-status`);
  }

  async getWorkspaceEvents(workspaceId) {
    const data = await this.request(`/workspaces/${workspaceId}/events`);
    return asArray(data, 'events');
  }

  async getWorkspaceLogs(workspaceId) {
    const data = await this.request(`/workspaces/${workspaceId}/logs`);
    return asArray(data, 'logs');
  }

  async getWorkspaceArtifacts(workspaceId, type) {
    const query = type ? `?type=${encodeURIComponent(type)}` : '';
    const data = await this.request(`/workspaces/${workspaceId}/artifacts${query}`);
    return asArray(data, 'artifacts').map(normalizeArtifact);
  }

  async createArtifact(workspaceId, type, metadata = {}) {
    const artifact = await this.mutate(`/workspaces/${workspaceId}/artifacts`, {
      method: 'POST',
      json: { type, metadata },
      idempotencyPrefix: 'artifact-create',
    });
    return normalizeArtifact(artifact);
  }

  async createArtifactVersion(artifactId, file) {
    const formData = new FormData();
    formData.append('file', file);

    return this.mutate(`/artifacts/${artifactId}/versions`, {
      method: 'POST',
      body: formData,
      idempotencyPrefix: 'artifact-version-create',
    });
  }

  async getArtifact(artifactId) {
    return normalizeArtifact(await this.request(`/artifacts/${artifactId}`));
  }

  async getArtifactVersions(artifactId) {
    const data = await this.request(`/artifacts/${artifactId}/versions`);
    return asArray(data, 'versions');
  }

  async getArtifactVersionContent(versionId) {
    try {
      return await this.request(`/artifact-versions/${versionId}/view`);
    } catch (error) {
      if (error?.message === 'Not Found') {
        throw new Error('Core API endpoint missing: GET /artifact-versions/{id}/view. Restart core-api and refresh.');
      }
      throw error;
    }
  }

  async getWorkspaceClaims(workspaceId) {
    const data = await this.request(`/workspaces/${workspaceId}/claims`);
    return asArray(data, 'claims').map(normalizeClaim);
  }

  async createClaim(workspaceId, payload) {
    return this.mutate(`/workspaces/${workspaceId}/claims`, {
      method: 'POST',
      json: payload,
      idempotencyPrefix: 'claim-create',
    });
  }

  async addEvidenceToClaim(claimId, payload) {
    return this.mutate(`/claims/${claimId}/evidence`, {
      method: 'POST',
      json: payload,
      idempotencyPrefix: 'claim-evidence-create',
    });
  }

  async getWorkspaceCritiques(workspaceId, filters = {}) {
    const params = new URLSearchParams();
    if (filters.targetId) params.set('target_id', filters.targetId);
    if (filters.status) params.set('status', filters.status);
    if (filters.severity) params.set('severity', filters.severity);
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return asArray(await this.request(`/workspaces/${workspaceId}/critiques${suffix}`)).map(normalizeCritique);
  }

  async createCritique(workspaceId, payload) {
    return this.mutate(`/workspaces/${workspaceId}/critiques`, {
      method: 'POST',
      json: payload,
      idempotencyPrefix: 'critique-create',
    });
  }

  async updateCritique(critiqueId, payload) {
    return this.mutate(`/critiques/${critiqueId}`, {
      method: 'PATCH',
      json: payload,
      idempotencyPrefix: 'critique-update',
    });
  }

  async getWorkspaceTasks(workspaceId) {
    return asArray(await this.request(`/workspaces/${workspaceId}/tasks`)).map(normalizeTask);
  }

  async updateTask(taskId, payload) {
    return this.mutate(`/tasks/${taskId}`, {
      method: 'PATCH',
      json: payload,
      idempotencyPrefix: 'task-update',
    });
  }

  async getDraftVersions(draftId) {
    const data = await this.request(`/drafts/${draftId}/versions`);
    return asArray(data, 'versions');
  }

  async createDraft(workspaceId, title) {
    return this.mutate(`/workspaces/${workspaceId}/drafts`, {
      method: 'POST',
      json: { title },
      idempotencyPrefix: 'draft-create',
    });
  }

  async createDraftVersion(draftId, content) {
    return this.mutate(`/drafts/${draftId}/versions`, {
      method: 'POST',
      json: { content },
      idempotencyPrefix: 'draft-version-create',
    });
  }

  async getRuleChecks(workspaceId) {
    return asArray(await this.request(`/rule-checks?workspace_id=${workspaceId}`)).map(normalizeRuleCheck);
  }

  async runRuleCheck(workspaceId, draftArtifactVersionId) {
    return this.mutate(`/workspaces/${workspaceId}/requests/run_rulecheck`, {
      method: 'POST',
      json: { draft_artifact_version_id: draftArtifactVersionId },
      idempotencyPrefix: 'rule-check-run',
    });
  }

  async requestIngestPdf(workspaceId, artifactId) {
    return this.mutate(`/workspaces/${workspaceId}/requests/ingest_pdf`, {
      method: 'POST',
      json: { artifact_id: artifactId },
      idempotencyPrefix: 'ingest-pdf',
    });
  }

  async requestIngestRepo(workspaceId, payload) {
    return this.mutate(`/workspaces/${workspaceId}/requests/ingest_repo`, {
      method: 'POST',
      json: payload,
      idempotencyPrefix: 'ingest-repo',
    });
  }

  async requestRunSandbox(workspaceId, payload) {
    return this.mutate(`/workspaces/${workspaceId}/requests/run_sandbox`, {
      method: 'POST',
      json: payload,
      idempotencyPrefix: 'sandbox-run',
    });
  }

  async resolveEvidence(artifactVersionId, location) {
    const params = new URLSearchParams({
      artifact_version_id: artifactVersionId,
      location,
    });
    return this.request(`/evidence/resolve?${params.toString()}`);
  }

  async search(query, workspaceId = null) {
    const params = new URLSearchParams({ query });
    if (workspaceId) params.append('workspace_id', workspaceId);
    return normalizeSearchResponse(await this.request(`/search?${params.toString()}`));
  }
}

export default new APIClient();
