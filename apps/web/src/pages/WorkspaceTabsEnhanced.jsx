import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { Card } from '../components/Layout';
import { StatusBadge, SeverityBadge } from '../components/Badge';
import { FilterBar, SplitPane } from '../components/Molecules';
import { Timestamp } from '../components/Atoms';
import EvidenceDrawer from '../components/EvidenceDrawer';
import './WorkspaceTabsEnhanced.css';

/**
 * Enhanced Timeline Tab with filters and summary/raw toggle
 */
export function TimelineTabEnhanced({ workspaceId }) {
  const [events, setEvents] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ showMode: 'both', type: 'all' });

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

  const handleFilterChange = (filterId, value) => {
    setFilters({ ...filters, [filterId]: value });
  };

  const filterDefinitions = [
    {
      id: 'type',
      label: 'Type',
      type: 'select',
      options: [
        { value: 'all', label: 'All' },
        { value: 'events', label: 'Events Only' },
        { value: 'logs', label: 'Logs Only' }
      ],
      value: filters.type
    },
    {
      id: 'showMode',
      label: 'Display',
      type: 'select',
      options: [
        { value: 'both', label: 'Summary' },
        { value: 'raw', label: 'Raw JSON' }
      ],
      value: filters.showMode
    }
  ];

  if (loading) return <div className="loading">Loading timeline...</div>;

  const filteredEvents = filters.type === 'logs' ? [] : events;
  const filteredLogs = filters.type === 'events' ? [] : logs;
  const combined = [
    ...filteredEvents.map(e => ({ ...e, type: 'event' })),
    ...filteredLogs.map(l => ({ ...l, type: 'log' }))
  ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  return (
    <Card title="Timeline">
      <FilterBar filters={filterDefinitions} onFilterChange={handleFilterChange} />
      
      <div className="timeline-list">
        {combined.length === 0 ? (
          <div className="empty-state">No events or logs yet.</div>
        ) : (
          combined.map((item, idx) => (
            <div key={idx} className="timeline-item">
              <div className="timeline-meta">
                <span className="timeline-type">{item.type}</span>
                <Timestamp date={item.created_at} />
              </div>
              <div className="timeline-content">
                {item.type === 'event' ? (
                  <>
                    <strong>{item.event_type}</strong>
                    {filters.showMode === 'raw' && item.payload && (
                      <pre className="json-preview">{JSON.stringify(item.payload, null, 2)}</pre>
                    )}
                    {filters.showMode === 'both' && item.payload && (
                      <div className="payload-summary">
                        {Object.keys(item.payload).length} fields
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    <span className="log-level">[{item.level}]</span> {item.message}
                    {filters.showMode === 'raw' && item.payload && (
                      <pre className="json-preview">{JSON.stringify(item.payload, null, 2)}</pre>
                    )}
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

/**
 * Enhanced Claims Tab with split pane and evidence viewing
 */
export function ClaimsTabEnhanced({ workspaceId }) {
  const [claims, setClaims] = useState([]);
  const [selectedClaim, setSelectedClaim] = useState(null);
  const [critiques, setCritiques] = useState([]);
  const [loading, setLoading] = useState(true);
  const [evidenceDrawer, setEvidenceDrawer] = useState(null);
  const [filters, setFilters] = useState({});

  useEffect(() => {
    loadClaims();
  }, [workspaceId]);

  const loadClaims = async () => {
    try {
      const [claimsData, critiquesData] = await Promise.all([
        apiClient.getWorkspaceClaims(workspaceId),
        apiClient.getWorkspaceCritiques(workspaceId)
      ]);
      setClaims(claimsData);
      setCritiques(critiquesData);
    } catch (err) {
      console.error('Error loading claims:', err);
    } finally {
      setLoading(false);
    }
  };

  const selectClaim = (claim) => {
    setSelectedClaim(claim);
  };

  const openEvidence = (artifactVersionId, location) => {
    setEvidenceDrawer({ artifactVersionId, location });
  };

  const filterDefinitions = [
    {
      id: 'kind',
      label: 'Kind',
      type: 'select',
      options: [
        { value: 'fact', label: 'Fact' },
        { value: 'hypothesis', label: 'Hypothesis' }
      ],
      value: filters.kind
    },
    {
      id: 'hasEvidence',
      label: 'Evidence',
      type: 'toggle',
      toggleLabel: 'Has Evidence',
      value: filters.hasEvidence
    }
  ];

  const handleFilterChange = (filterId, value) => {
    setFilters({ ...filters, [filterId]: value });
  };

  const filteredClaims = claims.filter((claim) => {
    if (filters.kind && claim.kind !== filters.kind) return false;
    if (filters.hasEvidence && (!claim.evidence || claim.evidence.length === 0)) return false;
    return true;
  });

  const claimCritiques = selectedClaim
    ? critiques.filter(c => c.target_type === 'claim' && c.target_id === selectedClaim.id)
    : [];

  if (loading) return <div className="loading">Loading claims...</div>;

  const leftPanel = (
    <div className="claims-list">
      <FilterBar filters={filterDefinitions} onFilterChange={handleFilterChange} />
      {filteredClaims.length === 0 ? (
        <div className="empty-state">No claims match filters.</div>
      ) : (
        filteredClaims.map((claim) => (
          <div
            key={claim.id}
            className={`claim-list-item ${selectedClaim?.id === claim.id ? 'active' : ''}`}
            onClick={() => selectClaim(claim)}
          >
            <p className="claim-text-preview">{claim.text.substring(0, 100)}...</p>
            {claim.evidence && claim.evidence.length > 0 && (
              <div className="claim-meta">
                📎 {claim.evidence.length} evidence pointer(s)
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );

  const rightPanel = selectedClaim ? (
    <div className="claim-detail">
      <h3>Claim Details</h3>
      <p className="claim-full-text">{selectedClaim.text}</p>
      
      <div className="claim-metadata">
        <div><strong>Kind:</strong> {selectedClaim.kind}</div>
        <div><strong>Status:</strong> {selectedClaim.status}</div>
        {selectedClaim.confidence !== undefined && (
          <div><strong>Confidence:</strong> {selectedClaim.confidence}</div>
        )}
      </div>

      {selectedClaim.evidence && selectedClaim.evidence.length > 0 && (
        <div className="claim-evidence-section">
          <h4>Evidence Pointers</h4>
          {selectedClaim.evidence.map((ev, idx) => (
            <button
              key={idx}
              className="evidence-pointer-button"
              onClick={() => openEvidence(ev.artifact_version_id, ev.location)}
            >
              📎 Evidence {idx + 1}: {ev.location}
            </button>
          ))}
        </div>
      )}

      {claimCritiques.length > 0 && (
        <div className="claim-critiques-section">
          <h4>Related Critiques</h4>
          {claimCritiques.map((critique, idx) => (
            <div key={idx} className="critique-item-small">
              <SeverityBadge severity={critique.severity} />
              <span>{critique.content.substring(0, 80)}...</span>
            </div>
          ))}
        </div>
      )}
    </div>
  ) : (
    <div className="empty-state">Select a claim to view details</div>
  );

  return (
    <>
      <Card title="Claims">
        <SplitPane left={leftPanel} right={rightPanel} leftWidth="350px" />
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

/**
 * Enhanced Critiques Tab with split pane and filters
 */
export function CritiquesTabEnhanced({ workspaceId }) {
  const [critiques, setCritiques] = useState([]);
  const [selectedCritique, setSelectedCritique] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({});

  useEffect(() => {
    loadCritiques();
  }, [workspaceId]);

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

  const filterDefinitions = [
    {
      id: 'severity',
      label: 'Severity',
      type: 'select',
      options: [
        { value: 'info', label: 'Info' },
        { value: 'minor', label: 'Minor' },
        { value: 'major', label: 'Major' },
        { value: 'blocking', label: 'Blocking' }
      ],
      value: filters.severity
    },
    {
      id: 'status',
      label: 'Status',
      type: 'select',
      options: [
        { value: 'open', label: 'Open' },
        { value: 'resolved', label: 'Resolved' },
        { value: 'deferred', label: 'Deferred' }
      ],
      value: filters.status
    }
  ];

  const handleFilterChange = (filterId, value) => {
    setFilters({ ...filters, [filterId]: value });
  };

  const filteredCritiques = critiques.filter((critique) => {
    if (filters.severity && critique.severity !== filters.severity) return false;
    if (filters.status && critique.status !== filters.status) return false;
    return true;
  });

  const blockingCritiques = critiques.filter(c => c.severity === 'blocking' && c.status === 'open');

  if (loading) return <div className="loading">Loading critiques...</div>;

  const leftPanel = (
    <div className="critiques-list">
      {blockingCritiques.length > 0 && (
        <div className="blockers-alert">
          ⚠️ {blockingCritiques.length} blocking critique(s) open
        </div>
      )}
      
      <FilterBar filters={filterDefinitions} onFilterChange={handleFilterChange} />
      
      {filteredCritiques.length === 0 ? (
        <div className="empty-state">No critiques match filters.</div>
      ) : (
        filteredCritiques.map((critique) => (
          <div
            key={critique.id}
            className={`critique-list-item ${selectedCritique?.id === critique.id ? 'active' : ''}`}
            onClick={() => setSelectedCritique(critique)}
          >
            <div className="critique-list-header">
              <SeverityBadge severity={critique.severity} />
              <StatusBadge status={critique.status} />
            </div>
            <p className="critique-preview">{critique.content.substring(0, 80)}...</p>
            <div className="critique-list-meta">
              <Timestamp date={critique.created_at} />
            </div>
          </div>
        ))
      )}
    </div>
  );

  const rightPanel = selectedCritique ? (
    <div className="critique-detail">
      <h3>Critique Details</h3>
      <div className="critique-detail-header">
        <SeverityBadge severity={selectedCritique.severity} />
        <StatusBadge status={selectedCritique.status} />
      </div>
      
      <div className="critique-content-full">
        {selectedCritique.content}
      </div>

      <div className="critique-metadata">
        <div><strong>Target Type:</strong> {selectedCritique.target_type}</div>
        <div><strong>Target ID:</strong> <code>{selectedCritique.target_id}</code></div>
        {selectedCritique.target_location && (
          <div><strong>Location:</strong> <code>{selectedCritique.target_location}</code></div>
        )}
        <div><strong>Created:</strong> <Timestamp date={selectedCritique.created_at} showRelative={false} /></div>
      </div>

      {selectedCritique.resolution && (
        <div className="critique-resolution">
          <h4>Resolution</h4>
          <StatusBadge status={selectedCritique.resolution.status} />
          <p>{selectedCritique.resolution.rationale || 'No rationale provided'}</p>
        </div>
      )}
    </div>
  ) : (
    <div className="empty-state">Select a critique to view details</div>
  );

  return (
    <Card title="Critiques">
      <SplitPane left={leftPanel} right={rightPanel} leftWidth="350px" />
    </Card>
  );
}

/**
 * Enhanced Rule Checks Tab with filters and detail drawer
 */
export function RuleChecksTabEnhanced({ workspaceId }) {
  const [ruleChecks, setRuleChecks] = useState([]);
  const [selectedRuleCheck, setSelectedRuleCheck] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({});

  useEffect(() => {
    loadRuleChecks();
  }, [workspaceId]);

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

  const filterDefinitions = [
    {
      id: 'status',
      label: 'Status',
      type: 'select',
      options: [
        { value: 'pass', label: 'Pass' },
        { value: 'fail', label: 'Fail' }
      ],
      value: filters.status
    },
    {
      id: 'ruleName',
      label: 'Rule',
      type: 'select',
      options: [
        { value: 'citation_coverage', label: 'Citation Coverage' },
        { value: 'citation_resolves', label: 'Citation Resolves' },
        { value: 'critique_sufficiency', label: 'Critique Sufficiency' },
        { value: 'role_caps', label: 'Role Caps' }
      ],
      value: filters.ruleName
    }
  ];

  const handleFilterChange = (filterId, value) => {
    setFilters({ ...filters, [filterId]: value });
  };

  const filteredRuleChecks = ruleChecks.filter((rc) => {
    if (filters.status && rc.status !== filters.status) return false;
    if (filters.ruleName && rc.rule_name !== filters.ruleName) return false;
    return true;
  });

  if (loading) return <div className="loading">Loading rule checks...</div>;

  const leftPanel = (
    <div className="rule-checks-list">
      <FilterBar filters={filterDefinitions} onFilterChange={handleFilterChange} />
      
      {filteredRuleChecks.length === 0 ? (
        <div className="empty-state">No rule checks match filters.</div>
      ) : (
        filteredRuleChecks.map((rc) => (
          <div
            key={rc.id}
            className={`rule-check-list-item ${selectedRuleCheck?.id === rc.id ? 'active' : ''}`}
            onClick={() => setSelectedRuleCheck(rc)}
          >
            <div className="rule-check-list-header">
              <StatusBadge status={rc.status} />
              <strong>{rc.rule_name}</strong>
            </div>
            <div className="rule-check-list-meta">
              <span>{rc.target_type}</span>
              <Timestamp date={rc.checked_at} />
            </div>
          </div>
        ))
      )}
    </div>
  );

  const rightPanel = selectedRuleCheck ? (
    <div className="rule-check-detail">
      <h3>Rule Check Details</h3>
      <div className="rule-check-detail-header">
        <StatusBadge status={selectedRuleCheck.status} />
        <h4>{selectedRuleCheck.rule_name}</h4>
      </div>

      <div className="rule-check-metadata">
        <div><strong>Target Type:</strong> {selectedRuleCheck.target_type}</div>
        <div><strong>Target ID:</strong> <code>{selectedRuleCheck.target_id}</code></div>
        <div><strong>Checked:</strong> <Timestamp date={selectedRuleCheck.checked_at} showRelative={false} /></div>
      </div>

      {selectedRuleCheck.details && (
        <div className="rule-check-details-section">
          <h4>Details</h4>
          <pre className="json-details">{JSON.stringify(selectedRuleCheck.details, null, 2)}</pre>
        </div>
      )}
    </div>
  ) : (
    <div className="empty-state">Select a rule check to view details</div>
  );

  return (
    <Card title="Rule Checks">
      <SplitPane left={leftPanel} right={rightPanel} leftWidth="400px" />
    </Card>
  );
}
