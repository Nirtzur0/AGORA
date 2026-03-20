import React from 'react';
import { SectionCard } from '../../components/Layout';
import { EmptyState, JsonBlock, StatusPill, formatTimestamp, humanize, toneForStatus } from './shared';

export default function RuleChecksTab({ ruleChecks }) {
  return (
    <SectionCard eyebrow="Governance" title="Rule-check ledger">
      {ruleChecks.length ? (
        <div className="stack">
          {ruleChecks.map((check, index) => (
            <div key={`${check.rule_name}-${index}`} className="list-card">
              <div className="workspace-inline-row">
                <strong>{check.rule_name}</strong>
                <StatusPill label={check.status} tone={toneForStatus(check.status)} />
              </div>
              <div className="metadata-row">
                <span>{humanize(check.target_type)}</span>
                <span>{formatTimestamp(check.created_at)}</span>
              </div>
              <JsonBlock value={check.details} />
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="No rule checks yet" body="Run a rule check from the requests tab or create a new draft version to generate coverage checks." />
      )}
    </SectionCard>
  );
}
