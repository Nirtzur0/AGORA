import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { PageContainer, Card } from '../components/Layout';
import { PhaseBadge, StatusBadge } from '../components/Badge';
import { FilterBar } from '../components/Molecules';
import { Timestamp, IdentityChip } from '../components/Atoms';
import { CreateWorkspaceModal } from '../components/CreateWorkspaceModal';
import './ProjectsPage.css';

export default function ProjectsPage() {
  const navigate = useNavigate();
  const [workspaces, setWorkspaces] = useState([]);
  const [workspaceDetails, setWorkspaceDetails] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState({});
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  useEffect(() => {
    loadWorkspaces();
  }, []);

  const loadWorkspaces = async () => {
    try {
      const data = await apiClient.getWorkspaces();
      setWorkspaces(data);
      // Load additional details for each workspace in parallel
      const detailsPromises = data.map(async (ws) => {
        try {
          const [artifactsResp, ruleChecks, critiques] = await Promise.all([
            // Core API returns `{ artifacts: [...] }` for this endpoint.
            apiClient.getWorkspaceArtifacts(ws.id).catch(() => ({ artifacts: [] })),
            apiClient.getRuleChecks(ws.id).catch(() => []),
            apiClient.getWorkspaceCritiques(ws.id).catch(() => [])
          ]);

          const artifacts = Array.isArray(artifactsResp) ? artifactsResp : (artifactsResp?.artifacts || []);
          return {
            id: ws.id,
            artifactsCount: artifacts.length,
            failingRuleChecks: ruleChecks.filter(r => r.status === 'fail').length,
            blockingCritiques: critiques.filter(c => c.severity === 'blocking' && c.status === 'open').length
          };
        } catch {
          return { id: ws.id, artifactsCount: 0, failingRuleChecks: 0, blockingCritiques: 0 };
        }
      });
      const details = await Promise.all(detailsPromises);
      const detailsMap = {};
      details.forEach(d => detailsMap[d.id] = d);
      setWorkspaceDetails(detailsMap);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (filterId, value) => {
    setFilters({ ...filters, [filterId]: value });
  };

  const handleClearFilters = () => {
    setFilters({});
  };

  const filterDefinitions = [
    {
      id: 'phase',
      label: 'Phase',
      type: 'pills',
      multiple: true,
      options: [
        { value: 'INIT', label: 'Init' },
        { value: 'LIT_REVIEW', label: 'Lit Review' },
        { value: 'CLAIM_VALIDATION', label: 'Claim Validation' },
        { value: 'HYPOTHESIS_PLANNING', label: 'Hypothesis Planning' },
        { value: 'EXPERIMENTATION', label: 'Experimentation' },
        { value: 'SYNTHESIS', label: 'Synthesis' },
        { value: 'INTERNAL_REVIEW', label: 'Internal Review' },
        { value: 'FINALIZED', label: 'Finalized' },
        { value: 'ARCHIVED', label: 'Archived' }
      ],
      value: filters.phase || []
    },
    {
      id: 'hasBlockers',
      label: 'Status',
      type: 'toggle',
      toggleLabel: 'Has Blockers',
      value: filters.hasBlockers || false
    }
  ];

  const filteredWorkspaces = workspaces.filter((ws) => {
    if (filters.phase && filters.phase.length > 0 && !filters.phase.includes(ws.phase)) {
      return false;
    }
    if (filters.hasBlockers) {
      const details = workspaceDetails[ws.id];
      if (!details || (details.failingRuleChecks === 0 && details.blockingCritiques === 0)) {
        return false;
      }
    }
    return true;
  });

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
    <PageContainer 
      title="Projects"
      actions={
        <button 
          className="btn btn-primary"
          onClick={() => setIsCreateModalOpen(true)}
        >
          + New Project
        </button>
      }
    >
      <FilterBar 
        filters={filterDefinitions}
        onFilterChange={handleFilterChange}
        onClear={handleClearFilters}
      />
      
      {filteredWorkspaces.length === 0 ? (
        <Card>
          <div className="empty-state">
            <p>No projects found matching filters.</p>
          </div>
        </Card>
      ) : (
        <div className="projects-grid">
          {filteredWorkspaces.map((workspace) => {
            const details = workspaceDetails[workspace.id] || {};
            const hasBlockers = (details.failingRuleChecks > 0) || (details.blockingCritiques > 0);
            
            return (
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
                
                <div className="project-stats">
                  <div className="stat-item">
                    📦 {details.artifactsCount || 0} artifacts
                  </div>
                  {hasBlockers && (
                    <div className="stat-item blockers">
                      ⚠️ {details.failingRuleChecks + details.blockingCritiques} blockers
                    </div>
                  )}
                </div>
                
                <div className="project-meta">
                  <span className="meta-item">
                    Last updated: <Timestamp date={workspace.updated_at || workspace.created_at} />
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
      <CreateWorkspaceModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreated={loadWorkspaces}
      />
    </PageContainer>
  );
}
