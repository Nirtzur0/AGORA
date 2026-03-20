import React from 'react';
import { Link, useParams } from 'react-router-dom';
import './AgoraRedesignPage.css';

const SCREEN_ORDER = [
  'catalog',
  'login',
  'portfolio',
  'workspace-overview',
  'investigation',
  'research-record',
  'operations',
  'review-governance',
  'team-settings',
  'system',
];

const SCREEN_LABELS = {
  catalog: 'Capture Catalog',
  login: 'Login + Onboarding',
  portfolio: 'Portfolio',
  'workspace-overview': 'Workspace Overview',
  investigation: 'Investigation',
  'research-record': 'Research Record',
  operations: 'Operations',
  'review-governance': 'Review and Governance',
  'team-settings': 'Team and Settings',
  system: 'System',
};

const PRODUCT_NAV = [
  {
    title: 'Overview',
    items: ['Portfolio', 'Workspace Overview'],
  },
  {
    title: 'Investigation',
    items: ['Evidence Explorer', 'Search', 'Artifact Viewer'],
  },
  {
    title: 'Research Record',
    items: ['Claims', 'Drafts', 'Citation Coverage'],
  },
  {
    title: 'Operations',
    items: ['Requests', 'Tasks', 'Timeline'],
  },
  {
    title: 'Review',
    items: ['Critiques', 'Rule Checks', 'Gate Readiness'],
  },
  {
    title: 'Administration',
    items: ['Team', 'Roles', 'Integrations', 'Settings'],
  },
];

const portfolioMetrics = [
  { label: 'Flagged workspaces', value: '4', delta: '2 require action today', tone: 'danger' },
  { label: 'Gate risks', value: '7', delta: '3 new since yesterday', tone: 'warning' },
  { label: 'Evidence gaps', value: '12', delta: '8 ready for review', tone: 'info' },
  { label: 'Open maintainer tasks', value: '19', delta: '6 blocked by missing evidence', tone: 'success' },
];

const workspaceCards = [
  {
    name: 'Method Audit: Claim Validation',
    phase: 'Claim Validation',
    owner: 'Nir Tzur',
    blockers: '2 blockers',
    summary: 'Citation coverage dipped after the latest critique; maintainer needs a fast drill-down path.',
    signals: ['Evidence gap', 'Blocking critique', '2 stale requests'],
  },
  {
    name: 'Replication: Paper X',
    phase: 'Experimentation',
    owner: 'Ops reviewer',
    blockers: 'Stable',
    summary: 'Sandbox runs are healthy, but the workspace needs tighter review orchestration before synthesis.',
    signals: ['0 blockers', '3 queued tasks', '1 draft ready'],
  },
  {
    name: 'Browser Agent Test Project',
    phase: 'Init',
    owner: 'Platform QA',
    blockers: 'Needs setup',
    summary: 'Empty-state guidance should pull this workspace into a meaningful first-run flow.',
    signals: ['No evidence', 'No team roles', 'No review coverage'],
  },
];

const riskSignals = [
  { title: 'Claim validation workspace needs gate cleanup', meta: 'Due now', tone: 'danger' },
  { title: 'Artifact provenance stale in two workspaces', meta: '4 hours old', tone: 'warning' },
  { title: 'Three join requests need maintainer review', meta: 'Approval desk', tone: 'info' },
  { title: 'One draft is ready for final governance review', meta: 'Review and Governance', tone: 'success' },
];

const overviewMetrics = [
  { label: 'Workspace health', value: '74', delta: 'Overall confidence score', tone: 'info' },
  { label: 'Open blockers', value: '3', delta: '1 new since morning', tone: 'danger' },
  { label: 'Gate readiness', value: '62%', delta: 'Missing 4 required checks', tone: 'warning' },
  { label: 'Actionable evidence', value: '27', delta: '13 linked to open tasks', tone: 'success' },
];

