import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import './EvidenceDrawer.css';

function EvidenceDrawer({ artifactVersionId, location, onClose, onOpenArtifactVersion }) {
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
    if (evidence?.source?.artifact_id) {
      const ref = `${evidence.source.artifact_id}@v${evidence.source.version || '?'}: ${evidence.normalized_location || location}`;
      navigator.clipboard.writeText(ref);
    }
  };

  const openArtifactVersion = () => {
    if (!onOpenArtifactVersion || !evidence?.source?.artifact_id) {
      return;
    }
    onOpenArtifactVersion({
      artifactId: evidence.source.artifact_id,
      versionId: artifactVersionId,
      location: evidence.normalized_location || location,
      artifactType: evidence.source.type || null,
      artifactVersion: evidence.source.version || null,
    });
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
                  <span className="status-indicator ok">
                    ok
                  </span>
                </div>

                <div className="meta-row">
                  <span className="meta-label">Artifact Version ID:</span>
                  <code className="meta-value location-code">{artifactVersionId}</code>
                </div>

                {evidence.source?.artifact_id && (
                  <div className="meta-row">
                    <span className="meta-label">Source Artifact ID:</span>
                    <code className="meta-value location-code">{evidence.source.artifact_id}</code>
                  </div>
                )}

                {evidence.source?.type && (
                  <div className="meta-row">
                    <span className="meta-label">Source Type:</span>
                    <span className="meta-value">{evidence.source.type}</span>
                  </div>
                )}

                {evidence.source?.version !== undefined && evidence.source?.version !== null && (
                  <div className="meta-row">
                    <span className="meta-label">Source Version:</span>
                    <span className="meta-value">v{evidence.source.version}</span>
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
                {evidence?.source?.artifact_id && (
                  <button className="action-button" onClick={copyDisplayReference}>
                    Copy Display Reference
                  </button>
                )}
                {evidence?.source?.artifact_id && onOpenArtifactVersion && (
                  <button className="action-button secondary" onClick={openArtifactVersion}>
                    Open Artifact Version
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
