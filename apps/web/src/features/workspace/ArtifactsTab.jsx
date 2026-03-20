import React from 'react';
import { SectionCard } from '../../components/Layout';
import ArtifactViewer from '../../components/ArtifactViewer';
import { ARTIFACT_TYPES } from './constants';
import { EmptyState, StatusPill, humanize } from './shared';

export default function ArtifactsTab({
  workspaceId,
  artifacts,
  versionsByArtifact,
  selectedArtifactId,
  setSelectedArtifactId,
  artifactForm,
  setArtifactForm,
  artifactFile,
  setArtifactFile,
  runAction,
  createArtifact,
  createArtifactVersion,
}) {
  const selectedArtifact = artifacts.find((artifact) => artifact.id === selectedArtifactId) || null;

  return (
    <div className="workspace-panel-grid">
      <SectionCard eyebrow="Registry" title="Create artifact record">
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            void runAction(
              async () => {
                const artifact = await createArtifact(workspaceId, artifactForm.type, {
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
            void runAction(async () => {
              await createArtifactVersion(selectedArtifactId, artifactFile);
              setArtifactFile(null);
            }, 'Artifact version uploaded');
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

      <SectionCard eyebrow="Registry" title="Artifact inventory">
        {artifacts.length ? (
          <div className="stack">
            {artifacts.map((artifact) => (
              <button
                type="button"
                key={artifact.id}
                className={`artifact-summary-card ${artifact.id === selectedArtifactId ? 'active' : ''}`}
                onClick={() => setSelectedArtifactId(artifact.id)}
              >
                <div className="workspace-inline-row">
                  <strong>{artifact.short_id}</strong>
                  <StatusPill label={`${(versionsByArtifact[artifact.id] || []).length} versions`} tone="info" />
                </div>
                <span>{humanize(artifact.type)}</span>
                <small>{artifact.metadata?.title || 'Untitled artifact'}</small>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title="No artifacts yet" body="Create an artifact record, then upload a version to start using the workspace." />
        )}
      </SectionCard>

      <SectionCard eyebrow="Registry" title="Artifact viewer">
        {selectedArtifact ? (
          <ArtifactViewer artifactId={selectedArtifact.id} />
        ) : (
          <EmptyState title="No artifact selected" body="Select an artifact to inspect versions and processed content." />
        )}
      </SectionCard>
    </div>
  );
}
