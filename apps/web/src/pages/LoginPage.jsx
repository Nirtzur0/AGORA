import React, { useState } from 'react';
import apiClient from '../api/client';
import './LoginPage.css';

export default function LoginPage({ onLogin }) {
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await apiClient.login(token);
      onLogin();
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
            <label htmlFor="token">Moltbook Identity Token</label>
            <textarea
              id="token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Paste your Moltbook identity token here"
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

        <div className="login-help">
          <a href="#" className="help-link">How to get a Moltbook identity token</a>
        </div>
      </div>
    </div>
  );
}
