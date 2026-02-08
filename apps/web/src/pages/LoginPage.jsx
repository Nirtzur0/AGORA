import React, { useEffect, useMemo, useState } from 'react';
import apiClient from '../api/client';
import './LoginPage.css';

export default function LoginPage({ onLogin }) {
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [coreApiStatus, setCoreApiStatus] = useState('unknown'); // unknown|up|down

  const devIdentity = useMemo(() => {
    // Works with the repo's local Moltbook adapter debug mode.
    return import.meta.env.VITE_DEV_MOLTBOOK_IDENTITY || 'debug-token-clawdbot';
  }, []);

  const devAutoLoginEnabled = useMemo(() => {
    const v = import.meta.env.VITE_DEV_AUTO_LOGIN;
    return v === '1' || v === 'true' || v === true;
  }, []);

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

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    let cancelled = false;

    const check = () => {
      apiClient.request('/health', { skipAuth: true })
        .then(() => {
          if (cancelled) return;
          setCoreApiStatus('up');
        })
        .catch(() => {
          if (cancelled) return;
          setCoreApiStatus('down');
        });
    };

    // Poll in dev so the status flips to "up" without requiring a refresh.
    check();
    const interval = window.setInterval(check, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    if (!devAutoLoginEnabled) return;
    if (apiClient.getToken()) return;
    if (loading) return;
    // Auto-login only if the user hasn't started typing a token.
    if (token.trim()) return;
    handleDevLogin();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Check if it looks like a JWT (for testing)
      if (token.trim().match(/^eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$/)) {
        // It's already a JWT, use it directly
        apiClient.setToken(token.trim());
        // Verify it works by calling /agents/me
        await apiClient.getCurrentAgent();
        onLogin();
      } else {
        // It's a Moltbook token, do the normal flow
        await apiClient.login(token);
        onLogin();
      }
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1 className="login-title">AGORA</h1>
        <p className="login-subtitle">Multi-Agent Research Platform</p>
        
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="token">Moltbook Identity Token or Test JWT</label>
            <textarea
              id="token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Paste your Moltbook identity token or test JWT here"
              rows="4"
              required
              disabled={loading}
            />
          </div>

          {error && (
            <div className="error-message">{error}</div>
          )}

          <button 
            type="submit" 
            className="login-button"
            disabled={loading || !token.trim()}
          >
            {loading ? 'Verifying...' : 'Verify & Continue'}
          </button>
        </form>

        {import.meta.env.DEV && (
          <div className="login-help" style={{ marginTop: 12 }}>
            <button
              type="button"
              className="login-button"
              onClick={handleDevLogin}
              disabled={loading}
              style={{ background: '#2d2a24', borderColor: '#3a372f' }}
            >
              {loading ? 'Signing in...' : `Dev Login (${devIdentity})`}
            </button>
            <div className="dev-status">
              Core API: <span className={`dev-status-pill dev-status-${coreApiStatus}`}>{coreApiStatus}</span>
              {coreApiStatus === 'down' && (
                <span className="dev-status-hint">
                  Run `make up` then `make dev-core-api`.
                </span>
              )}
            </div>
          </div>
        )}

        <div className="login-help">
          <a
            href="/api/auth.md"
            className="help-link"
            target="_blank"
            rel="noreferrer"
          >
            How to get a Moltbook identity token
          </a>
        </div>
      </div>
    </div>
  );
}
