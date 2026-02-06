import React, { useEffect, useId, useState } from 'react';
import apiClient from '../api/client';
import './CreateWorkspaceModal.css';

export function CreateWorkspaceModal({ isOpen, onClose, onCreated }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const titleId = useId();

  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      if (!name.trim()) {
        throw new Error('Workspace name is required');
      }

      await apiClient.createWorkspace({
        name: name.trim(),
        description: description.trim(),
      });

      setName('');
      setDescription('');
      onCreated();
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to create workspace');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 className="modal-title" id={titleId}>Create New Project</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="modal-form-group">
            <label className="modal-form-label" htmlFor="create-workspace-name">Project Name</label>
            <input
              id="create-workspace-name"
              className="modal-form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Lithium-Ion Battery Optimization"
              autoFocus
            />
          </div>

          <div className="modal-form-group">
            <label className="modal-form-label" htmlFor="create-workspace-description">Description</label>
            <textarea
              id="create-workspace-description"
              className="modal-form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Briefly describe the research goals..."
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
              disabled={isSubmitting || !name.trim()}
            >
              {isSubmitting ? 'Creating...' : 'Create Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
