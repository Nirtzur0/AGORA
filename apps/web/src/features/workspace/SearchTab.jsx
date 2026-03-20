import React from 'react';
import { SectionCard } from '../../components/Layout';
import { EmptyState, JsonBlock, StatusPill, humanize } from './shared';

export default function SearchTab({ searchQuery, setSearchQuery, searchResults, onSearch, setProvenanceViewer }) {
  return (
    <div className="workspace-panel-grid">
      <SectionCard eyebrow="Search index" title="Search artifact content">
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            void onSearch(searchQuery.trim());
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
}
