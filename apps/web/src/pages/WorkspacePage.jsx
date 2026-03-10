import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import apiClient from '../api/client';
import { SectionCard, TabNav } from '../components/Layout';
import ArtifactViewer from '../components/ArtifactViewer';
import EvidenceDrawer from '../components/EvidenceDrawer';
import './WorkspacePage.css';

const TAB_ORDER = [
  { id: 'overview', label: 'Overview' },
  { id: 'team', label: 'Team' },
  { id: 'requests', label: 'Requests' },
  { id: 'artifacts', label: 'Artifacts' },
  { id: 'claims', label: 'Claims' },
  { id: 'drafts', label: 'Drafts' },
  { id: 'tasks', label: 'Tasks' },
  { id: 'critiques', label: 'Critiques' },
  { id: 'rule-checks', label: 'Rule checks' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'search', label: 'Search' },
];

const CRITIQUE_SEVERITIES = ['info', 'minor', 'major', 'blocking'];
const CRITIQUE_STATUSES = ['open', 'resolved', 'deferred', 'rejected'];
const TASK_STATUSES = ['open', 'in_progress', 'blocked', 'completed'];
const ARTIFACT_TYPES = ['pdf', 'code', 'dataset', 'log', 'config'];

function humanize(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatTimestamp(value) {
  if (!value) return 'Unknown';
  return new Date(value).toLocaleString();
}

function toneForStatus(status) {
  const normalized = String(status || '').toLowerCase();
  if (['pass', 'passed', 'healthy', 'stable', 'resolved', 'completed'].includes(normalized)) return 'good';
  if (['fail', 'failed', 'blocking', 'rejected'].includes(normalized)) return 'danger';
  if (['warning', 'open', 'blocked', 'deferred', 'in_progress'].includes(normalized)) return 'warning';
  return 'info';
}

function JsonBlock({ value }) {
  if (!value) return null;
  return <pre className="console-json">{JSON.stringify(value, null, 2)}</pre>;
}

function EmptyState({ title, body }) {
  return (
    <div className="empty-block">
      <strong>{title}</strong>
      <span>{body}</span>
    </div>
  );
}

function StatusPill({ label, tone }) {
  return <span className={`pill status-${tone}`}>{label}</span>;
}

function DraftMarkdown({ content, onOpenEvidence }) {
  const citationRegex = /\[\[cite:([^|]+)\|([^\]]+)\]\]/g;
  const parts = [];
  let cursor = 0;
  let match;

  while ((match = citationRegex.exec(content || '')) !== null) {
    if (match.index > cursor) {
      parts.push({ type: 'markdown', value: content.slice(cursor, match.index) });
    }
    parts.push({ type: 'citation', artifactVersionId: match[1], location: match[2] });
    cursor = match.index + match[0].length;
  }

  if (cursor < (content || '').length) {
    parts.push({ type: 'markdown', value: content.slice(cursor) });
  }

  return (
    <div className="draft-markdown">
      {parts.map((part, index) =>
        part.type === 'citation' ? (
          <button
            key={`${part.artifactVersionId}-${index}`}
            type="button"
            className="cite-button"
            onClick={() => onOpenEvidence(part.artifactVersionId, part.location)}
          >
            Citation · {part.location}
          </button>
        ) : (
          <ReactMarkdown key={`m-${index}`}>{part.value}</ReactMarkdown>
        )
      )}
    </div>
  );
}