const blockerRows = [
  {
    title: 'Blocking critique on Claim C-18',
    owner: 'Review lead',
    detail: 'Evidence pointer resolves, but supporting context is not visible without opening three separate surfaces.',
    priority: 'Blocking',
  },
  {
    title: 'Rule check coverage missing on latest draft version',
    owner: 'Maintainer',
    detail: 'Governance state belongs in the workspace command rail, not hidden in a ledger tab.',
    priority: 'High',
  },
  {
    title: 'Sandbox request has been pending for 6 hours',
    owner: 'Operations',
    detail: 'Operational latency needs a summarized workflow card before raw timeline entries.',
    priority: 'Watch',
  },
];

const investigationResults = [
  {
    title: 'Claim C-18 evidence cluster',
    summary: 'PDF paragraph, log line, and draft citation all point to the same contradiction.',
    tags: ['3 linked artifacts', '2 critiques', '1 unresolved gap'],
  },
  {
    title: 'Sandbox execution drift',
    summary: 'Run logs diverged from the approved config artifact after the latest request.',
    tags: ['Execution', 'Config mismatch', 'Needs owner'],
  },
  {
    title: 'Repo ingest coverage',
    summary: 'Index quality is good, but the current UI makes artifact comparison feel like separate chores.',
    tags: ['Searchable', 'Healthy ingest', 'Weak comparison UI'],
  },
];

const researchClaims = [
  {
    id: 'C-18',
    claim: 'The seeded log captured deterministic browser evidence for the claim-validation flow.',
    status: 'Needs more context',
    evidence: '2 direct pointers, 1 critique',
  },
  {
    id: 'C-21',
    claim: 'Draft citations can be resolved to a single immutable artifact version.',
    status: 'Review-ready',
    evidence: '3 linked citations',
  },
  {
    id: 'C-27',
    claim: 'Workspace health should roll up blockers before raw lists.',
    status: 'Hypothesis',
    evidence: 'No evidence yet',
  },
];

const operationsTimeline = [
  { time: '09:14', event: 'Repo ingest requested', detail: 'Queued with deterministic branch pin', tone: 'info' },
  { time: '09:41', event: 'Sandbox run completed', detail: 'Output artifact stored as immutable version', tone: 'success' },
  { time: '10:12', event: 'Rule check failed', detail: 'Citation coverage incomplete in section 2', tone: 'danger' },
  { time: '10:35', event: 'Join request pending', detail: 'Reviewer role requires Maintainer approval', tone: 'warning' },
];

const governanceColumns = [
  {
    title: 'Triage now',
    items: [
      'Blocking critique with no owner',
      'Draft ready but missing governance notes',
      'Evidence drawer proves issue but action path is unclear',
    ],
  },
  {
    title: 'Ready for review',
    items: [
      'Draft v7 has full citation coverage',
      'Task bundle has linked outputs',
      'Recent timeline entries are healthy',
    ],
  },
  {
    title: 'Can wait',
    items: [
      'Older timeline noise',
      'Resolved critiques without downstream impact',
      'Metrics that belong in rollups, not hero surfaces',
    ],
  },
];

const teamRoles = [
  { role: 'Maintainer', users: '3', permissions: 'Review requests, advance gate, assign work' },
  { role: 'Reviewer', users: '4', permissions: 'Critique claims, inspect provenance, resolve findings' },
  { role: 'Contributor', users: '9', permissions: 'Create evidence, claims, drafts, and requests' },
];

const componentGroups = [
  {
    title: 'Shell and navigation',
    items: ['Sidebar shell', 'Command/search rail', 'Workspace status rail', 'Context breadcrumbs'],
  },
  {
    title: 'Decision surfaces',
    items: ['KPI cluster', 'Alert digest', 'Action queue', 'Gate readiness strip'],
  },
  {
    title: 'Investigation',
    items: ['Evidence result card', 'Artifact comparison panel', 'Provenance drawer', 'Query and filter builder'],
  },
  {
    title: 'Ledgers and forms',
    items: ['Dense review table', 'Task board row', 'Request composer', 'Settings form section'],
  },
];

