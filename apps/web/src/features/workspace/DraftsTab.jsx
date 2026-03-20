import React from 'react';
import { SectionCard } from '../../components/Layout';
import { DraftMarkdown, EmptyState, StatusPill } from './shared';

export default function DraftsTab({
  workspaceId,
  drafts,
  versionsByArtifact,
  selectedDraftId,
  setSelectedDraftId,
  selectedDraftContent,
  loadingDraft,
  draftForm,
  setDraftForm,
  draftVersionForm,
  setDraftVersionForm,
  runAction,
  createDraft,
  createDraftVersion,
  openEvidence,
  gateStatus,
}) {
  const selectedDraft = drafts.find((draft) => draft.id === selectedDraftId) || null;

  return (
    <div className="workspace-panel-grid">
      <SectionCard eyebrow="Draft lifecycle" title="Create draft">
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            void runAction(
              async () => {
                const draft = await createDraft(workspaceId, draftForm.title);
                if (draftForm.content.trim()) {
                  await createDraftVersion(draft.id, draftForm.content);
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
            void runAction(async () => {
              await createDraftVersion(draftVersionForm.draftId, draftVersionForm.content);
              setDraftVersionForm((current) => ({ ...current, content: '' }));
            }, 'Draft version created');
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

      <SectionCard eyebrow="Governance" title="Finalization status">
        <div className="stack">
          <StatusPill
            label={gateStatus?.gate_required ? `Gate ${gateStatus.gate_status || 'unknown'}` : 'No gate required'}
            tone={gateStatus?.can_advance ? 'good' : gateStatus?.gate_required ? 'warning' : 'info'}
          />
          <span className="muted-copy">Draft finalization remains orchestrator-owned. Use this console to inspect readiness, not to finalize directly.</span>
          {gateStatus?.reasons?.length ? (
            <ul className="bullet-list">
              {gateStatus.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
        </div>
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
                  <small>{(versionsByArtifact[draft.id] || []).length} versions</small>
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
                      label={`Latest version · v${(versionsByArtifact[selectedDraft.id] || [])[0]?.version || 0}`}
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
}
