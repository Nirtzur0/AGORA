import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { PageContainer, Card } from '../components/Layout';
import { PhaseBadge } from '../components/Badge';
import './ProjectsPage.css';

export default function ProjectsPage() {
  const navigate = useNavigate();
  const [workspaces, setWorkspaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadWorkspaces();
  }, []);

  const loadWorkspaces = async () => {
    try {
      const data = await apiClient.getWorkspaces();
      setWorkspaces(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <PageContainer title="Projects">
        <div className="loading">Loading projects...</div>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer title="Projects">
        <div className="error">Error loading projects: {error}</div>
      </PageContainer>
    );
  }

  return (
    <PageContainer title="Projects">
      {workspaces.length === 0 ? (
        <Card>
          <div className="empty-state">
            <p>No projects found.</p>
          </div>
        </Card>
      ) : (
        <div className="projects-grid">
          {workspaces.map((workspace) => (
            <div
              key={workspace.id}
              className="project-card"
              onClick={() => navigate(`/projects/${workspace.id}/overview`)}
            >
              <div className="project-header">
                <h3 className="project-name">{workspace.name}</h3>
                <PhaseBadge phase={workspace.phase} />
              </div>
              
              {workspace.description && (
                <p className="project-description">{workspace.description}</p>
              )}
              
              {workspace.tags && workspace.tags.length > 0 && (
                <div className="project-tags">
                  {workspace.tags.map((tag, idx) => (
                    <span key={idx} className="tag">{tag}</span>
                  ))}
                </div>
              )}
              
              <div className="project-meta">
                <span className="meta-item">
                  Last updated: {new Date(workspace.updated_at || workspace.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </PageContainer>
  );
}
