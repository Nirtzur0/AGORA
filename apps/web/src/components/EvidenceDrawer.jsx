import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import './EvidenceDrawer.css';

function EvidenceDrawer({ artifactVersionId, location, onClose }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [evidence, setEvidence] = useState(null);

  useEffect(() => {
    if (!artifactVersionId || !location) return;

    setLoading(true);
    setError(null);

    apiClient.resolveEvidence(artifactVersionId, location)
      .then(data => {
        setEvidence(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message || 'Failed to resolve evidence');
        setLoading(false);
      });
  }, [artifactVersionId, location]);

  if (!artifactVersionId || !location) return null;

  const handleOverlayClick = (e) => {
    if (e.target.classList.contains('evidence-drawer-overlay')) {
      onClose();
    }
  };

  const copyPointer = () => {
    const pointer = JSON.stringify({
      artifact_version_id: artifactVersionId,
      location: location
    }, null, 2);
    navigator.clipboard.writeText(pointer);
  };

  const copyDisplayReference = () => {
    if (evidence?.artifact_short_id) {
      const ref = `${evidence.artifact_short_id}@v${evidence.version || '?'}: ${evidence.normalized_location || location}`;
      navigator.clipboard.writeText(ref);
    }
  };

  return (
    <div className="evidence-drawer-overlay" onClick={handleOverlayClick}>
      <div className="evidence-drawer">
        <div className="evidence-drawer-header">
          <h3>Evidence Snippet</h3>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="evidence-drawer-content">
          {loading && <p className="loading-message">Resolving evidence...</p>}
          
          {error && (
            <div className="error-box">
              <strong>Resolution Failed</strong>
              <p>{error}</p>
            </div>
          )}

          {evidence && !loading && !error && (
            <>
              <div className="evidence-meta">
                <div className="meta-row">
                  <span className="meta-label">Status:</span>
                  <span className={`status-indicator ${evidence.status}`}>
                    {evidence.status}
                  </span>
                </div>
                
                {evidence.artifact_short_id && (
                  <div className="meta-row">
                    <span className="meta-label">Source:</span>
                    <span className="meta-value">
                      {evidence.artifact_short_id}
                      {evidence.version && `@v${evidence.version}`}
                      {evidence.artifact_type && ` (${evidence.artifact_type})`}
                    </span>
                  </div>
                )}

                <div className="meta-row">
                  <span className="meta-label">Original Location:</span>
                  <code className="meta-value location-code">{location}</code>
                </div>

                {evidence.normalized_location && evidence.normalized_location !== location && (
                  <div className="meta-row">
                    <span className="meta-label">Normalized Location:</span>
                    <code className="meta-value location-code">{evidence.normalized_location}</code>
                  </div>
                )}
              </div>

              {evidence.snippet && (
                <div className="evidence-snippet">
                  <div className="snippet-header">
                    <strong>Snippet:</strong>
                  </div>
                  <pre className="snippet-text">{evidence.snippet}</pre>
                </div>
              )}

              {evidence.error_code && (
                <div className="error-box">
                  <strong>Error Code: {evidence.error_code}</strong>
                  {evidence.error_detail && <p>{evidence.error_detail}</p>}
                </div>
              )}

              <div className="evidence-actions">
                <button className="action-button" onClick={copyPointer}>
                  Copy Pointer JSON
                </button>
                {evidence.artifact_short_id && (
                  <button className="action-button" onClick={copyDisplayReference}>
                    Copy Display Reference
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default EvidenceDrawer;
