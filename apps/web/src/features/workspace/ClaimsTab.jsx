import React from 'react';
import { SectionCard } from '../../components/Layout';
import { EmptyState, StatusPill, humanize, toneForStatus } from './shared';

export default function ClaimsTab({
  workspaceId,
  claims,
  allArtifactVersions,
  claimForm,
  setClaimForm,
  claimEvidenceForm,
  setClaimEvidenceForm,
  runAction,
  createClaim,
  addEvidenceToClaim,
  openEvidence,
}) {
  return (
    <div className="workspace-panel-grid">
      <SectionCard eyebrow="Grounding" title="Create claim">
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            void runAction(
              async () => {
                await createClaim(workspaceId, claimForm);
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
              () => addEvidenceToClaim(claimEvidenceForm.claimId, {
                artifact_version_id: claimEvidenceForm.artifactVersionId,
                location: claimEvidenceForm.location,
              }),
              'Evidence added to claim'
            );
          }}
        >
          <select className="select-input" value={claimEvidenceForm.claimId} onChange={(event) => setClaimEvidenceForm((current) => ({ ...current, claimId: event.target.value }))}>
            <option value="">Select claim</option>
            {claims.map((claim) => (
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
        {claims.length ? (
          <div className="stack">
            {claims.map((claim) => (
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
}
