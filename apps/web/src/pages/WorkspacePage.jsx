import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import apiClient from '../api/client';
import ArtifactViewer from '../components/ArtifactViewer';
import EvidenceDrawer from '../components/EvidenceDrawer';
import { AppShell, SectionCard, TabNav, useShellFrame } from '../components/Layout';
import OverviewTab from '../features/workspace/OverviewTab';
import TeamTab from '../features/workspace/TeamTab';
import RequestsTab from '../features/workspace/RequestsTab';
import ArtifactsTab from '../features/workspace/ArtifactsTab';
import ClaimsTab from '../features/workspace/ClaimsTab';
import DraftsTab from '../features/workspace/DraftsTab';
import TasksTab from '../features/workspace/TasksTab';
import CritiquesTab from '../features/workspace/CritiquesTab';
import RuleChecksTab from '../features/workspace/RuleChecksTab';
import TimelineTab from '../features/workspace/TimelineTab';
import SearchTab from '../features/workspace/SearchTab';
import { TAB_ORDER } from '../features/workspace/constants';
import { EmptyState, MetricTile, StatusPill, formatTimestamp, humanize, toneForStatus } from '../features/workspace/shared';
import './WorkspacePage.css';

function buildTabCounts({ artifacts, claims, critiques, drafts, tasks, ruleChecks }) {
  return TAB_ORDER.map((tab) => {
    if (tab.id === 'artifacts') return { ...tab, count: artifacts.length };
    if (tab.id === 'claims') return { ...tab, count: claims.length };
    if (tab.id === 'drafts') return { ...tab, count: drafts.length };
    if (tab.id === 'tasks') return { ...tab, count: tasks.filter((task) => task.status !== 'completed').length };
    if (tab.id === 'critiques') return { ...tab, count: critiques.filter((critique) => critique.status === 'open').length };
    if (tab.id === 'rule-checks') return { ...tab, count: ruleChecks.length };
    return tab;
  });
}

