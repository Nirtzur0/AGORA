import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';

export function humanize(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function formatTimestamp(value) {
  if (!value) return 'Unknown';
  return new Date(value).toLocaleString();
}

export function toneForStatus(status) {
  const normalized = String(status || '').toLowerCase();
  if (['pass', 'passed', 'healthy', 'stable', 'resolved', 'completed', 'approved', 'active'].includes(normalized)) return 'good';
  if (['fail', 'failed', 'blocking', 'rejected'].includes(normalized)) return 'danger';
  if (['warning', 'open', 'blocked', 'deferred', 'in_progress', 'pending'].includes(normalized)) return 'warning';
  return 'info';
}

export function JsonBlock({ value }) {
  if (!value) return null;
  return <pre className="console-json">{JSON.stringify(value, null, 2)}</pre>;
}

export function EmptyState({ title, body }) {
  return (
    <div className="empty-block">
      <strong>{title}</strong>
      <span>{body}</span>
    </div>
  );
}

export function StatusPill({ label, tone }) {
  return <span className={`pill status-${tone}`}>{label}</span>;
}

export function MetricTile({ label, value, tone = 'info' }) {
  return (
    <div className={`metric-panel metric-panel-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function InsightList({ items, emptyTitle, emptyBody }) {
  if (!items.length) {
    return <EmptyState title={emptyTitle} body={emptyBody} />;
  }

  return (
    <div className="stack">
      {items.map((item) => (
        <div key={item.id} className="insight-row">
          <div>
            <strong>{item.title}</strong>
            {item.body ? <p>{item.body}</p> : null}
          </div>
          {item.meta ? <span>{item.meta}</span> : null}
        </div>
      ))}
    </div>
  );
}

export function DraftMarkdown({ content, onOpenEvidence }) {
  const citationRegex = /\[\[cite:([^|]+)\|([^\]]+)\]\]/g;
  const parts = [];
  let cursor = 0;
  let match;

  while ((match = citationRegex.exec(content || '')) !== null) {
    if (match.index > cursor) {
      parts.push({ type: 'markdown', value: content.slice(cursor, match.index) });
    }
    parts.push({ type: 'citation', artifactVersionId: match[1], location: match[2] });
    cursor = match.index + match[0].length;
  }

  if (cursor < (content || '').length) {
    parts.push({ type: 'markdown', value: content.slice(cursor) });
  }

  return (
    <div className="draft-markdown">
      {parts.map((part, index) =>
        part.type === 'citation' ? (
          <button
            key={`${part.artifactVersionId}-${index}`}
            type="button"
            className="cite-button"
            onClick={() => onOpenEvidence(part.artifactVersionId, part.location)}
          >
            Citation · {part.location}
          </button>
        ) : (
          <ReactMarkdown key={`m-${index}`}>{part.value}</ReactMarkdown>
        )
      )}
    </div>
  );
}

export function CritiqueCard({ critique, statuses, onUpdate }) {
  const [status, setStatus] = useState(critique.status);
  const [resolutionStatus, setResolutionStatus] = useState('accepted_fix');
  const [rationale, setRationale] = useState('');

  return (
    <div className="list-card">
      <div className="workspace-inline-row">
        <div>
          <strong>{humanize(critique.target_type)}</strong>
          <div className="metadata-row">
            <span>{critique.target_id}</span>
            <span>{formatTimestamp(critique.created_at)}</span>
          </div>
        </div>
        <div className="workspace-inline-row">
          <StatusPill label={critique.severity} tone={toneForStatus(critique.severity)} />
          <StatusPill label={critique.status} tone={toneForStatus(critique.status)} />
        </div>
      </div>
      <p>{critique.message}</p>
      <div className="stack">
        <select className="select-input" value={status} onChange={(event) => setStatus(event.target.value)}>
          {statuses.map((item) => (
            <option key={item} value={item}>
              {humanize(item)}
            </option>
          ))}
        </select>
        <select className="select-input" value={resolutionStatus} onChange={(event) => setResolutionStatus(event.target.value)}>
          <option value="accepted_fix">Accepted fix</option>
          <option value="deferred_with_rationale">Deferred with rationale</option>
          <option value="rejected_with_evidence">Rejected with evidence</option>
        </select>
        <textarea className="text-area" value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Resolution rationale" />
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() =>
            onUpdate({
              status,
              resolution: rationale.trim()
                ? {
                    status: resolutionStatus,
                    rationale,
                  }
                : undefined,
            })
          }
        >
          Update critique
        </button>
      </div>
      {critique.resolution ? <JsonBlock value={critique.resolution} /> : null}
    </div>
  );
}

export function TaskCard({ task, currentAgentId, statuses, onUpdate }) {
  const [status, setStatus] = useState(task.status);
  const [notes, setNotes] = useState(task.payload?.notes || '');
  const [resultType, setResultType] = useState('artifact');
  const [resultId, setResultId] = useState('');
  const isAssignee = task.assignee_agent_id === currentAgentId;

  return (
    <div className="list-card">
      <div className="workspace-inline-row">
        <div>
          <strong>{humanize(task.type)}</strong>
          <div className="metadata-row">
            <span>Assignee {task.assignee_agent_id || 'Unassigned'}</span>
            <span>{formatTimestamp(task.created_at)}</span>
          </div>
        </div>
        <StatusPill label={task.status} tone={toneForStatus(task.status)} />
      </div>
      <JsonBlock value={task.payload} />
      {isAssignee ? (
        <div className="stack">
          <select className="select-input" value={status} onChange={(event) => setStatus(event.target.value)}>
            {statuses.map((taskStatus) => (
              <option key={taskStatus} value={taskStatus}>
                {humanize(taskStatus)}
              </option>
            ))}
          </select>
          <textarea className="text-area" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Notes or blockers" />
          <div className="workspace-inline-row">
            <select className="select-input" value={resultType} onChange={(event) => setResultType(event.target.value)}>
              <option value="artifact">Artifact</option>
              <option value="claim">Claim</option>
              <option value="draft">Draft</option>
              <option value="critique">Critique</option>
              <option value="log">Log</option>
            </select>
            <input className="text-input" placeholder="Result item id (optional)" value={resultId} onChange={(event) => setResultId(event.target.value)} />
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() =>
              onUpdate({
                status,
                notes,
                result_links: resultId.trim()
                  ? [
                      {
                        type: resultType,
                        id: resultId.trim(),
                      },
                    ]
                  : undefined,
              })
            }
          >
            Update task
          </button>
        </div>
      ) : (
        <span className="muted-copy">Only explicitly assigned tasks can be updated from the browser console; role-targeted tasks remain read-only here.</span>
      )}
    </div>
  );
}
