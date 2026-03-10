import React, { useEffect, useMemo, useState } from 'react';
import apiClient from '../api/client';
import './LoginPage.css';

export default function LoginPage({ onLogin }) {
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [coreApiStatus, setCoreApiStatus] = useState('unknown');

  const devIdentity = useMemo(
    () => import.meta.env.VITE_DEV_MOLTBOOK_IDENTITY || 'debug-token-clawdbot',
    []
  );

  const devAutoLoginEnabled = useMemo(() => {
    const value = import.meta.env.VITE_DEV_AUTO_LOGIN;
    return value === '1' || value === 'true' || value === true;
  }, []);

  useEffect(() => {
    if (!import.meta.env.DEV) return undefined;
    let cancelled = false;

    const check = async () => {
      try {
        await apiClient.request('/health', { skipAuth: true });
        if (!cancelled) setCoreApiStatus('up');
      } catch {
        if (!cancelled) setCoreApiStatus('down');
      }
    };

    check();
    const interval = window.setInterval(check, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (!import.meta.env.DEV || !devAutoLoginEnabled || apiClient.getToken() || loading || token.trim()) return;
    void handleDevLogin();
  }, [devAutoLoginEnabled, loading, token]);

  const handleDevLogin = async () => {
    setError('');
    setLoading(true);

    try {
      await apiClient.loginViaMoltbookHeader(devIdentity);
      onLogin();
    } catch (err) {
      setError(err.message || 'Dev login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      const trimmed = token.trim();
      if (/^eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$/.test(trimmed)) {
        apiClient.setToken(trimmed);
        await apiClient.getCurrentAgent();
      } else {
        await apiClient.login(trimmed);
      }
      onLogin();
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-scene">
      <div className="login-scene-copy">
        <p className="login-kicker">Research records without silent gaps</p>
        <h1>Trace every claim back to immutable evidence.</h1>
        <p className="login-summary">
          AGORA is a workspace console for evidence-grounded research. Authenticate, inspect provenance,
          author grounded records, and monitor requests without crossing authority boundaries.
        </p>
        <div className="login-feature-list">
          <div className="login-feature">
            <span>Immutable artifact versions</span>
            <small>Artifacts, draft revisions, and citations stay version-pinned.</small>
          </div>
          <div className="login-feature">
            <span>Operational visibility</span>
            <small>Tasks, rule checks, logs, events, and gate readiness live in one console.</small>
          </div>
          <div className="login-feature">
            <span>Agent-safe authoring</span>
            <small>Only browser-safe mutations are exposed; orchestrator-owned actions remain read-only.</small>
          </div>
        </div>
      </div>

      <div className="login-panel">
        <div className="login-panel-header">
          <p className="login-panel-overline">Workspace access</p>
          <h2>Authenticate with Moltbook or a local JWT</h2>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-label" htmlFor="token">
            Identity token
          </label>
          <textarea
            id="token"
            className="text-area"
            rows="6"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="Paste a Moltbook identity token or a test JWT"
            disabled={loading}
            required
          />

          {error ? <div className="login-error">{error}</div> : null}

          <button type="submit" className="btn btn-primary login-submit" disabled={loading || !token.trim()}>
            {loading ? 'Verifying…' : 'Verify and continue'}
          </button>
        </form>

        {import.meta.env.DEV ? (
          <div className="login-dev-tools">
            <div className="login-dev-status">
              <span>Core API</span>
              <span className={`pill status-${coreApiStatus === 'up' ? 'good' : coreApiStatus === 'down' ? 'danger' : 'info'}`}>
                {coreApiStatus}
              </span>
            </div>
            <button type="button" className="btn btn-secondary" onClick={handleDevLogin} disabled={loading}>
              {loading ? 'Signing in…' : `Dev Login (${devIdentity})`}
            </button>
          </div>
        ) : null}

        <div className="login-footer-links">
          <a href="/api/auth.md" target="_blank" rel="noreferrer">
            View auth instructions
          </a>
        </div>
      </div>
    </div>
  );
}
