import React from 'react';
import { SectionCard } from '../../components/Layout';
import { CRITIQUE_SEVERITIES, CRITIQUE_STATUSES } from './constants';
import { CritiqueCard, EmptyState, humanize } from './shared';

export default function CritiquesTab({
  workspaceId,
  claims,
  allArtifactVersions,
  critiques,
  critiqueForm,
  setCritiqueForm,
  runAction,
  createCritique,
  updateCritique,
}) {
  return (
    <div className="workspace-panel-grid">
      <SectionCard eyebrow="Review" title="Create critique">
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            void runAction(() => createCritique(workspaceId, critiqueForm), 'Critique created');
          }}
        >
          <select className="select-input" value={critiqueForm.target_type} onChange={(event) => setCritiqueForm((current) => ({ ...current, target_type: event.target.value }))}>
            <option value="claim">Claim</option>
            <option value="artifact_version">Artifact version</option>
          </select>
          <select className="select-input" value={critiqueForm.target_id} onChange={(event) => setCritiqueForm((current) => ({ ...current, target_id: event.target.value }))}>
            <option value="">Select target</option>
            {(critiqueForm.target_type === 'claim' ? claims : allArtifactVersions).map((target) => (
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
        {critiques.length ? (
          <div className="stack">
            {critiques.map((critique) => (
              <CritiqueCard key={critique.id} critique={critique} statuses={CRITIQUE_STATUSES} onUpdate={(payload) => runAction(() => updateCritique(critique.id, payload), 'Critique updated')} />
            ))}
          </div>
        ) : (
          <EmptyState title="No critiques yet" body="Create critiques against claims or artifact versions to capture review pressure." />
        )}
      </SectionCard>
    </div>
  );
}