function screenHref(screenId) {
  return screenId === 'catalog'
    ? '/design-preview/agora-redesign'
    : `/design-preview/agora-redesign/${screenId}`;
}

function TonePill({ tone = 'info', children }) {
  return <span className={`arp-pill arp-pill-${tone}`}>{children}</span>;
}

function MetricCard({ label, value, delta, tone = 'info' }) {
  return (
    <article className={`arp-card arp-metric-card arp-tone-${tone}`}>
      <span className="arp-metric-label">{label}</span>
      <strong className="arp-metric-value">{value}</strong>
      <span className="arp-metric-delta">{delta}</span>
    </article>
  );
}

function Panel({ eyebrow, title, summary, actions, children, tone = 'default' }) {
  return (
    <section className={`arp-card arp-panel arp-panel-${tone}`}>
      <header className="arp-panel-header">
        <div>
          {eyebrow ? <p className="arp-eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
          {summary ? <p className="arp-panel-summary">{summary}</p> : null}
        </div>
        {actions ? <div className="arp-panel-actions">{actions}</div> : null}
      </header>
      {children}
    </section>
  );
}

function SparkBars({ values, tone = 'info' }) {
  return (
    <div className={`arp-sparkbars arp-tone-${tone}`} aria-hidden="true">
      {values.map((value, index) => (
        <span key={`${value}-${index}`} style={{ height: `${value}%` }} />
      ))}
    </div>
  );
}

function WorkspaceCard({ workspace }) {
  return (
    <article className="arp-card arp-workspace-card">
      <div className="arp-workspace-header">
        <div>
          <p className="arp-overline">{workspace.phase}</p>
          <h3>{workspace.name}</h3>
        </div>
        <TonePill tone={workspace.blockers === 'Stable' ? 'success' : workspace.blockers === 'Needs setup' ? 'warning' : 'danger'}>
          {workspace.blockers}
        </TonePill>
      </div>
      <p className="arp-workspace-summary">{workspace.summary}</p>
      <div className="arp-meta-row">
        <span>Owner: {workspace.owner}</span>
        <span>Maintainer-first routing</span>
      </div>
      <div className="arp-tag-row">
        {workspace.signals.map((signal) => (
          <TonePill key={signal} tone="info">
            {signal}
          </TonePill>
        ))}
      </div>
    </article>
  );
}

function LedgerList({ rows, tone = 'default' }) {
  return (
    <div className={`arp-ledger arp-ledger-${tone}`}>
      {rows.map((row) => (
        <article key={row.title} className="arp-ledger-row">
          <div>
            <strong>{row.title}</strong>
            <p>{row.detail || row.summary}</p>
          </div>
          <div className="arp-ledger-meta">
            {row.owner ? <span>{row.owner}</span> : null}
            {row.priority ? <TonePill tone={row.priority === 'Blocking' ? 'danger' : row.priority === 'High' ? 'warning' : 'info'}>{row.priority}</TonePill> : null}
          </div>
        </article>
      ))}
    </div>
  );
}

function DataTable({ columns, rows }) {
  return (
    <div className="arp-table-wrap">
      <table className="arp-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id || row.role}>
              {columns.map((column) => (
                <td key={column.key}>
                  {column.render ? column.render(row[column.key], row) : row[column.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CatalogScreen() {
  return (
    <div className="arp-screen-grid">
      <Panel
        eyebrow="Packet"
        title="AGORA redesign capture plan"
        summary="This route family exists to support the Figma redesign handoff with deterministic, implementation-ready screens."
        actions={<TonePill tone="success">Public preview routes</TonePill>}
      >
        <div className="arp-kicker-grid">
          <div>
            <span className="arp-kicker-label">Primary audience</span>
            <strong>Maintainers and reviewers</strong>
          </div>
          <div>
            <span className="arp-kicker-label">Design stance</span>
            <strong>Calm, dense, decision-first</strong>
          </div>
          <div>
            <span className="arp-kicker-label">Current issue</span>
            <strong>CRUD console with weak hierarchy</strong>
          </div>
        </div>
      </Panel>

      <Panel
        eyebrow="IA split"
        title="New workspace structure"
        summary="Overview, investigation, research record, operations, governance, and settings are intentionally separated so each screen has a clear job."
      >
        <div className="arp-ia-grid">
          {PRODUCT_NAV.map((group) => (
            <article key={group.title} className="arp-ia-card">
              <h3>{group.title}</h3>
              <ul>
                {group.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </Panel>

      <Panel eyebrow="Capture map" title="Screen routes" summary="Use these routes as individual Figma capture targets.">
        <div className="arp-screen-link-grid">
          {SCREEN_ORDER.filter((screenId) => screenId !== 'catalog').map((screenId) => (
            <Link key={screenId} to={screenHref(screenId)} className="arp-screen-link">
              <span>{SCREEN_LABELS[screenId]}</span>
              <small>{screenHref(screenId)}</small>
            </Link>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function LoginScreen() {
  return (
    <div className="arp-login-layout">
      <Panel eyebrow="Welcome" title="Trace every claim without losing operational clarity." summary="The current login page has the right message, but the first-run path should introduce product structure instead of dropping users into a raw console.">
        <div className="arp-login-hero">
          <div>
            <div className="arp-tag-row">
              <TonePill tone="info">Evidence-first</TonePill>
              <TonePill tone="success">Review-safe</TonePill>
              <TonePill tone="warning">No silent fallback</TonePill>
            </div>
            <h3 className="arp-hero-title">One console for provenance, gate readiness, and review pressure.</h3>
            <p className="arp-hero-copy">
              New users should understand the product from the login screen: what AGORA governs, what the main workflows are, and why maintainers can trust the evidence trail.
            </p>
            <div className="arp-feature-grid">
              <article className="arp-feature-card">
                <strong>Immutable records</strong>
                <p>Every artifact version, draft revision, and citation resolves to a deterministic source.</p>
              </article>
              <article className="arp-feature-card">
                <strong>Operational confidence</strong>
                <p>Requests, rule checks, blockers, and review tasks are summarized before users dive into details.</p>
              </article>
              <article className="arp-feature-card">
                <strong>Maintainer-first control</strong>
                <p>Authority boundaries stay clear while contributors still get fast evidence and draft workflows.</p>
              </article>
            </div>
          </div>
          <aside className="arp-auth-panel">
            <div className="arp-auth-header">
              <p className="arp-overline">Workspace access</p>
              <h4>Authenticate and choose a mode</h4>
            </div>
            <label className="arp-field-label">
              Identity token
              <div className="arp-input-surface">Paste Moltbook token or local JWT</div>
            </label>
            <div className="arp-button-stack">
              <button type="button" className="arp-button arp-button-primary">
                Verify and continue
              </button>
              <button type="button" className="arp-button arp-button-secondary">
                Open local dev session
              </button>
            </div>
            <div className="arp-note-card">
              <strong>First-run guidance</strong>
              <p>Show role-sensitive starting points: open review queue, inspect flagged workspaces, or create the first evidence record.</p>
            </div>
          </aside>
        </div>
      </Panel>
    </div>
  );
}

function PortfolioScreen() {
  return (
    <div className="arp-screen-grid">
      <Panel
        eyebrow="Portfolio command center"
        title="A portfolio view that surfaces action, not just inventory."
        summary="The current projects page lists workspaces, but it does not help maintainers understand what actually needs attention."
        actions={
          <div className="arp-panel-actions">
            <TonePill tone="danger">4 critical workspaces</TonePill>
            <TonePill tone="info">Saved view: Review queue</TonePill>
          </div>
        }
      >
        <div className="arp-metric-grid">
          {portfolioMetrics.map((metric) => (
            <MetricCard key={metric.label} {...metric} />
          ))}
        </div>
      </Panel>

      <div className="arp-two-column">
        <Panel eyebrow="Watchlist" title="Where maintainers should look first">
          <LedgerList
            rows={riskSignals.map((signal) => ({
              title: signal.title,
              detail: signal.meta,
              priority: signal.tone === 'danger' ? 'Blocking' : signal.tone === 'warning' ? 'High' : 'Watch',
            }))}
          />
        </Panel>
        <Panel eyebrow="Signals" title="Operational trend" summary="High-level signal bars replace noisy chart spam.">
          <SparkBars values={[38, 72, 54, 86, 61, 48, 79, 66, 58, 91]} tone="warning" />
          <p className="arp-panel-footnote">Gate pressure is up 12% week over week; evidence gaps remain the main source of drag.</p>
        </Panel>
      </div>

      <Panel eyebrow="Workspaces" title="Priority-ranked workspace cards" summary="Cards carry decision-supporting signals, not just artifact counts.">
        <div className="arp-workspace-grid">
          {workspaceCards.map((workspace) => (
            <WorkspaceCard key={workspace.name} workspace={workspace} />
          ))}
        </div>
      </Panel>
    </div>
  );
}

function WorkspaceOverviewScreen() {
  return (
    <div className="arp-screen-grid">
      <Panel
        eyebrow="Workspace overview"
        title="The workspace home becomes a control tower."
        summary="Blockers, gate readiness, provenance hotspots, and next actions come first. Raw forms move out of the landing surface."
      >
        <div className="arp-metric-grid">
          {overviewMetrics.map((metric) => (
            <MetricCard key={metric.label} {...metric} />
          ))}
        </div>
      </Panel>

      <div className="arp-three-column">
        <Panel eyebrow="Now" title="Blockers and decision queue">
          <LedgerList rows={blockerRows} />
        </Panel>
        <Panel eyebrow="Gate" title="Readiness rail" summary="A single strip shows whether the workspace can move forward and why not.">
          <div className="arp-gate-rail">
            <div className="arp-gate-score">
              <span>Gate readiness</span>
              <strong>62%</strong>
            </div>
            <div className="arp-progress-bar">
              <span style={{ width: '62%' }} />
            </div>
            <ul className="arp-checklist">
              <li>Citation coverage missing in 2 sections</li>
              <li>One blocking critique still open</li>
              <li>Rule check rerun needed after latest draft update</li>
            </ul>
          </div>
        </Panel>
        <Panel eyebrow="Context" title="Recent critical changes">
          <LedgerList
            rows={[
              { title: 'Draft v7 created', detail: 'Added two new citations to section 2', owner: 'Today, 10:12' },
              { title: 'Claim C-18 updated', detail: 'Confidence reduced after critique triage', owner: 'Today, 09:48' },
              { title: 'Sandbox output linked', detail: 'Execution artifact now available for review', owner: 'Today, 09:41' },
            ]}
          />
        </Panel>
      </div>
    </div>
  );
}

function InvestigationScreen() {
  return (
    <div className="arp-screen-grid">
      <div className="arp-investigation-layout">
        <Panel eyebrow="Query builder" title="Investigation filters" summary="Search, artifact type, evidence health, owner, and open-review filters live in one place.">
          <div className="arp-filter-stack">
            <div className="arp-input-surface">Search evidence, artifacts, claims, or logs</div>
            <div className="arp-chip-grid">
              <TonePill tone="info">Artifact type: PDF + Log</TonePill>
              <TonePill tone="warning">Open critiques only</TonePill>
              <TonePill tone="info">Workspace: Claim Validation</TonePill>
              <TonePill tone="success">Saved view: Gate blockers</TonePill>
            </div>
          </div>
        </Panel>

        <Panel eyebrow="Results" title="Evidence clusters" summary="Artifacts, claims, and critiques are grouped into a single investigation result model.">
          <div className="arp-result-stack">
            {investigationResults.map((result) => (
              <article key={result.title} className="arp-card arp-result-card">
                <div>
                  <h3>{result.title}</h3>
                  <p>{result.summary}</p>
                </div>
                <div className="arp-tag-row">
                  {result.tags.map((tag) => (
                    <TonePill key={tag} tone="info">
                      {tag}
                    </TonePill>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </Panel>

        <Panel eyebrow="Selected result" title="Evidence detail and provenance" summary="The drill-down combines artifact preview, linked claims, provenance chain, and actions without forcing modal hopping.">
          <div className="arp-detail-composition">
            <div className="arp-detail-viewer">
              <div className="arp-detail-header">
                <div>
                  <p className="arp-overline">Artifact version AV-204</p>
                  <h3>Seed evidence log</h3>
                </div>
                <TonePill tone="success">Resolvable</TonePill>
              </div>
              <div className="arp-code-block">
                <span>Smoke log start</span>
                <span>smoke-search-token-20260311</span>
                <span>Smoke log finish</span>
              </div>
            </div>
            <div className="arp-provenance-column">
              <div className="arp-provenance-node">
                <strong>Claim C-18</strong>
                <p>Needs more context before review can pass.</p>
              </div>
              <div className="arp-provenance-connector" />
              <div className="arp-provenance-node">
                <strong>Critique CR-4</strong>
                <p>Blocking issue: missing surrounding explanation.</p>
              </div>
              <div className="arp-provenance-connector" />
              <div className="arp-provenance-node">
                <strong>Draft v7</strong>
                <p>Citation appears in section 2 and the review summary.</p>
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function ResearchRecordScreen() {
  return (
    <div className="arp-screen-grid">
      <Panel eyebrow="Research record" title="Claims and drafts belong in one reviewable flow." summary="The redesign combines claim confidence, citation coverage, and manuscript progress so maintainers can review the research record without cross-tab scavenging.">
        <div className="arp-two-column">
          <div className="arp-card arp-record-summary">
            <p className="arp-overline">Draft health</p>
            <h3>Method Audit Draft v7</h3>
            <div className="arp-metric-split">
              <div>
                <strong>83%</strong>
                <span>Citation coverage</span>
              </div>
              <div>
                <strong>2</strong>
                <span>Open review findings</span>
              </div>
              <div>
                <strong>1</strong>
                <span>Section blocked</span>
              </div>
            </div>
          </div>
          <div className="arp-card arp-reading-pane">
            <p className="arp-overline">Draft reader</p>
            <h3>Executive summary</h3>
            <p>
              Claims remain grounded, but section-level review comments should surface directly in the reading flow. Citations need richer inline context and clearer ownership.
            </p>
            <div className="arp-tag-row">
              <TonePill tone="success">12 linked citations</TonePill>
              <TonePill tone="warning">2 unresolved notes</TonePill>
              <TonePill tone="info">Last updated 28m ago</TonePill>
            </div>
          </div>
        </div>
      </Panel>

      <Panel eyebrow="Claim register" title="Claims with confidence and evidence status">
        <DataTable
          columns={[
            { key: 'id', label: 'Claim' },
            { key: 'claim', label: 'Text' },
            {
              key: 'status',
              label: 'Status',
              render: (value) => <TonePill tone={value === 'Review-ready' ? 'success' : value === 'Hypothesis' ? 'info' : 'warning'}>{value}</TonePill>,
            },
            { key: 'evidence', label: 'Evidence' },
          ]}
          rows={researchClaims}
        />
      </Panel>
    </div>
  );
}

function OperationsScreen() {
  return (
    <div className="arp-screen-grid">
      <div className="arp-three-column">
        <Panel eyebrow="Requests" title="Request pipeline">
          <div className="arp-stage-list">
            <div className="arp-stage-card">
              <strong>Queued</strong>
              <span>Repo ingest, PDF ingest</span>
              <TonePill tone="warning">2 items</TonePill>
            </div>
            <div className="arp-stage-card">
              <strong>Running</strong>
              <span>Sandbox execution</span>
              <TonePill tone="info">1 item</TonePill>
            </div>
            <div className="arp-stage-card">
              <strong>Needs action</strong>
              <span>Rule check failure</span>
              <TonePill tone="danger">1 item</TonePill>
            </div>
          </div>
        </Panel>
        <Panel eyebrow="Tasks" title="Maintainer work queue">
          <LedgerList
            rows={[
              { title: 'Resolve critique on Claim C-18', detail: 'Owner: Nir Tzur', priority: 'Blocking' },
              { title: 'Review join request for Reviewer role', detail: 'Owner: Maintainer', priority: 'High' },
              { title: 'Confirm sandbox output provenance', detail: 'Owner: Ops reviewer', priority: 'Watch' },
            ]}
          />
        </Panel>
        <Panel eyebrow="Signal digest" title="Timeline that earns its space">
          <LedgerList rows={operationsTimeline.map((entry) => ({ title: entry.event, detail: `${entry.time} - ${entry.detail}`, priority: entry.tone === 'danger' ? 'Blocking' : entry.tone === 'warning' ? 'High' : 'Watch' }))} />
        </Panel>
      </div>
    </div>
  );
}

function ReviewGovernanceScreen() {
  return (
    <div className="arp-screen-grid">
      <Panel eyebrow="Governance" title="A review surface designed around decisions, not ledgers." summary="Critiques, rule checks, and gate state become a triage workspace with clear priority and ownership.">
        <div className="arp-governance-grid">
          {governanceColumns.map((column) => (
            <article key={column.title} className="arp-card arp-governance-column">
              <h3>{column.title}</h3>
              <ul>
                {column.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </Panel>

      <Panel eyebrow="Rule checks" title="Gate matrix" summary="Compact governance signals replace a raw ledger-first experience.">
        <div className="arp-gate-matrix">
          <div className="arp-gate-cell">
            <span>Citation coverage</span>
            <strong>Fail</strong>
            <small>2 sections missing coverage</small>
          </div>
          <div className="arp-gate-cell">
            <span>Critique status</span>
            <strong>Warn</strong>
            <small>1 blocking critique open</small>
          </div>
          <div className="arp-gate-cell">
            <span>Task completion</span>
            <strong>Pass</strong>
            <small>All required outputs linked</small>
          </div>
          <div className="arp-gate-cell">
            <span>Provenance health</span>
            <strong>Pass</strong>
            <small>Linked versions resolve correctly</small>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function TeamSettingsScreen() {
  return (
    <div className="arp-screen-grid">
      <div className="arp-two-column">
        <Panel eyebrow="Roster" title="Roles and approvals">
          <DataTable
            columns={[
              { key: 'role', label: 'Role' },
              { key: 'users', label: 'Users' },
              { key: 'permissions', label: 'What this role can do' },
            ]}
            rows={teamRoles}
          />
        </Panel>
        <Panel eyebrow="Integrations" title="Settings in grouped, low-friction sections">
          <div className="arp-settings-stack">
            <article className="arp-card arp-settings-card">
              <strong>Identity and access</strong>
              <p>Moltbook verification, local dev access, and approval routing live in one section.</p>
            </article>
            <article className="arp-card arp-settings-card">
              <strong>Evidence retention</strong>
              <p>Artifact serving, signed URLs, and provenance policy are visible without leaking implementation details.</p>
            </article>
            <article className="arp-card arp-settings-card">
              <strong>Operational defaults</strong>
              <p>Saved views, default filters, and density mode give repeat users faster scanning paths.</p>
            </article>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function SystemScreen() {
  return (
    <div className="arp-screen-grid">
      <Panel eyebrow="Component system" title="Design system foundations" summary="The product should feel like one intentional system instead of many stitched surfaces.">
        <div className="arp-ia-grid">
          {componentGroups.map((group) => (
            <article key={group.title} className="arp-ia-card">
              <h3>{group.title}</h3>
              <ul>
                {group.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </Panel>

      <div className="arp-two-column">
        <Panel eyebrow="Tokens" title="Visual direction">
          <div className="arp-token-grid">
            <div className="arp-token-card">
              <span>Typography</span>
              <strong>Display serif + operational sans</strong>
            </div>
            <div className="arp-token-card">
              <span>Spacing</span>
              <strong>8px base, compact dense mode</strong>
            </div>
            <div className="arp-token-card">
              <span>Color roles</span>
              <strong>Ink, surface, attention, governance, success</strong>
            </div>
            <div className="arp-token-card">
              <span>Chart palette</span>
              <strong>Muted categorical, alert color reserved for exceptions</strong>
            </div>
          </div>
        </Panel>
        <Panel eyebrow="Responsive" title="Behavior by breakpoint">
          <ul className="arp-checklist">
            <li>Desktop: full sidebar, split-pane investigation, dense tables.</li>
            <li>Laptop: keep command rail visible, collapse secondary cards earlier.</li>
            <li>Tablet: turn split panes into stacked cards with sticky action rail.</li>
            <li>Mobile: prioritize watchlist, queue, and detail drawers over raw ledgers.</li>
          </ul>
        </Panel>
      </div>
    </div>
  );
}

function renderScreen(screenId) {
  if (screenId === 'login') return <LoginScreen />;
  if (screenId === 'portfolio') return <PortfolioScreen />;
  if (screenId === 'workspace-overview') return <WorkspaceOverviewScreen />;
  if (screenId === 'investigation') return <InvestigationScreen />;
  if (screenId === 'research-record') return <ResearchRecordScreen />;
  if (screenId === 'operations') return <OperationsScreen />;
  if (screenId === 'review-governance') return <ReviewGovernanceScreen />;
  if (screenId === 'team-settings') return <TeamSettingsScreen />;
  if (screenId === 'system') return <SystemScreen />;
  return <CatalogScreen />;
}

export default function AgoraRedesignPage() {
  const { screenId: routeScreenId } = useParams();
  const screenId = SCREEN_ORDER.includes(routeScreenId) ? routeScreenId : 'catalog';

  return (
    <div className="arp-root">
      <aside className="arp-sidebar">
        <div className="arp-brand">
          <span className="arp-brand-mark">AG</span>
          <div>
            <p className="arp-overline">Figma capture preview</p>
            <h1>AGORA Redesign</h1>
          </div>
        </div>

        <div className="arp-sidebar-block">
          <span className="arp-kicker-label">Screen set</span>
          <nav className="arp-preview-nav">
            {SCREEN_ORDER.map((item) => (
              <Link key={item} to={screenHref(item)} className={`arp-preview-link ${screenId === item ? 'active' : ''}`}>
                {SCREEN_LABELS[item]}
              </Link>
            ))}
          </nav>
        </div>

        <div className="arp-sidebar-block">
          <span className="arp-kicker-label">Product navigation</span>
          <div className="arp-sidebar-groups">
            {PRODUCT_NAV.map((group) => (
              <article key={group.title}>
                <strong>{group.title}</strong>
                <ul>
                  {group.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </div>
      </aside>

      <div className="arp-main">
        <header className="arp-topbar">
          <div>
            <p className="arp-overline">Screen</p>
            <h2>{SCREEN_LABELS[screenId]}</h2>
          </div>
          <div className="arp-tag-row">
            <TonePill tone="info">Maintainer-first</TonePill>
            <TonePill tone="success">Decision-oriented</TonePill>
            <TonePill tone="warning">Capture-ready</TonePill>
          </div>
        </header>

        <main className="arp-canvas">{renderScreen(screenId)}</main>
      </div>
    </div>
  );
}
