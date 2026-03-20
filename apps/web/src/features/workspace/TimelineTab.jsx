import React from 'react';
import { SectionCard } from '../../components/Layout';
import { EmptyState, JsonBlock, StatusPill, formatTimestamp, toneForStatus } from './shared';

export default function TimelineTab({ timelineItems }) {
  return (
    <SectionCard eyebrow="Audit trail" title="Events and logs">
      {timelineItems.length ? (
        <div className="stack">
          {timelineItems.map((item) => (
            <div key={`${item.kind}-${item.id}`} className="timeline-card">
              <div className="workspace-inline-row">
                <StatusPill label={item.kind === 'event' ? item.event_type : item.action || item.level || 'log'} tone={toneForStatus(item.level || item.event_type)} />
                <span>{formatTimestamp(item.created_at)}</span>
              </div>
              <div>{item.kind === 'event' ? item.event_type : item.message || item.action}</div>
              <JsonBlock value={item.payload} />
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="No timeline entries" body="Events and logs will appear here as the workspace changes." />
      )}
    </SectionCard>
  );
}