export default function WorkspacePage() {
  const { workspaceId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const activeTab = TAB_ORDER.find((tab) => location.pathname.endsWith(`/${tab.id}`))?.id || 'overview';

  const [consoleState, setConsoleState] = useState({
    agent: null,
    workspaceDetail: null,
    phaseStatus: null,
    gateStatus: null,
    roles: [],
    joinRequests: [],
    artifacts: [],
    versionsByArtifact: {},
    claims: [],
    critiques: [],
    tasks: [],
    logs: [],
    events: [],
    ruleChecks: [],
  });
  const [selectedArtifactId, setSelectedArtifactId] = useState(null);
  const [selectedDraftId, setSelectedDraftId] = useState(null);
  const [selectedDraftContent, setSelectedDraftContent] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingDraft, setLoadingDraft] = useState(false);
  const [error, setError] = useState('');
  const [banner, setBanner] = useState(null);
  const [evidenceDrawer, setEvidenceDrawer] = useState(null);
  const [provenanceViewer, setProvenanceViewer] = useState(null);

  const [workspaceDescription, setWorkspaceDescription] = useState('');
  const [joinRoleId, setJoinRoleId] = useState('');
  const [artifactForm, setArtifactForm] = useState({ type: 'pdf', title: '', notes: '' });
  const [artifactFile, setArtifactFile] = useState(null);
  const [claimForm, setClaimForm] = useState({ text: '', kind: 'fact', confidence: 'high' });
  const [claimEvidenceForm, setClaimEvidenceForm] = useState({ claimId: '', artifactVersionId: '', location: '' });
  const [draftForm, setDraftForm] = useState({ title: '', content: '' });
  const [draftVersionForm, setDraftVersionForm] = useState({ draftId: '', content: '' });
  const [repoRequestForm, setRepoRequestForm] = useState({ repo_url: '', branch: '', commit_hash: '' });
  const [pdfRequestArtifactId, setPdfRequestArtifactId] = useState('');
  const [sandboxForm, setSandboxForm] = useState({ script_artifact_id: '', parameters: '', image: 'python:3.11-slim' });
  const [ruleCheckDraftVersionId, setRuleCheckDraftVersionId] = useState('');
  const [critiqueForm, setCritiqueForm] = useState({ target_type: 'claim', target_id: '', target_location: '', severity: 'minor', message: '' });

  const loadWorkspaceConsole = async () => {
    setLoading(true);
    setError('');

    try {
      const [
        agent,
        workspaceDetail,
        phaseStatus,
        gateStatus,
        roles,
        artifacts,
        claims,
        critiques,
        tasks,
        logs,
        events,
        ruleChecks,
        joinRequests,
      ] = await Promise.all([
        apiClient.getCurrentAgent(),
        apiClient.getWorkspace(workspaceId),
        apiClient.getPhaseStatus(workspaceId).catch(() => null),
        apiClient.getGateStatus(workspaceId).catch(() => null),
        apiClient.getRoles().catch(() => []),
        apiClient.getWorkspaceArtifacts(workspaceId),
        apiClient.getWorkspaceClaims(workspaceId),
        apiClient.getWorkspaceCritiques(workspaceId),
        apiClient.getWorkspaceTasks(workspaceId),
        apiClient.getWorkspaceLogs(workspaceId),
        apiClient.getWorkspaceEvents(workspaceId),
        apiClient.getRuleChecks(workspaceId),
        apiClient.getWorkspaceJoinRequests(workspaceId).catch(() => []),
      ]);

      const versionEntries = await Promise.all(
        artifacts.map(async (artifact) => [artifact.id, await apiClient.getArtifactVersions(artifact.id).catch(() => [])])
      );
      const versionsByArtifact = Object.fromEntries(versionEntries);

      setConsoleState({
        agent,
        workspaceDetail,
        phaseStatus,
        gateStatus,
        roles,
        joinRequests,
        artifacts,
        versionsByArtifact,
        claims,
        critiques,
        tasks,
        logs,
        events,
        ruleChecks,
      });

      setWorkspaceDescription(workspaceDetail.workspace?.description || '');
      setJoinRoleId((current) => current || roles[0]?.id || '');
      setSelectedArtifactId((current) => current || artifacts[0]?.id || null);
      const drafts = artifacts.filter((artifact) => artifact.type === 'draft');
      setSelectedDraftId((current) => current || drafts[0]?.id || null);
      if (!ruleCheckDraftVersionId) {
        const latestDraftVersion = drafts
          .flatMap((draft) => versionsByArtifact[draft.id] || [])
          .sort((a, b) => b.version - a.version)[0];
        setRuleCheckDraftVersionId(latestDraftVersion?.id || '');
      }
      if (!pdfRequestArtifactId) {
        setPdfRequestArtifactId(artifacts.find((artifact) => artifact.type === 'pdf')?.id || '');
      }
      if (!sandboxForm.script_artifact_id) {
        setSandboxForm((current) => ({
          ...current,
          script_artifact_id: artifacts.find((artifact) => ['code', 'script'].includes(artifact.type))?.id || '',
        }));
      }
      if (!draftVersionForm.draftId) {
        setDraftVersionForm((current) => ({
          ...current,
          draftId: drafts[0]?.id || '',
        }));
      }
      if (!claimEvidenceForm.claimId) {
        setClaimEvidenceForm((current) => ({
          ...current,
          claimId: claims[0]?.id || '',
          artifactVersionId:
            current.artifactVersionId ||
            artifacts.flatMap((artifact) => versionsByArtifact[artifact.id] || [])[0]?.id ||
            '',
        }));
      }
      if (!critiqueForm.target_id) {
        setCritiqueForm((current) => ({
          ...current,
          target_id:
            current.target_id ||
            claims[0]?.id ||
            artifacts.flatMap((artifact) => versionsByArtifact[artifact.id] || [])[0]?.id ||
            '',
        }));
      }
    } catch (err) {
      setError(err.message || 'Failed to load workspace console');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadWorkspaceConsole();
  }, [workspaceId]);

  useEffect(() => {
    const loadDraftContent = async () => {
      if (!selectedDraftId) {
        setSelectedDraftContent('');
        return;
      }

      const versions = consoleState.versionsByArtifact[selectedDraftId] || [];
      const latestVersion = versions[0];
      if (!latestVersion) {
        setSelectedDraftContent('');
        return;
      }

      setLoadingDraft(true);
      try {
        const content = await apiClient.getArtifactVersionContent(latestVersion.id);
        setSelectedDraftContent(content.text || content.content || '');
      } catch (err) {
        setSelectedDraftContent(`Failed to load draft content: ${err.message}`);
      } finally {
        setLoadingDraft(false);
      }
    };

    void loadDraftContent();
  }, [consoleState.versionsByArtifact, selectedDraftId]);

  const workspace = consoleState.workspaceDetail?.workspace;
  const team = consoleState.workspaceDetail?.team || [];
  const currentAgentId = consoleState.agent?.agent_id;
  const isWorkspaceMember = team.some((member) => member.agent_id === currentAgentId && member.status === 'active');
  const canReviewJoinRequests = team.some(
    (member) => member.agent_id === currentAgentId && member.status === 'active' && member.role_name === 'Maintainer'
  );
  const artifacts = consoleState.artifacts;
  const drafts = artifacts.filter((artifact) => artifact.type === 'draft');
  const allArtifactVersions = artifacts.flatMap((artifact) =>
    (consoleState.versionsByArtifact[artifact.id] || []).map((version) => ({
      ...version,
      artifact,
      label: `${artifact.short_id} · ${humanize(artifact.type)} · v${version.version}`,
    }))
  );
  const selectedArtifact = artifacts.find((artifact) => artifact.id === selectedArtifactId) || null;
  const selectedDraft = drafts.find((draft) => draft.id === selectedDraftId) || null;

  const overviewMetrics = useMemo(() => {
    return {
      artifacts: artifacts.length,
      claims: consoleState.claims.length,
      critiques: consoleState.critiques.length,
      tasks: consoleState.tasks.filter((task) => task.status !== 'completed').length,
      blockers:
        consoleState.critiques.filter((critique) => critique.status === 'open' && critique.severity === 'blocking').length +
        consoleState.ruleChecks.filter((check) => check.status === 'fail').length,
    };
  }, [artifacts, consoleState.claims, consoleState.critiques, consoleState.ruleChecks, consoleState.tasks]);

  const timelineItems = useMemo(() => {
    return [
      ...consoleState.events.map((event) => ({ ...event, kind: 'event' })),
      ...consoleState.logs.map((log) => ({ ...log, kind: 'log' })),
    ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }, [consoleState.events, consoleState.logs]);

  const tabConfig = TAB_ORDER.map((tab) => {
    if (tab.id === 'artifacts') return { ...tab, count: artifacts.length };
    if (tab.id === 'claims') return { ...tab, count: consoleState.claims.length };
    if (tab.id === 'drafts') return { ...tab, count: drafts.length };
    if (tab.id === 'tasks') return { ...tab, count: consoleState.tasks.filter((task) => task.status !== 'completed').length };
    if (tab.id === 'critiques') return { ...tab, count: consoleState.critiques.filter((critique) => critique.status === 'open').length };
    if (tab.id === 'rule-checks') return { ...tab, count: consoleState.ruleChecks.length };
    return tab;
  });

  const flash = (message, tone = 'good') => {
    setBanner({ message, tone });
    window.setTimeout(() => {
      setBanner((current) => (current?.message === message ? null : current));
    }, 3200);
  };

  const runAction = async (operation, successMessage) => {
    try {
      await operation();
      flash(successMessage, 'good');
      await loadWorkspaceConsole();
    } catch (err) {
      flash(err.message || 'Action failed', 'danger');
    }
  };

  const openEvidence = (artifactVersionId, location) => {
    setEvidenceDrawer({ artifactVersionId, location });
  };

  const renderTab = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <div className="workspace-panel-grid">
            <SectionCard eyebrow="Workspace state" title="Operational summary">
              <div className="workspace-stat-grid">
                <MetricTile label="Artifacts" value={overviewMetrics.artifacts} />
                <MetricTile label="Claims" value={overviewMetrics.claims} />
                <MetricTile label="Open tasks" value={overviewMetrics.tasks} />
                <MetricTile label="Blockers" value={overviewMetrics.blockers} tone={overviewMetrics.blockers > 0 ? 'danger' : 'good'} />
              </div>
            </SectionCard>

            <SectionCard eyebrow="Authority boundaries" title="Phase and gate readiness" tone={consoleState.gateStatus?.can_advance ? 'success' : 'warning'}>
              <div className="stack">
                <div className="workspace-inline-row">
                  <StatusPill label={`Current phase · ${humanize(workspace?.phase)}`} tone="info" />
                  {consoleState.gateStatus?.gate_required ? (
                    <StatusPill
                      label={`Gate ${consoleState.gateStatus.gate_status || 'unknown'}`}
                      tone={consoleState.gateStatus.can_advance ? 'good' : 'warning'}
                    />
                  ) : (
                    <StatusPill label="No gate required" tone="good" />
                  )}
                </div>
                {consoleState.phaseStatus ? (
                  <div className="hint-block">
                    <strong>Allowed next phases</strong>
                    <span>{consoleState.phaseStatus.allowed_next_phases?.map(humanize).join(', ') || 'None'}</span>
                  </div>
                ) : null}
                {consoleState.gateStatus?.reasons?.length ? (
                  <ul className="bullet-list">
                    {consoleState.gateStatus.reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                ) : null}
                {consoleState.gateStatus?.required_actions?.length ? (
                  <>
                    <strong>Required actions</strong>
                    <ul className="bullet-list">
                      {consoleState.gateStatus.required_actions.map((action) => (
                        <li key={action}>{action}</li>
                      ))}
                    </ul>
                  </>
                ) : null}
              </div>
            </SectionCard>

            <SectionCard eyebrow="Workspace settings" title="Update description">
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runAction(() => apiClient.updateWorkspace(workspaceId, workspaceDescription), 'Workspace description updated');
                }}
              >
                <textarea
                  className="text-area"
                  value={workspaceDescription}
                  onChange={(event) => setWorkspaceDescription(event.target.value)}
                />
                <button type="submit" className="btn btn-primary">
                  Save description
                </button>
              </form>
            </SectionCard>

            <SectionCard eyebrow="Recent activity" title="Latest events and logs">
              {timelineItems.length ? (
                <div className="stack">
                  {timelineItems.slice(0, 6).map((item) => (
                    <div key={`${item.kind}-${item.id}`} className="timeline-card">
                      <div className="workspace-inline-row">
                        <StatusPill label={humanize(item.kind === 'event' ? item.event_type : item.action || item.level || 'log')} tone={toneForStatus(item.level || item.event_type)} />
                        <span>{formatTimestamp(item.created_at)}</span>
                      </div>
                      <div>{item.kind === 'event' ? item.event_type : item.message || item.action}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No activity yet" body="Events and logs will appear here as work advances." />
              )}
            </SectionCard>
          </div>
        );
      case 'team':
        return (
          <div className="workspace-panel-grid">
            <SectionCard eyebrow="Workspace roster" title="Current team">
              {team.length ? (
                <div className="stack">
                  {team.map((member) => (
                    <div key={member.agent_id} className="list-card">
                      <div className="workspace-inline-row">
                        <strong>{member.role_name}</strong>
                        <StatusPill label={member.status} tone={toneForStatus(member.status)} />
                      </div>
                      <span>Agent {member.agent_id}</span>
                      <span>Joined {formatTimestamp(member.joined_at)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No team roster" body="Members will appear once join requests are approved." />
              )}
            </SectionCard>

            <SectionCard eyebrow="Join workflow" title="Request a role">
              {isWorkspaceMember ? (
                <EmptyState
                  title="Already an active member"
                  body="Join requests are only needed from a non-member session. Use another account to test role application flows."
                />
              ) : (
                <form
                  className="stack"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void runAction(() => apiClient.createJoinRequest(workspaceId, joinRoleId), 'Join request submitted');
                  }}
                >
                  <select className="select-input" value={joinRoleId} onChange={(event) => setJoinRoleId(event.target.value)}>
                    {consoleState.roles.map((role) => (
                      <option key={role.id} value={role.id}>
                        {role.name} · min reputation {role.min_reputation ?? 0}
                      </option>
                    ))}
                  </select>
                  <button type="submit" className="btn btn-primary" disabled={!joinRoleId}>
                    Submit join request
                  </button>
                </form>
              )}
            </SectionCard>

            <SectionCard eyebrow="Join workflow" title="Pending and reviewed requests">
              {consoleState.joinRequests.length ? (
                <div className="stack">
                  {consoleState.joinRequests.map((request) => (
                    <div key={request.id} className="list-card">
                      <div className="workspace-inline-row">
                        <strong>{request.role_name || request.role_id}</strong>
                        <StatusPill label={request.status} tone={toneForStatus(request.status)} />
                      </div>
                      <span>Agent {request.agent_id}</span>
                      <span>Requested {formatTimestamp(request.requested_at)}</span>
                      {request.status === 'pending' && canReviewJoinRequests ? (
                        <div className="workspace-inline-row">
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => void runAction(() => apiClient.reviewJoinRequest(workspaceId, request.id, true, 'Approved from console'), 'Join request approved')}
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger"
                            onClick={() => void runAction(() => apiClient.reviewJoinRequest(workspaceId, request.id, false, 'Rejected from console'), 'Join request rejected')}
                          >
                            Reject
                          </button>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No join requests yet" body="Join requests created through the console will appear here." />
              )}
            </SectionCard>
          </div>
        );
      case 'requests':
        return (
          <div className="workspace-panel-grid">
            <SectionCard eyebrow="Ingestion" title="Request PDF ingestion">
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runAction(() => apiClient.requestIngestPdf(workspaceId, pdfRequestArtifactId), 'PDF ingestion requested');
                }}
              >
                <select className="select-input" value={pdfRequestArtifactId} onChange={(event) => setPdfRequestArtifactId(event.target.value)}>
                  <option value="">Select PDF artifact</option>
                  {artifacts.filter((artifact) => artifact.type === 'pdf').map((artifact) => (
                    <option key={artifact.id} value={artifact.id}>
                      {artifact.short_id} · {artifact.metadata?.title || 'Untitled PDF'}
                    </option>
                  ))}
                </select>
                <button type="submit" className="btn btn-primary" disabled={!pdfRequestArtifactId}>
                  Request PDF ingest
                </button>
              </form>
            </SectionCard>

            <SectionCard eyebrow="Ingestion" title="Request repository ingest">
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runAction(() => apiClient.requestIngestRepo(workspaceId, repoRequestForm), 'Repository ingest requested');
                }}
              >
                <input className="text-input" placeholder="Repository URL" value={repoRequestForm.repo_url} onChange={(event) => setRepoRequestForm((current) => ({ ...current, repo_url: event.target.value }))} />
                <div className="workspace-inline-row">
                  <input className="text-input" placeholder="Branch (optional)" value={repoRequestForm.branch} onChange={(event) => setRepoRequestForm((current) => ({ ...current, branch: event.target.value }))} />
                  <input className="text-input" placeholder="Commit hash (optional)" value={repoRequestForm.commit_hash} onChange={(event) => setRepoRequestForm((current) => ({ ...current, commit_hash: event.target.value }))} />
                </div>
                <button type="submit" className="btn btn-primary" disabled={!repoRequestForm.repo_url.trim()}>
                  Request repo ingest
                </button>
              </form>
            </SectionCard>

            <SectionCard eyebrow="Execution" title="Run sandbox">
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  const payload = {
                    script_artifact_id: sandboxForm.script_artifact_id,
                    image: sandboxForm.image,
                    parameters: sandboxForm.parameters ? JSON.parse(sandboxForm.parameters) : undefined,
                  };
                  void runAction(() => apiClient.requestRunSandbox(workspaceId, payload), 'Sandbox run requested');
                }}
              >
                <select className="select-input" value={sandboxForm.script_artifact_id} onChange={(event) => setSandboxForm((current) => ({ ...current, script_artifact_id: event.target.value }))}>
                  <option value="">Select executable artifact</option>
                  {artifacts.filter((artifact) => ['code', 'script'].includes(artifact.type)).map((artifact) => (
                    <option key={artifact.id} value={artifact.id}>
                      {artifact.short_id} · {artifact.metadata?.title || artifact.type}
                    </option>
                  ))}
                </select>
                <input className="text-input" placeholder="Container image" value={sandboxForm.image} onChange={(event) => setSandboxForm((current) => ({ ...current, image: event.target.value }))} />
                <textarea className="text-area" placeholder='Parameters JSON, e.g. {"args":["--help"]}' value={sandboxForm.parameters} onChange={(event) => setSandboxForm((current) => ({ ...current, parameters: event.target.value }))} />
                <button type="submit" className="btn btn-primary" disabled={!sandboxForm.script_artifact_id}>
                  Run sandbox
                </button>
              </form>
            </SectionCard>

            <SectionCard eyebrow="Governance" title="Run rule check">
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runAction(() => apiClient.runRuleCheck(workspaceId, ruleCheckDraftVersionId), 'Rule check requested');
                }}
              >
                <select className="select-input" value={ruleCheckDraftVersionId} onChange={(event) => setRuleCheckDraftVersionId(event.target.value)}>
                  <option value="">Select draft version</option>
                  {drafts.flatMap((draft) =>
                    (consoleState.versionsByArtifact[draft.id] || []).map((version) => (
                      <option key={version.id} value={version.id}>
                        {draft.short_id} · v{version.version}
                      </option>
                    ))
                  )}
                </select>
                <button type="submit" className="btn btn-primary" disabled={!ruleCheckDraftVersionId}>
                  Run rule check
                </button>
              </form>
            </SectionCard>
          </div>
        );
      case 'artifacts':
        return (
          <div className="workspace-panel-grid">
            <SectionCard eyebrow="Registry" title="Create artifact record">
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runAction(
                    async () => {
                      const artifact = await apiClient.createArtifact(workspaceId, artifactForm.type, {
                        title: artifactForm.title,
                        notes: artifactForm.notes,
                      });
                      setArtifactForm({ type: 'pdf', title: '', notes: '' });
                      setSelectedArtifactId(artifact.id);
                    },
                    'Artifact created'
                  );
                }}
              >
                <select className="select-input" value={artifactForm.type} onChange={(event) => setArtifactForm((current) => ({ ...current, type: event.target.value }))}>
                  {ARTIFACT_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {humanize(type)}
                    </option>
                  ))}
                </select>
                <input className="text-input" placeholder="Title" value={artifactForm.title} onChange={(event) => setArtifactForm((current) => ({ ...current, title: event.target.value }))} />
                <textarea className="text-area" placeholder="Metadata notes" value={artifactForm.notes} onChange={(event) => setArtifactForm((current) => ({ ...current, notes: event.target.value }))} />
                <button type="submit" className="btn btn-primary" disabled={!artifactForm.title.trim()}>
                  Create artifact
                </button>
              </form>
            </SectionCard>

            <SectionCard eyebrow="Registry" title="Upload new version">
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (!selectedArtifactId || !artifactFile) return;
                  void runAction(() => apiClient.createArtifactVersion(selectedArtifactId, artifactFile), 'Artifact version uploaded');
                }}
              >
                <select className="select-input" value={selectedArtifactId || ''} onChange={(event) => setSelectedArtifactId(event.target.value)}>
                  <option value="">Select artifact</option>
                  {artifacts.map((artifact) => (
                    <option key={artifact.id} value={artifact.id}>
                      {artifact.short_id} · {artifact.metadata?.title || humanize(artifact.type)}
                    </option>
                  ))}
                </select>
                <input type="file" className="field" onChange={(event) => setArtifactFile(event.target.files?.[0] || null)} />
                <button type="submit" className="btn btn-primary" disabled={!selectedArtifactId || !artifactFile}>
                  Upload version
                </button>
              </form>
            </SectionCard>

            <SectionCard eyebrow="Registry" title="Artifact viewer">
              {artifacts.length ? (
                <div className="artifact-console-layout">
                  <div className="artifact-console-list">
                    {artifacts.map((artifact) => (
                      <button
                        type="button"
                        key={artifact.id}
                        className={`artifact-summary-card ${artifact.id === selectedArtifactId ? 'active' : ''}`}
                        onClick={() => setSelectedArtifactId(artifact.id)}
                      >
                        <strong>{artifact.short_id}</strong>
                        <span>{humanize(artifact.type)}</span>
                        <small>{artifact.metadata?.title || 'Untitled artifact'}</small>
                      </button>
                    ))}
                  </div>
                  <div className="artifact-console-viewer">
                    {selectedArtifact ? (
                      <ArtifactViewer artifactId={selectedArtifact.id} />
                    ) : (
                      <EmptyState title="No artifact selected" body="Select an artifact to inspect versions and processed content." />
                    )}
                  </div>
                </div>
              ) : (
                <EmptyState title="No artifacts yet" body="Create an artifact record, then upload a version to start using the workspace." />
              )}
            </SectionCard>
          </div>
        );
      case 'claims':
        return (
          <div className="workspace-panel-grid">
            <SectionCard eyebrow="Grounding" title="Create claim">
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runAction(
                    async () => {
                      await apiClient.createClaim(workspaceId, claimForm);
                      setClaimForm({ text: '', kind: 'fact', confidence: 'high' });
                    },
                    'Claim created'
                  );
                }}
              >
                <select className="select-input" value={claimForm.kind} onChange={(event) => setClaimForm((current) => ({ ...current, kind: event.target.value }))}>
                  <option value="fact">Fact</option>
                  <option value="hypothesis">Hypothesis</option>
                  <option value="conclusion">Conclusion</option>
                </select>
                <select className="select-input" value={claimForm.confidence} onChange={(event) => setClaimForm((current) => ({ ...current, confidence: event.target.value }))}>
                  <option value="high">High confidence</option>
                  <option value="medium">Medium confidence</option>
                  <option value="low">Low confidence</option>
                </select>
                <textarea className="text-area" value={claimForm.text} onChange={(event) => setClaimForm((current) => ({ ...current, text: event.target.value }))} placeholder="State the claim in one grounded sentence" />
                <button type="submit" className="btn btn-primary" disabled={!claimForm.text.trim()}>
                  Create claim
                </button>
              </form>
            </SectionCard>

            <SectionCard eyebrow="Grounding" title="Attach evidence pointer">
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runAction(
                    () => apiClient.addEvidenceToClaim(claimEvidenceForm.claimId, {
                      artifact_version_id: claimEvidenceForm.artifactVersionId,
                      location: claimEvidenceForm.location,
                    }),
                    'Evidence added to claim'
                  );
                }}
              >
                <select className="select-input" value={claimEvidenceForm.claimId} onChange={(event) => setClaimEvidenceForm((current) => ({ ...current, claimId: event.target.value }))}>
                  <option value="">Select claim</option>
                  {consoleState.claims.map((claim) => (
                    <option key={claim.id} value={claim.id}>
                      {claim.text.slice(0, 64)}
                    </option>
                  ))}
                </select>
                <select className="select-input" value={claimEvidenceForm.artifactVersionId} onChange={(event) => setClaimEvidenceForm((current) => ({ ...current, artifactVersionId: event.target.value }))}>
                  <option value="">Select artifact version</option>
                  {allArtifactVersions.map((version) => (
                    <option key={version.id} value={version.id}>
                      {version.label}
                    </option>
                  ))}
                </select>
                <input className="text-input" placeholder="Location pointer, e.g. pdf:p=1#char=0-10" value={claimEvidenceForm.location} onChange={(event) => setClaimEvidenceForm((current) => ({ ...current, location: event.target.value }))} />
                <button type="submit" className="btn btn-primary" disabled={!claimEvidenceForm.claimId || !claimEvidenceForm.artifactVersionId || !claimEvidenceForm.location.trim()}>
                  Add evidence
                </button>
              </form>
            </SectionCard>

            <SectionCard eyebrow="Grounding" title="Claims registry">
              {consoleState.claims.length ? (
                <div className="stack">
                  {consoleState.claims.map((claim) => (
                    <div key={claim.id} className="list-card">
                      <div className="workspace-inline-row">
                        <div>
                          <strong>{claim.text}</strong>
                          <div className="metadata-row">
                            <span>{humanize(claim.kind)}</span>
                            <span>{humanize(claim.confidence)}</span>
                          </div>
                        </div>
                        <StatusPill label={claim.status} tone={toneForStatus(claim.status)} />
                      </div>
                      {claim.evidence?.length ? (
                        <div className="workspace-inline-row wrap">
                          {claim.evidence.map((evidence) => (
                            <button
                              type="button"
                              key={evidence.id}
                              className="btn btn-ghost"
                              onClick={() => openEvidence(evidence.artifact_version_id, evidence.location)}
                            >
                              {evidence.location}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <span className="muted-copy">No evidence pointers attached yet.</span>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No claims yet" body="Create a claim, then attach evidence pointers to ground it." />
              )}
            </SectionCard>
          </div>
        );
      case 'drafts':
        return (
          <div className="workspace-panel-grid">
            <SectionCard eyebrow="Draft lifecycle" title="Create draft">
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runAction(
                    async () => {
                      const draft = await apiClient.createDraft(workspaceId, draftForm.title);
                      if (draftForm.content.trim()) {
                        await apiClient.createDraftVersion(draft.id, draftForm.content);
                      }
                      setDraftForm({ title: '', content: '' });
                      setSelectedDraftId(draft.id);
                    },
                    'Draft created'
                  );
                }}
              >
                <input className="text-input" placeholder="Draft title" value={draftForm.title} onChange={(event) => setDraftForm((current) => ({ ...current, title: event.target.value }))} />
                <textarea className="text-area" placeholder="Initial markdown (optional)" value={draftForm.content} onChange={(event) => setDraftForm((current) => ({ ...current, content: event.target.value }))} />
                <button type="submit" className="btn btn-primary" disabled={!draftForm.title.trim()}>
                  Create draft
                </button>
              </form>
            </SectionCard>

            <SectionCard eyebrow="Draft lifecycle" title="Create new draft version">
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runAction(
                    () => apiClient.createDraftVersion(draftVersionForm.draftId, draftVersionForm.content),
                    'Draft version created'
                  );
                }}
              >
                <select className="select-input" value={draftVersionForm.draftId} onChange={(event) => setDraftVersionForm((current) => ({ ...current, draftId: event.target.value }))}>
                  <option value="">Select draft</option>
                  {drafts.map((draft) => (
                    <option key={draft.id} value={draft.id}>
                      {draft.short_id} · {draft.metadata?.title || 'Draft'}
                    </option>
                  ))}
                </select>
                <textarea className="text-area" placeholder="Markdown content" value={draftVersionForm.content} onChange={(event) => setDraftVersionForm((current) => ({ ...current, content: event.target.value }))} />
                <button type="submit" className="btn btn-primary" disabled={!draftVersionForm.draftId || !draftVersionForm.content.trim()}>
                  Create version
                </button>
              </form>
            </SectionCard>

            <SectionCard eyebrow="Draft lifecycle" title="Draft reader">
              {drafts.length ? (
                <div className="artifact-console-layout">
                  <div className="artifact-console-list">
                    {drafts.map((draft) => (
                      <button
                        type="button"
                        key={draft.id}
                        className={`artifact-summary-card ${draft.id === selectedDraftId ? 'active' : ''}`}
                        onClick={() => setSelectedDraftId(draft.id)}
                      >
                        <strong>{draft.short_id}</strong>
                        <span>{draft.metadata?.title || 'Draft'}</span>
                        <small>{(consoleState.versionsByArtifact[draft.id] || []).length} versions</small>
                      </button>
                    ))}
                  </div>
                  <div className="draft-reader-pane">
                    {loadingDraft ? <EmptyState title="Loading draft" body="Fetching latest markdown version." /> : null}
                    {!loadingDraft && selectedDraft ? (
                      <>
                        <div className="workspace-inline-row">
                          <strong>{selectedDraft.metadata?.title || selectedDraft.short_id}</strong>
                          <StatusPill
                            label={`Latest version · v${(consoleState.versionsByArtifact[selectedDraft.id] || [])[0]?.version || 0}`}
                            tone="info"
                          />
                        </div>
                        <DraftMarkdown content={selectedDraftContent} onOpenEvidence={openEvidence} />
                      </>
                    ) : null}
                  </div>
                </div>
              ) : (
                <EmptyState title="No drafts yet" body="Create a draft to start collecting markdown revisions and citations." />
              )}
            </SectionCard>
          </div>
        );
      case 'tasks':
        return (
          <SectionCard eyebrow="Task execution" title="Assigned tasks">
            {consoleState.tasks.length ? (
              <div className="stack">
                  {consoleState.tasks.map((task) => (
                    <TaskCard
                      key={task.id}
                      task={task}
                      currentAgentId={currentAgentId}
                      onUpdate={(payload) => runAction(() => apiClient.updateTask(task.id, payload), 'Task updated')}
                    />
                  ))}
              </div>
            ) : (
              <EmptyState title="No tasks assigned" body="Tasks created by ingestion workflows or maintainers will appear here." />
            )}
          </SectionCard>
        );
      case 'critiques':
        return (
          <div className="workspace-panel-grid">
            <SectionCard eyebrow="Review" title="Create critique">
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runAction(() => apiClient.createCritique(workspaceId, critiqueForm), 'Critique created');
                }}
              >
                <select className="select-input" value={critiqueForm.target_type} onChange={(event) => setCritiqueForm((current) => ({ ...current, target_type: event.target.value }))}>
                  <option value="claim">Claim</option>
                  <option value="artifact_version">Artifact version</option>
                </select>
                <select className="select-input" value={critiqueForm.target_id} onChange={(event) => setCritiqueForm((current) => ({ ...current, target_id: event.target.value }))}>
                  <option value="">Select target</option>
                  {(critiqueForm.target_type === 'claim' ? consoleState.claims : allArtifactVersions).map((target) => (
                    <option key={target.id} value={target.id}>
                      {'text' in target ? target.text.slice(0, 64) : target.label}
                    </option>
                  ))}
                </select>
                <input className="text-input" placeholder="Target location (optional)" value={critiqueForm.target_location} onChange={(event) => setCritiqueForm((current) => ({ ...current, target_location: event.target.value }))} />
                <select className="select-input" value={critiqueForm.severity} onChange={(event) => setCritiqueForm((current) => ({ ...current, severity: event.target.value }))}>
                  {CRITIQUE_SEVERITIES.map((severity) => (
                    <option key={severity} value={severity}>
                      {humanize(severity)}
                    </option>
                  ))}
                </select>
                <textarea className="text-area" value={critiqueForm.message} onChange={(event) => setCritiqueForm((current) => ({ ...current, message: event.target.value }))} placeholder="Describe the issue, request, or review finding" />
                <button type="submit" className="btn btn-primary" disabled={!critiqueForm.target_id || !critiqueForm.message.trim()}>
                  Create critique
                </button>
              </form>
            </SectionCard>

            <SectionCard eyebrow="Review" title="Critique ledger">
              {consoleState.critiques.length ? (
                <div className="stack">
                  {consoleState.critiques.map((critique) => (
                    <CritiqueCard key={critique.id} critique={critique} onUpdate={(payload) => runAction(() => apiClient.updateCritique(critique.id, payload), 'Critique updated')} />
                  ))}
                </div>
              ) : (
                <EmptyState title="No critiques yet" body="Create critiques against claims or artifact versions to capture review pressure." />
              )}
            </SectionCard>
          </div>
        );
      case 'rule-checks':
        return (
          <SectionCard eyebrow="Governance" title="Rule-check ledger">
            {consoleState.ruleChecks.length ? (
              <div className="stack">
                {consoleState.ruleChecks.map((check, index) => (
                  <div key={`${check.rule_name}-${index}`} className="list-card">
                    <div className="workspace-inline-row">
                      <strong>{check.rule_name}</strong>
                      <StatusPill label={check.status} tone={toneForStatus(check.status)} />
                    </div>
                    <div className="metadata-row">
                      <span>{humanize(check.target_type)}</span>
                      <span>{formatTimestamp(check.created_at)}</span>
                    </div>
                    <JsonBlock value={check.details} />
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No rule checks yet" body="Run a rule check from the requests tab or create a new draft version to generate coverage checks." />
            )}
          </SectionCard>
        );
      case 'timeline':
        return (
          <SectionCard eyebrow="Audit trail" title="Events and logs">
            {timelineItems.length ? (
              <div className="stack">
                {timelineItems.map((item) => (
                  <div key={`${item.kind}-${item.id}`} className="timeline-card">
                    <div className="workspace-inline-row">
                      <StatusPill label={item.kind === 'event' ? item.event_type : item.action || item.level || 'log'} tone={toneForStatus(item.level || item.event_type)} />
                      <span>{formatTimestamp(item.created_at)}</span>
                    </div>
                    <div>{item.kind === 'event' ? item.event_type : item.message || item.action}</div>
                    <JsonBlock value={item.payload} />
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No timeline entries" body="Events and logs will appear here as the workspace changes." />
            )}
          </SectionCard>
        );
      case 'search':
        return (
          <div className="workspace-panel-grid">
            <SectionCard eyebrow="Search index" title="Search artifact content">
              <form
                className="stack"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (!searchQuery.trim()) return;
                  void (async () => {
                    try {
                      const response = await apiClient.search(searchQuery.trim(), workspaceId);
                      setSearchResults(response);
                    } catch (err) {
                      flash(err.message || 'Search failed', 'danger');
                    }
                  })();
                }}
              >
                <input className="text-input" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search PDF text, repo content, logs, and more" />
                <button type="submit" className="btn btn-primary" disabled={!searchQuery.trim()}>
                  Search workspace
                </button>
              </form>
            </SectionCard>

            <SectionCard eyebrow="Search index" title="Results">
              {searchResults?.hits?.length ? (
                <div className="stack">
                  {searchResults.hits.map((hit) => (
                    <div key={`${hit.artifact_version_id}-${hit.relevance_rank}`} className="list-card">
                      <div className="workspace-inline-row">
                        <strong>{humanize(hit.artifact_type)}</strong>
                        <StatusPill label={`Rank ${hit.relevance_rank.toFixed(2)}`} tone="info" />
                      </div>
                      <p>{hit.snippet}</p>
                      <div className="workspace-inline-row wrap">
                        <button type="button" className="btn btn-ghost" onClick={() => setProvenanceViewer({ artifactId: hit.artifact_id, versionId: hit.artifact_version_id })}>
                          Open artifact version
                        </button>
                      </div>
                      <JsonBlock value={hit.metadata} />
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No results yet" body="Run a workspace search to inspect indexed snippets and provenance targets." />
              )}
            </SectionCard>
          </div>
        );
      default:
        return <EmptyState title="Tab unavailable" body="Select another workspace tab." />;
    }
  };

  if (loading) {
    return <div className="workspace-empty">Loading workspace console…</div>;
  }

  if (error || !workspace) {
    return <div className="workspace-error">{error || 'Workspace not found'}</div>;
  }

  return (
    <div className="workspace-page">
      <section className="workspace-hero">
        <div>
          <div className="workspace-inline-row wrap">
            <p className="workspace-kicker">Workspace console</p>
            <StatusPill label={humanize(workspace.phase)} tone="info" />
            <StatusPill
              label={consoleState.gateStatus?.gate_required ? `Gate ${consoleState.gateStatus.gate_status || 'unknown'}` : 'No gate'}
              tone={consoleState.gateStatus?.can_advance ? 'good' : consoleState.gateStatus?.gate_required ? 'warning' : 'info'}
            />
          </div>
          <h2>{workspace.name}</h2>
          <p>{workspace.description || 'No workspace description yet.'}</p>
        </div>
        <div className="workspace-hero-metrics">
          <MetricTile label="Artifacts" value={overviewMetrics.artifacts} />
          <MetricTile label="Claims" value={overviewMetrics.claims} />
          <MetricTile label="Blockers" value={overviewMetrics.blockers} tone={overviewMetrics.blockers > 0 ? 'danger' : 'good'} />
        </div>
      </section>

      {banner ? <div className={`workspace-banner workspace-banner-${banner.tone}`}>{banner.message}</div> : null}

      <div className="workspace-layout">
        <aside className="workspace-sidebar">
          <SectionCard eyebrow="Navigation" title="Workspace areas">
            <TabNav tabs={tabConfig} activeTab={activeTab} onTabChange={(tabId) => navigate(`/projects/${workspaceId}/${tabId}`)} />
          </SectionCard>

          <SectionCard eyebrow="Summary" title="Current operator context">
            <div className="stack">
              <div className="sidebar-stat-row">
                <span>Team members</span>
                <strong>{team.length}</strong>
              </div>
              <div className="sidebar-stat-row">
                <span>Join requests</span>
                <strong>{consoleState.joinRequests.length}</strong>
              </div>
              <div className="sidebar-stat-row">
                <span>Open critiques</span>
                <strong>{consoleState.critiques.filter((critique) => critique.status === 'open').length}</strong>
              </div>
              <div className="sidebar-stat-row">
                <span>Latest activity</span>
                <strong>{timelineItems[0] ? formatTimestamp(timelineItems[0].created_at) : 'None yet'}</strong>
              </div>
            </div>
          </SectionCard>
        </aside>

        <div className="workspace-main">{renderTab()}</div>
      </div>

      {evidenceDrawer ? (
        <EvidenceDrawer
          artifactVersionId={evidenceDrawer.artifactVersionId}
          location={evidenceDrawer.location}
          onClose={() => setEvidenceDrawer(null)}
          onOpenArtifactVersion={(target) => {
            setEvidenceDrawer(null);
            setProvenanceViewer(target);
          }}
        />
      ) : null}

      {provenanceViewer ? (
        <div className="provenance-modal">
          <div className="provenance-card">
            <div className="workspace-inline-row">
              <h3>Artifact provenance</h3>
              <button type="button" className="btn btn-secondary" onClick={() => setProvenanceViewer(null)}>
                Close
              </button>
            </div>
            <ArtifactViewer artifactId={provenanceViewer.artifactId} versionId={provenanceViewer.versionId} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function MetricTile({ label, value, tone = 'info' }) {
  return (
    <div className={`metric-panel metric-panel-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function CritiqueCard({ critique, onUpdate }) {
  const [status, setStatus] = useState(critique.status);
  const [resolutionStatus, setResolutionStatus] = useState('accepted_fix');
  const [rationale, setRationale] = useState('');

  return (
    <div className="list-card">
      <div className="workspace-inline-row">
        <div>
          <strong>{humanize(critique.target_type)}</strong>
          <div className="metadata-row">
            <span>{critique.target_id}</span>
            <span>{formatTimestamp(critique.created_at)}</span>
          </div>
        </div>
        <div className="workspace-inline-row">
          <StatusPill label={critique.severity} tone={toneForStatus(critique.severity)} />
          <StatusPill label={critique.status} tone={toneForStatus(critique.status)} />
        </div>
      </div>
      <p>{critique.message}</p>
      <div className="stack">
        <select className="select-input" value={status} onChange={(event) => setStatus(event.target.value)}>
          {CRITIQUE_STATUSES.map((item) => (
            <option key={item} value={item}>
              {humanize(item)}
            </option>
          ))}
        </select>
        <select className="select-input" value={resolutionStatus} onChange={(event) => setResolutionStatus(event.target.value)}>
          <option value="accepted_fix">Accepted fix</option>
          <option value="deferred_with_rationale">Deferred with rationale</option>
          <option value="rejected_with_evidence">Rejected with evidence</option>
        </select>
        <textarea className="text-area" value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Resolution rationale" />
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() =>
            onUpdate({
              status,
              resolution: rationale.trim()
                ? {
                    status: resolutionStatus,
                    rationale,
                  }
                : undefined,
            })
          }
        >
          Update critique
        </button>
      </div>
      {critique.resolution ? <JsonBlock value={critique.resolution} /> : null}
    </div>
  );
}

function TaskCard({ task, currentAgentId, onUpdate }) {
  const [status, setStatus] = useState(task.status);
  const [notes, setNotes] = useState(task.payload?.notes || '');
  const [resultType, setResultType] = useState('artifact');
  const [resultId, setResultId] = useState('');
  const isAssignee = task.assignee_agent_id === currentAgentId;

  return (
    <div className="list-card">
      <div className="workspace-inline-row">
        <div>
          <strong>{task.type}</strong>
          <div className="metadata-row">
            <span>Assignee {task.assignee_agent_id || 'Unassigned'}</span>
            <span>{formatTimestamp(task.created_at)}</span>
          </div>
        </div>
        <StatusPill label={task.status} tone={toneForStatus(task.status)} />
      </div>
      <JsonBlock value={task.payload} />
      {isAssignee ? (
        <div className="stack">
          <select className="select-input" value={status} onChange={(event) => setStatus(event.target.value)}>
            {TASK_STATUSES.map((taskStatus) => (
              <option key={taskStatus} value={taskStatus}>
                {humanize(taskStatus)}
              </option>
            ))}
          </select>
          <textarea className="text-area" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Notes or blockers" />
          <div className="workspace-inline-row">
            <select className="select-input" value={resultType} onChange={(event) => setResultType(event.target.value)}>
              <option value="artifact">Artifact</option>
              <option value="claim">Claim</option>
              <option value="draft">Draft</option>
              <option value="critique">Critique</option>
              <option value="log">Log</option>
            </select>
            <input className="text-input" placeholder="Result item id (optional)" value={resultId} onChange={(event) => setResultId(event.target.value)} />
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() =>
              onUpdate({
                status,
                notes,
                result_links: resultId.trim()
                  ? [
                      {
                        type: resultType,
                        id: resultId.trim(),
                      },
                    ]
                  : undefined,
              })
            }
          >
            Update task
          </button>
        </div>
      ) : (
        <span className="muted-copy">Only explicitly assigned tasks can be updated from the browser console; role-targeted tasks remain read-only here.</span>
      )}
    </div>
  );
}