export default function WorkspacePage() {
  const { workspaceId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const activeTab = TAB_ORDER.find((tab) => location.pathname.endsWith(`/${tab.id}`))?.id || 'overview';
  const urlSearchQuery = useMemo(() => new URLSearchParams(location.search).get('q') || '', [location.search]);
  const autoSearchKeyRef = useRef('');

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

  const flash = (message, tone = 'good') => {
    setBanner({ message, tone });
    window.setTimeout(() => {
      setBanner((current) => (current?.message === message ? null : current));
    }, 3200);
  };

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
      const drafts = artifacts.filter((artifact) => artifact.type === 'draft');
      const latestDraftVersion = drafts
        .flatMap((draft) => versionsByArtifact[draft.id] || [])
        .sort((a, b) => b.version - a.version)[0];
      const firstArtifactVersion = artifacts.flatMap((artifact) => versionsByArtifact[artifact.id] || [])[0];

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
      setSelectedDraftId((current) => current || drafts[0]?.id || null);
      setRuleCheckDraftVersionId((current) => current || latestDraftVersion?.id || '');
      setPdfRequestArtifactId((current) => current || artifacts.find((artifact) => artifact.type === 'pdf')?.id || '');
      setSandboxForm((current) => ({
        ...current,
        script_artifact_id:
          current.script_artifact_id || artifacts.find((artifact) => ['code', 'script'].includes(artifact.type))?.id || '',
      }));
      setDraftVersionForm((current) => ({
        ...current,
        draftId: current.draftId || drafts[0]?.id || '',
      }));
      setClaimEvidenceForm((current) => ({
        ...current,
        claimId: current.claimId || claims[0]?.id || '',
        artifactVersionId: current.artifactVersionId || firstArtifactVersion?.id || '',
      }));
      setCritiqueForm((current) => ({
        ...current,
        target_id: current.target_id || claims[0]?.id || firstArtifactVersion?.id || '',
      }));
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
  const artifacts = consoleState.artifacts;
  const drafts = artifacts.filter((artifact) => artifact.type === 'draft');
  const selectedDraft = drafts.find((draft) => draft.id === selectedDraftId) || null;
  const isWorkspaceMember = team.some((member) => member.agent_id === currentAgentId && member.status === 'active');
  const canReviewJoinRequests = team.some(
    (member) => member.agent_id === currentAgentId && member.status === 'active' && member.role_name === 'Maintainer'
  );

  const allArtifactVersions = useMemo(
    () =>
      artifacts.flatMap((artifact) =>
        (consoleState.versionsByArtifact[artifact.id] || []).map((version) => ({
          ...version,
          artifact,
          label: `${artifact.short_id} · ${humanize(artifact.type)} · v${version.version}`,
        }))
      ),
    [artifacts, consoleState.versionsByArtifact]
  );

  const overviewMetrics = useMemo(
    () => ({
      artifacts: artifacts.length,
      claims: consoleState.claims.length,
      critiques: consoleState.critiques.length,
      tasks: consoleState.tasks.filter((task) => task.status !== 'completed').length,
      blockers:
        consoleState.critiques.filter((critique) => critique.status === 'open' && critique.severity === 'blocking').length +
        consoleState.ruleChecks.filter((check) => check.status === 'fail').length,
    }),
    [artifacts.length, consoleState.claims.length, consoleState.critiques, consoleState.ruleChecks, consoleState.tasks]
  );

  const timelineItems = useMemo(
    () =>
      [
        ...consoleState.events.map((event) => ({ ...event, kind: 'event' })),
        ...consoleState.logs.map((log) => ({ ...log, kind: 'log' })),
      ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)),
    [consoleState.events, consoleState.logs]
  );

  const tabConfig = useMemo(
    () =>
      buildTabCounts({
        artifacts,
        claims: consoleState.claims,
        critiques: consoleState.critiques,
        drafts,
        tasks: consoleState.tasks,
        ruleChecks: consoleState.ruleChecks,
      }),
    [artifacts, consoleState.claims, consoleState.critiques, drafts, consoleState.ruleChecks, consoleState.tasks]
  );

  const handleSearch = async (query) => {
    if (!query.trim()) return;
    try {
      const response = await apiClient.search(query.trim(), workspaceId);
      setSearchResults(response);
    } catch (err) {
      flash(err.message || 'Search failed', 'danger');
    }
  };

  useEffect(() => {
    setSearchQuery(urlSearchQuery);
    if (activeTab !== 'search' || !urlSearchQuery.trim()) return;
    const key = `${workspaceId}:${urlSearchQuery.trim()}`;
    if (autoSearchKeyRef.current === key) return;
    autoSearchKeyRef.current = key;
    void handleSearch(urlSearchQuery.trim());
  }, [activeTab, urlSearchQuery, workspaceId]);

  const shellActions = useMemo(
    () => (
      <>
        <button type="button" className="btn btn-secondary" onClick={() => navigate(`/projects/${workspaceId}/requests`)}>
          Run request
        </button>
        <button type="button" className="btn btn-primary" onClick={() => navigate(`/projects/${workspaceId}/search`)}>
          Open search
        </button>
      </>
    ),
    [navigate, workspaceId]
  );

  const shellSearchSubmit = useMemo(
    () => (query) => {
      if (!query.trim()) return;
      navigate(`/projects/${workspaceId}/search?q=${encodeURIComponent(query.trim())}`);
    },
    [navigate, workspaceId]
  );

  const shellFrame = useMemo(
    () => ({
      eyebrow: activeTab === 'overview' ? 'Workspace command center' : `Workspace area · ${humanize(activeTab)}`,
      title: workspace?.name || 'Workspace console',
      summary:
        workspace?.description ||
        'Track evidence, requests, tasks, and review pressure from one operational console.',
      search: {
        initialValue: urlSearchQuery,
        placeholder: 'Search this workspace across indexed evidence and drafts',
        buttonLabel: 'Search workspace',
        hint: 'Search routes directly to the workspace index and preserves the query in the URL.',
        onSubmit: shellSearchSubmit,
      },
      actions: shellActions,
    }),
    [activeTab, shellActions, shellSearchSubmit, urlSearchQuery, workspace?.description, workspace?.name]
  );

  useShellFrame(shellFrame);

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
          <OverviewTab
            workspaceId={workspaceId}
            workspace={workspace}
            team={team}
            artifacts={artifacts}
            tasks={consoleState.tasks}
            critiques={consoleState.critiques}
            ruleChecks={consoleState.ruleChecks}
            phaseStatus={consoleState.phaseStatus}
            gateStatus={consoleState.gateStatus}
            timelineItems={timelineItems}
            workspaceDescription={workspaceDescription}
            setWorkspaceDescription={setWorkspaceDescription}
            runAction={runAction}
            updateWorkspace={apiClient.updateWorkspace.bind(apiClient)}
          />
        );
      case 'team':
        return (
          <TeamTab
            workspaceId={workspaceId}
            team={team}
            isWorkspaceMember={isWorkspaceMember}
            canReviewJoinRequests={canReviewJoinRequests}
            roles={consoleState.roles}
            joinRoleId={joinRoleId}
            setJoinRoleId={setJoinRoleId}
            joinRequests={consoleState.joinRequests}
            runAction={runAction}
            createJoinRequest={apiClient.createJoinRequest.bind(apiClient)}
            reviewJoinRequest={apiClient.reviewJoinRequest.bind(apiClient)}
          />
        );
      case 'requests':
        return (
          <RequestsTab
            workspaceId={workspaceId}
            artifacts={artifacts}
            drafts={drafts}
            versionsByArtifact={consoleState.versionsByArtifact}
            logs={consoleState.logs}
            ruleChecks={consoleState.ruleChecks}
            pdfRequestArtifactId={pdfRequestArtifactId}
            setPdfRequestArtifactId={setPdfRequestArtifactId}
            repoRequestForm={repoRequestForm}
            setRepoRequestForm={setRepoRequestForm}
            sandboxForm={sandboxForm}
            setSandboxForm={setSandboxForm}
            ruleCheckDraftVersionId={ruleCheckDraftVersionId}
            setRuleCheckDraftVersionId={setRuleCheckDraftVersionId}
            runAction={runAction}
            requestIngestPdf={apiClient.requestIngestPdf.bind(apiClient)}
            requestIngestRepo={apiClient.requestIngestRepo.bind(apiClient)}
            requestRunSandbox={apiClient.requestRunSandbox.bind(apiClient)}
            runRuleCheck={apiClient.runRuleCheck.bind(apiClient)}
          />
        );
      case 'artifacts':
        return (
          <ArtifactsTab
            workspaceId={workspaceId}
            artifacts={artifacts}
            versionsByArtifact={consoleState.versionsByArtifact}
            selectedArtifactId={selectedArtifactId}
            setSelectedArtifactId={setSelectedArtifactId}
            artifactForm={artifactForm}
            setArtifactForm={setArtifactForm}
            artifactFile={artifactFile}
            setArtifactFile={setArtifactFile}
            runAction={runAction}
            createArtifact={apiClient.createArtifact.bind(apiClient)}
            createArtifactVersion={apiClient.createArtifactVersion.bind(apiClient)}
          />
        );
      case 'claims':
        return (
          <ClaimsTab
            workspaceId={workspaceId}
            claims={consoleState.claims}
            allArtifactVersions={allArtifactVersions}
            claimForm={claimForm}
            setClaimForm={setClaimForm}
            claimEvidenceForm={claimEvidenceForm}
            setClaimEvidenceForm={setClaimEvidenceForm}
            runAction={runAction}
            createClaim={apiClient.createClaim.bind(apiClient)}
            addEvidenceToClaim={apiClient.addEvidenceToClaim.bind(apiClient)}
            openEvidence={openEvidence}
          />
        );
      case 'drafts':
        return (
          <DraftsTab
            workspaceId={workspaceId}
            drafts={drafts}
            versionsByArtifact={consoleState.versionsByArtifact}
            selectedDraftId={selectedDraftId}
            setSelectedDraftId={setSelectedDraftId}
            selectedDraftContent={selectedDraftContent}
            loadingDraft={loadingDraft}
            draftForm={draftForm}
            setDraftForm={setDraftForm}
            draftVersionForm={draftVersionForm}
            setDraftVersionForm={setDraftVersionForm}
            runAction={runAction}
            createDraft={apiClient.createDraft.bind(apiClient)}
            createDraftVersion={apiClient.createDraftVersion.bind(apiClient)}
            openEvidence={openEvidence}
            gateStatus={consoleState.gateStatus}
          />
        );
      case 'tasks':
        return (
          <TasksTab
            tasks={consoleState.tasks}
            currentAgentId={currentAgentId}
            runAction={runAction}
            updateTask={apiClient.updateTask.bind(apiClient)}
          />
        );
      case 'critiques':
        return (
          <CritiquesTab
            workspaceId={workspaceId}
            claims={consoleState.claims}
            allArtifactVersions={allArtifactVersions}
            critiques={consoleState.critiques}
            critiqueForm={critiqueForm}
            setCritiqueForm={setCritiqueForm}
            runAction={runAction}
            createCritique={apiClient.createCritique.bind(apiClient)}
            updateCritique={apiClient.updateCritique.bind(apiClient)}
          />
        );
      case 'rule-checks':
        return <RuleChecksTab ruleChecks={consoleState.ruleChecks} />;
      case 'timeline':
        return <TimelineTab timelineItems={timelineItems} />;
      case 'search':
        return (
          <SearchTab
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            searchResults={searchResults}
            onSearch={handleSearch}
            setProvenanceViewer={setProvenanceViewer}
          />
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
        <div className="workspace-hero-copy">
          <div className="workspace-inline-row wrap">
            <p className="workspace-kicker">Workspace command center</p>
            <StatusPill label={humanize(workspace.phase)} tone="info" />
            <StatusPill
              label={consoleState.gateStatus?.gate_required ? `Gate ${consoleState.gateStatus.gate_status || 'unknown'}` : 'No gate'}
              tone={consoleState.gateStatus?.can_advance ? 'good' : consoleState.gateStatus?.gate_required ? 'warning' : 'info'}
            />
          </div>
          <h2>{workspace.name}</h2>
          <p>{workspace.description || 'No workspace description yet.'}</p>
          <div className="workspace-hero-footnotes">
            <span>Latest activity {timelineItems[0] ? formatTimestamp(timelineItems[0].created_at) : 'none yet'}</span>
            <span>{team.length} active collaborators</span>
            <span>{consoleState.joinRequests.length} join requests tracked</span>
          </div>
        </div>
        <div className="workspace-hero-right">
          <div className="workspace-hero-metrics">
            <MetricTile label="Artifacts" value={overviewMetrics.artifacts} />
            <MetricTile label="Claims" value={overviewMetrics.claims} />
            <MetricTile label="Open tasks" value={overviewMetrics.tasks} />
            <MetricTile label="Blockers" value={overviewMetrics.blockers} tone={overviewMetrics.blockers > 0 ? 'danger' : 'good'} />
          </div>
          <div className="workspace-signal-strip">
            <div className="workspace-signal">
              <span>Team pressure</span>
              <strong>{consoleState.critiques.filter((critique) => critique.status === 'open').length} open critiques</strong>
            </div>
            <div className="workspace-signal">
              <span>Governance</span>
              <strong>{consoleState.ruleChecks.filter((check) => check.status === 'fail').length} failing checks</strong>
            </div>
          </div>
        </div>
      </section>

      {banner ? <div className={`workspace-banner workspace-banner-${banner.tone}`}>{banner.message}</div> : null}

      <div className="workspace-layout">
        <aside className="workspace-sidebar">
          <SectionCard eyebrow="Navigation" title="Workspace areas">
            <TabNav tabs={tabConfig} activeTab={activeTab} onTabChange={(tabId) => navigate(`/projects/${workspaceId}/${tabId}`)} />
          </SectionCard>

          <SectionCard eyebrow="Operator context" title="Live summary">
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

          <SectionCard eyebrow="Audit trail" title="Recent signals">
            {timelineItems.length ? (
              <div className="stack">
                {timelineItems.slice(0, 3).map((item) => (
                  <div key={`${item.kind}-${item.id}`} className="signal-card">
                    <StatusPill label={item.kind === 'event' ? humanize(item.event_type) : humanize(item.level || item.action || 'log')} tone={toneForStatus(item.level || item.event_type)} />
                    <strong>{formatTimestamp(item.created_at)}</strong>
                    <span>{item.kind === 'event' ? item.event_type : item.message || item.action}</span>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No signals yet" body="Recent logs and events will appear here." />
            )}
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
