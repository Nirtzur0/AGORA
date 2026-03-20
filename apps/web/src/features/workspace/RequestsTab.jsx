import React from 'react';
import { SectionCard } from '../../components/Layout';
import { EmptyState, JsonBlock, StatusPill, formatTimestamp, toneForStatus } from './shared';

export default function RequestsTab({
  workspaceId,
  artifacts,
  drafts,
  versionsByArtifact,
  logs,
  ruleChecks,
  pdfRequestArtifactId,
  setPdfRequestArtifactId,
  repoRequestForm,
  setRepoRequestForm,
  sandboxForm,
  setSandboxForm,
  ruleCheckDraftVersionId,
  setRuleCheckDraftVersionId,
  runAction,
  requestIngestPdf,
  requestIngestRepo,
  requestRunSandbox,
  runRuleCheck,
}) {
  const recentRequestSignals = [
    ...logs
      .filter((log) => String(log.action || log.message || '').toLowerCase().includes('request'))
      .map((log) => ({
        id: log.id,
        title: log.action || log.level || 'request',
        body: log.message || 'Request activity recorded',
        meta: formatTimestamp(log.created_at),
        tone: toneForStatus(log.level || log.action),
        details: log.payload,
      })),
    ...ruleChecks.slice(0, 3).map((check, index) => ({
      id: `rule-${index}-${check.rule_name}`,
      title: check.rule_name,
      body: `Rule check ${check.status}`,
      meta: formatTimestamp(check.created_at),
      tone: toneForStatus(check.status),
      details: check.details,
    })),
  ].slice(0, 6);

  return (
    <div className="workspace-panel-grid">
      <SectionCard eyebrow="Ingestion" title="Request PDF ingestion">
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            void runAction(() => requestIngestPdf(workspaceId, pdfRequestArtifactId), 'PDF ingestion requested');
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
            void runAction(() => requestIngestRepo(workspaceId, repoRequestForm), 'Repository ingest requested');
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
            void runAction(async () => {
              const payload = {
                script_artifact_id: sandboxForm.script_artifact_id,
                image: sandboxForm.image,
                parameters: sandboxForm.parameters ? JSON.parse(sandboxForm.parameters) : undefined,
              };
              await requestRunSandbox(workspaceId, payload);
            }, 'Sandbox run requested');
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
            void runAction(() => runRuleCheck(workspaceId, ruleCheckDraftVersionId), 'Rule check requested');
          }}
        >
          <select className="select-input" value={ruleCheckDraftVersionId} onChange={(event) => setRuleCheckDraftVersionId(event.target.value)}>
            <option value="">Select draft version</option>
            {drafts.flatMap((draft) =>
              (versionsByArtifact[draft.id] || []).map((version) => (
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

      <SectionCard eyebrow="Signals" title="Recent request and governance activity">
        {recentRequestSignals.length ? (
          <div className="stack">
            {recentRequestSignals.map((signal) => (
              <div key={signal.id} className="list-card">
                <div className="workspace-inline-row">
                  <strong>{signal.title}</strong>
                  <StatusPill label={signal.meta} tone={signal.tone} />
                </div>
                <p>{signal.body}</p>
                <JsonBlock value={signal.details} />
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No request activity yet" body="Ingestion, sandbox, and rule-check results will appear here." />
        )}
      </SectionCard>
    </div>
  );
}
