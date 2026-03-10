import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { SectionCard } from '../components/Layout';
import './ProjectsPage.css';

const PHASES = ['INIT', 'LIT_REVIEW', 'CLAIM_VALIDATION', 'HYPOTHESIS_PLANNING', 'EXPERIMENTATION', 'SYNTHESIS', 'INTERNAL_REVIEW', 'FINALIZED', 'ARCHIVED'];

function scoreWorkspaceHealth(detail) {
  const blockers = (detail.failingRuleChecks || 0) + (detail.blockingCritiques || 0);
  if (blockers > 0) return { label: 'Needs intervention', tone: 'danger' };
  if ((detail.openTasks || 0) > 0) return { label: 'In flight', tone: 'warning' };
  return { label: 'Stable', tone: 'good' };
}

function WorkspaceCreateDialog({ open, onClose, onCreated }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  if (!open) return null;

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSaving(true);

    try {
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
      setSaving(false);
    }
  };

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div className="dialog-card" onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="dialog-kicker">New workspace</p>
            <h2>Open a research workspace</h2>
          </div>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>
        <form className="dialog-form" onSubmit={handleSubmit}>
          <label>
            <span>Name</span>
            <input className="text-input" value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          <label>
            <span>Description</span>
            <textarea className="text-area" value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          {error ? <div className="dialog-error">{error}</div> : null}
          <button type="submit" className="btn btn-primary" disabled={saving || !name.trim()}>
            {saving ? 'Creating…' : 'Create workspace'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function ProjectsPage() {
  const navigate = useNavigate();
  const [workspaces, setWorkspaces] = useState([]);
  const [workspaceDetails, setWorkspaceDetails] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [phaseFilter, setPhaseFilter] = useState('ALL');
  const [showCreate, setShowCreate] = useState(false);

  const loadWorkspaces = async () => {
    setLoading(true);
    setError('');

    try {
      const workspaceList = await apiClient.getWorkspaces();
      setWorkspaces(workspaceList);

      const detailEntries = await Promise.all(
        workspaceList.map(async (workspace) => {
          const [artifacts, claims, critiques, ruleChecks, tasks] = await Promise.all([
            apiClient.getWorkspaceArtifacts(workspace.id).catch(() => []),
            apiClient.getWorkspaceClaims(workspace.id).catch(() => []),
            apiClient.getWorkspaceCritiques(workspace.id).catch(() => []),
            apiClient.getRuleChecks(workspace.id).catch(() => []),
            apiClient.getWorkspaceTasks(workspace.id).catch(() => []),
          ]);

          return [
            workspace.id,
            {
              artifactsCount: artifacts.length,
              claimsCount: claims.length,
              blockingCritiques: critiques.filter((critique) => critique.status === 'open' && critique.severity === 'blocking').length,
              failingRuleChecks: ruleChecks.filter((check) => check.status === 'fail').length,
              openTasks: tasks.filter((task) => task.status !== 'completed').length,
            },
          ];
        })
      );

      setWorkspaceDetails(Object.fromEntries(detailEntries));
    } catch (err) {
      setError(err.message || 'Failed to load workspaces');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadWorkspaces();
  }, []);

  const filteredWorkspaces = useMemo(() => {
    return workspaces.filter((workspace) => {
      if (phaseFilter !== 'ALL' && workspace.phase !== phaseFilter) return false;
      if (!search.trim()) return true;

      const haystack = `${workspace.name} ${workspace.description || ''}`.toLowerCase();
      return haystack.includes(search.trim().toLowerCase());
    });
  }, [phaseFilter, search, workspaces]);

  const totals = useMemo(() => {
    return workspaces.reduce(
      (acc, workspace) => {
        const detail = workspaceDetails[workspace.id] || {};
        acc.blockers += (detail.blockingCritiques || 0) + (detail.failingRuleChecks || 0);
        acc.activeTasks += detail.openTasks || 0;
        return acc;
      },
      { blockers: 0, activeTasks: 0 }
    );
  }, [workspaceDetails, workspaces]);

  return (
    <div className="projects-page">
      <section className="projects-hero">
        <div>
          <p className="projects-kicker">Workspace portfolio</p>
          <h2>See evidence, execution, and blockers across every research workspace.</h2>
          <p className="projects-summary">
            Review current phase, open tasks, critique pressure, and rule-check health before drilling into a specific workspace.
          </p>
        </div>
        <div className="projects-hero-actions">
          <button type="button" className="btn btn-secondary" onClick={loadWorkspaces}>
            Refresh
          </button>
          <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
            New workspace
          </button>
        </div>
      </section>

      <div className="projects-top-grid">
        <SectionCard eyebrow="Fleet state" title="Portfolio snapshot">
          <div className="metric-grid">
            <div className="metric-card">
              <span>Total workspaces</span>
              <strong>{workspaces.length}</strong>
            </div>
            <div className="metric-card">
              <span>Active blockers</span>
              <strong>{totals.blockers}</strong>
            </div>
            <div className="metric-card">
              <span>Open tasks</span>
              <strong>{totals.activeTasks}</strong>
            </div>
          </div>
        </SectionCard>

        <SectionCard eyebrow="Workspace finder" title="Filter and sort">
          <div className="projects-filter-grid">
            <input
              className="text-input"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search workspace name or description"
            />
            <select className="select-input" value={phaseFilter} onChange={(event) => setPhaseFilter(event.target.value)}>
              <option value="ALL">All phases</option>
              {PHASES.map((phase) => (
                <option key={phase} value={phase}>
                  {phase.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </div>
        </SectionCard>
      </div>

      {loading ? <div className="projects-empty">Loading workspaces…</div> : null}
      {error ? <div className="projects-error">{error}</div> : null}

      {!loading && !error ? (
        filteredWorkspaces.length > 0 ? (
          <div className="projects-grid">
            {filteredWorkspaces.map((workspace) => {
              const detail = workspaceDetails[workspace.id] || {};
              const health = scoreWorkspaceHealth(detail);

              return (
                <button
                  type="button"
                  key={workspace.id}
                  className="project-card"
                  onClick={() => navigate(`/projects/${workspace.id}/overview`)}
                >
                  <div className="project-card-top">
                    <div>
                      <p className="project-phase">{workspace.phase.replaceAll('_', ' ')}</p>
                      <h3>{workspace.name}</h3>
                    </div>
                    <span className={`pill status-${health.tone}`}>{health.label}</span>
                  </div>
                  <p className="project-description">{workspace.description || 'No description yet.'}</p>
                  <div className="project-metrics">
                    <span>{detail.artifactsCount || 0} artifacts</span>
                    <span>{detail.claimsCount || 0} claims</span>
                    <span>{detail.openTasks || 0} active tasks</span>
                  </div>
                  <div className="project-blockers">
                    <span>{detail.failingRuleChecks || 0} failing checks</span>
                    <span>{detail.blockingCritiques || 0} blocking critiques</span>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="projects-empty">No workspaces match the current filters.</div>
        )
      ) : null}

      <WorkspaceCreateDialog open={showCreate} onClose={() => setShowCreate(false)} onCreated={loadWorkspaces} />
    </div>
  );
}
