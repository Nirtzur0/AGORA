import React, { useState } from 'react';
import apiClient from '../api/client';
import './CreateWorkspaceModal.css'; // Reuse basic modal styles
import './CreateCritiqueModal.css';

export function CreateCritiqueModal({ isOpen, onClose, workspaceId, targetType, targetId, onCreated }) {
  const [severity, setSeverity] = useState('minor');
  const [message, setMessage] = useState('');
  const [location, setLocation] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      if (!message.trim()) {
        throw new Error('Critique message is required');
      }

      await apiClient.createCritique(workspaceId, {
        target_type: targetType,
        target_id: targetId,
        target_location: location.trim() || undefined,
        severity,
        message: message.trim()
      });

      setMessage('');
      setLocation('');
      setSeverity('minor');
      if (onCreated) onCreated();
      onClose();
    } catch (err) {
        // Handle "Workspace ... not found" or other API errors nicely
      setError(err.message || 'Failed to create critique');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content critique-modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Add Critique</h2>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <div className="modal-context-info">
          <small>
            Targeting {targetType}: {targetId && targetId.substring(0, 8)}...
          </small>
        </div>

        <form onSubmit={handleSubmit} className="critique-form">
          <div className="modal-form-group">
            <label className="modal-form-label">Severity</label>
            <select 
              className="modal-form-select"
              value={severity}
              onChange={e => setSeverity(e.target.value)}
            >
                <option value="info">ℹ️ Info (Suggestion/Comment)</option>
                <option value="minor">⚠️ Minor (Should fix)</option>
                <option value="major">🔥 Major (Must fix)</option>
                <option value="blocking">⛔ Blocking (Cannot proceed)</option>
            </select>
          </div>

          <div className="modal-form-group">
            <label className="modal-form-label">Location (Optional)</label>
            <input
              className="modal-form-input"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. Section 2.1, Line 45, or specific code block"
            />
          </div>

          <div className="modal-form-group">
            <label className="modal-form-label">Critique</label>
            <textarea
              className="modal-form-textarea critique-textarea"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Describe the issue or feedback..."
              autoFocus
            />
          </div>

          <div className="modal-actions">
            <button 
              type="button" 
              className="btn btn-secondary" 
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button 
              type="submit" 
              className="btn btn-primary"
              disabled={isSubmitting || !message.trim()}
            >
              {isSubmitting ? 'Submitting...' : 'Submit Critique'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
