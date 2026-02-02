import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import apiClient from '../api/client';
import { PageContainer, TabNav, Card } from '../components/Layout';
import { PhaseBadge, StatusBadge, SeverityBadge } from '../components/Badge';
import EvidenceDrawer from '../components/EvidenceDrawer';
import ReactMarkdown from 'react-markdown';
import './WorkspacePage.css';

export default function WorkspacePage() {
  const { workspaceId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [workspace, setWorkspace] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Determine active tab from URL
  const pathParts = location.pathname.split('/');
  const activeTab = pathParts[pathParts.length - 1] || 'overview';

  useEffect(() => {
    loadWorkspace();
  }, [workspaceId]);

  const loadWorkspace = async () => {
    try {
      const data = await apiClient.getWorkspace(workspaceId);
      setWorkspace(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'timeline', label: 'Timeline' },
    { id: 'artifacts', label: 'Artifacts' },
    { id: 'claims', label: 'Claims' },
    { id: 'drafts', label: 'Drafts' },
    { id: 'critiques', label: 'Critiques' },
    { id: 'rule-checks', label: 'Rule Checks' },
  ];

  const handleTabChange = (tabId) => {
    navigate(`/projects/${workspaceId}/${tabId}`);
  };

  if (loading) {
    return (
      <PageContainer>
        <div className="loading">Loading workspace...</div>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <div className="error">Error loading workspace: {error}</div>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <div className="workspace-header">
        <div className="workspace-title-row">
          <h2 className="workspace-name">{workspace.name}</h2>
          <PhaseBadge phase={workspace.phase} />
        </div>
        {workspace.description && (
          <p className="workspace-description">{workspace.description}</p>
        )}
        {workspace.tags && workspace.tags.length > 0 && (
          <div className="workspace-tags">
            {workspace.tags.map((tag, idx) => (
              <span key={idx} className="tag">{tag}</span>
            ))}
          </div>
        )}
      </div>

      <TabNav tabs={tabs} activeTab={activeTab} onTabChange={handleTabChange} />

      <div className="tab-content">
        {activeTab === 'overview' && <OverviewTab workspaceId={workspaceId} />}
        {activeTab === 'timeline' && <TimelineTab workspaceId={workspaceId} />}
        {activeTab === 'artifacts' && <ArtifactsTab workspaceId={workspaceId} />}
        {activeTab === 'claims' && <ClaimsTab workspaceId={workspaceId} />}
        {activeTab === 'drafts' && <DraftsTab workspaceId={workspaceId} />}
        {activeTab === 'critiques' && <CritiquesTab workspaceId={workspaceId} />}
        {activeTab === 'rule-checks' && <RuleChecksTab workspaceId={workspaceId} />}
      </div>
    </PageContainer>
  );
}

// Overview Tab
function OverviewTab({ workspaceId }) {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [artifacts, claims, ruleChecks, critiques] = await Promise.all([
          apiClient.getWorkspaceArtifacts(workspaceId),
          apiClient.getWorkspaceClaims(workspaceId),
          apiClient.getRuleChecks(workspaceId),
          apiClient.getWorkspaceCritiques(workspaceId)
        ]);
        setData({ artifacts, claims, ruleChecks, critiques });
      } catch (err) {
        console.error('Error loading overview:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [workspaceId]);

  if (loading) return <div className="loading">Loading overview...</div>;

  const failingRuleChecks = data.ruleChecks?.filter(rc => rc.status === 'fail') || [];
  const blockingCritiques = data.critiques?.filter(c => c.severity === 'blocking' && c.status === 'open') || [];

  return (
    <div className="overview-grid">
      <Card title="Quick Stats">
        <div className="stats-grid">
          <div className="stat-item">
            <div className="stat-label">Artifacts</div>
            <div className="stat-value">{data.artifacts?.length || 0}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">Claims</div>
            <div className="stat-value">{data.claims?.length || 0}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">Rule Checks</div>
            <div className="stat-value">{data.ruleChecks?.length || 0}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">Critiques</div>
            <div className="stat-value">{data.critiques?.length || 0}</div>
          </div>
        </div>
      </Card>

      {failingRuleChecks.length > 0 && (
        <Card title="Failing Rule Checks">
          <div className="list-items">
            {failingRuleChecks.slice(0, 5).map((rc, idx) => (
              <div key={idx} className="list-item">
                <StatusBadge status={rc.status} />
                <span>{rc.rule_name}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {blockingCritiques.length > 0 && (
        <Card title="Blocking Critiques">
          <div className="list-items">
            {blockingCritiques.slice(0, 5).map((c, idx) => (
              <div key={idx} className="list-item">
                <SeverityBadge severity={c.severity} />
                <span>{c.content.substring(0, 100)}...</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

// Timeline Tab
function TimelineTab({ workspaceId }) {
  const [events, setEvents] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadTimeline = async () => {
      try {
        const [eventsData, logsData] = await Promise.all([
          apiClient.getWorkspaceEvents(workspaceId),
          apiClient.getWorkspaceLogs(workspaceId)
        ]);
        setEvents(eventsData);
        setLogs(logsData);
      } catch (err) {
        console.error('Error loading timeline:', err);
      } finally {
        setLoading(false);
      }
    };
    loadTimeline();
  }, [workspaceId]);

  if (loading) return <div className="loading">Loading timeline...</div>;

  // Combine and sort
  const combined = [
    ...events.map(e => ({ ...e, type: 'event' })),
    ...logs.map(l => ({ ...l, type: 'log' }))
  ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  return (
    <Card title="Timeline">
      <div className="timeline-list">
        {combined.length === 0 ? (
          <div className="empty-state">No events or logs yet.</div>
        ) : (
          combined.map((item, idx) => (
            <div key={idx} className="timeline-item">
              <div className="timeline-meta">
                <span className="timeline-type">{item.type}</span>
                <span className="timeline-time">
                  {new Date(item.created_at).toLocaleString()}
                </span>
              </div>
              <div className="timeline-content">
                {item.type === 'event' ? (
                  <>
                    <strong>{item.event_type}</strong>
                    {item.payload && <pre className="json-preview">{JSON.stringify(item.payload, null, 2)}</pre>}
                  </>
                ) : (
                  <>
                    <span className="log-level">[{item.level}]</span> {item.message}
                  </>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

// Artifacts Tab
function ArtifactsTab({ workspaceId }) {
  const [artifacts, setArtifacts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadArtifacts = async () => {
      try {
        const data = await apiClient.getWorkspaceArtifacts(workspaceId);
        setArtifacts(data);
      } catch (err) {
        console.error('Error loading artifacts:', err);
      } finally {
        setLoading(false);
      }
    };
    loadArtifacts();
  }, [workspaceId]);

  if (loading) return <div className="loading">Loading artifacts...</div>;

  return (
    <Card title="Artifacts">
      {artifacts.length === 0 ? (
        <div className="empty-state">No artifacts yet.</div>
      ) : (
        <div className="artifacts-list">
          {artifacts.map((artifact) => (
            <div key={artifact.id} className="artifact-item">
              <div className="artifact-header">
                <span className="artifact-type">{artifact.type}</span>
                <span className="artifact-short-id">{artifact.short_id}</span>
              </div>
              <div className="artifact-meta">
                <span>Created: {new Date(artifact.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// Claims Tab
function ClaimsTab({ workspaceId }) {
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(true);
  const [evidenceDrawer, setEvidenceDrawer] = useState(null);

  useEffect(() => {
    const loadClaims = async () => {
      try {
        const data = await apiClient.getWorkspaceClaims(workspaceId);
        setClaims(data);
      } catch (err) {
        console.error('Error loading claims:', err);
      } finally {
        setLoading(false);
      }
    };
    loadClaims();
  }, [workspaceId]);

  const openEvidence = (artifactVersionId, location) => {
    setEvidenceDrawer({ artifactVersionId, location });
  };

  if (loading) return <div className="loading">Loading claims...</div>;

  return (
    <>
      <Card title="Claims">
        {claims.length === 0 ? (
          <div className="empty-state">No claims yet.</div>
        ) : (
          <div className="claims-list">
            {claims.map((claim) => (
              <div key={claim.id} className="claim-item">
                <p className="claim-text">{claim.text}</p>
                {claim.evidence && claim.evidence.length > 0 && (
                  <div className="claim-evidence">
                    <strong>Evidence: </strong>
                    {claim.evidence.map((ev, idx) => (
                      <button
                        key={idx}
                        className="evidence-button"
                        onClick={() => openEvidence(ev.artifact_version_id, ev.location)}
                      >
                        Evidence {idx + 1}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
      
      {evidenceDrawer && (
        <EvidenceDrawer
          artifactVersionId={evidenceDrawer.artifactVersionId}
          location={evidenceDrawer.location}
          onClose={() => setEvidenceDrawer(null)}
        />
      )}
    </>
  );
}

// Drafts Tab
function DraftsTab({ workspaceId }) {
  const [artifacts, setArtifacts] = useState([]);
  const [selectedDraft, setSelectedDraft] = useState(null);
  const [draftContent, setDraftContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [evidenceDrawer, setEvidenceDrawer] = useState(null);

  useEffect(() => {
    const loadDrafts = async () => {
      try {
        const allArtifacts = await apiClient.getWorkspaceArtifacts(workspaceId);
        const drafts = allArtifacts.filter(a => a.type === 'draft');
        setArtifacts(drafts);
        if (drafts.length > 0) {
          selectDraft(drafts[0]);
        }
      } catch (err) {
        console.error('Error loading drafts:', err);
      } finally {
        setLoading(false);
      }
    };
    loadDrafts();
  }, [workspaceId]);

  const selectDraft = async (draft) => {
    setSelectedDraft(draft);
    try {
      const versions = await apiClient.getArtifactVersions(draft.id);
      if (versions.length > 0) {
        const latestVersion = versions[versions.length - 1];
        const content = await apiClient.getArtifactVersionContent(latestVersion.id);
        setDraftContent(content.text || content.content || 'No content');
      }
    } catch (err) {
      console.error('Error loading draft content:', err);
      setDraftContent('Error loading content');
    }
  };

  const renderDraftContent = (text) => {
    // Parse [[cite:artifact_version_id|location]] markers
    const citationRegex = /\[\[cite:([^|]+)\|([^\]]+)\]\]/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = citationRegex.exec(text)) !== null) {
      // Add text before citation
      if (match.index > lastIndex) {
        parts.push({
          type: 'text',
          content: text.substring(lastIndex, match.index)
        });
      }
      // Add citation
      parts.push({
        type: 'citation',
        artifactVersionId: match[1],
        location: match[2]
      });
      lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      parts.push({
        type: 'text',
        content: text.substring(lastIndex)
      });
    }

    return parts.map((part, idx) => {
      if (part.type === 'citation') {
        return (
          <button
            key={idx}
            className="cite-chip"
            onClick={() => setEvidenceDrawer({
              artifactVersionId: part.artifactVersionId,
              location: part.location
            })}
            title={`${part.artifactVersionId}: ${part.location}`}
          >
            📎 Cite
          </button>
        );
      }
      return <ReactMarkdown key={idx}>{part.content}</ReactMarkdown>;
    });
  };

  if (loading) return <div className="loading">Loading drafts...</div>;

  return (
    <>
      <div className="drafts-view">
        <div className="drafts-sidebar">
          <h4>Draft Versions</h4>
          {artifacts.length === 0 ? (
            <div className="empty-state">No drafts yet.</div>
          ) : (
            artifacts.map((draft) => (
              <div
                key={draft.id}
                className={`draft-item ${selectedDraft?.id === draft.id ? 'active' : ''}`}
                onClick={() => selectDraft(draft)}
              >
                <span className="draft-name">{draft.short_id}</span>
                <span className="draft-date">{new Date(draft.created_at).toLocaleDateString()}</span>
              </div>
            ))
          )}
        </div>
        <div className="drafts-content">
          {selectedDraft ? (
            <Card title={`Draft: ${selectedDraft.short_id}`}>
              <div className="markdown-content">
                {renderDraftContent(draftContent)}
              </div>
            </Card>
          ) : (
            <div className="empty-state">Select a draft to view</div>
          )}
        </div>
      </div>
      
      {evidenceDrawer && (
        <EvidenceDrawer
          artifactVersionId={evidenceDrawer.artifactVersionId}
          location={evidenceDrawer.location}
          onClose={() => setEvidenceDrawer(null)}
        />
      )}
    </>
  );
}

// Critiques Tab
function CritiquesTab({ workspaceId }) {
  const [critiques, setCritiques] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadCritiques = async () => {
      try {
        const data = await apiClient.getWorkspaceCritiques(workspaceId);
        setCritiques(data);
      } catch (err) {
        console.error('Error loading critiques:', err);
      } finally {
        setLoading(false);
      }
    };
    loadCritiques();
  }, [workspaceId]);

  if (loading) return <div className="loading">Loading critiques...</div>;

  return (
    <Card title="Critiques">
      {critiques.length === 0 ? (
        <div className="empty-state">No critiques yet.</div>
      ) : (
        <div className="critiques-list">
          {critiques.map((critique) => (
            <div key={critique.id} className="critique-item">
              <div className="critique-header">
                <SeverityBadge severity={critique.severity} />
                <StatusBadge status={critique.status} />
              </div>
              <p className="critique-content">{critique.content}</p>
              <div className="critique-meta">
                <span>Created: {new Date(critique.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// Rule Checks Tab
function RuleChecksTab({ workspaceId }) {
  const [ruleChecks, setRuleChecks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadRuleChecks = async () => {
      try {
        const data = await apiClient.getRuleChecks(workspaceId);
        setRuleChecks(data);
      } catch (err) {
        console.error('Error loading rule checks:', err);
      } finally {
        setLoading(false);
      }
    };
    loadRuleChecks();
  }, [workspaceId]);

  if (loading) return <div className="loading">Loading rule checks...</div>;

  return (
    <Card title="Rule Checks">
      {ruleChecks.length === 0 ? (
        <div className="empty-state">No rule checks yet.</div>
      ) : (
        <div className="rule-checks-list">
          {ruleChecks.map((rc, idx) => (
            <div key={idx} className="rule-check-item">
              <div className="rule-check-header">
                <strong>{rc.rule_name}</strong>
                <StatusBadge status={rc.status} />
              </div>
              <div className="rule-check-meta">
                <span>Target: {rc.target_type}</span>
                <span>Checked: {new Date(rc.created_at).toLocaleString()}</span>
              </div>
              {rc.details && (
                <pre className="json-preview">{JSON.stringify(rc.details, null, 2)}</pre>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
