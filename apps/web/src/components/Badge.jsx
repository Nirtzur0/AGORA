import React from 'react';
import './Badge.css';

export function PhaseBadge({ phase }) {
  const phaseTone = {
    INIT: 'muted',
    LIT_REVIEW: 'info',
    CLAIM_VALIDATION: 'info',
    HYPOTHESIS_PLANNING: 'warning',
    EXPERIMENTATION: 'warning',
    SYNTHESIS: 'success',
    INTERNAL_REVIEW: 'warning',
    FINALIZED: 'success',
    ARCHIVED: 'muted',
  };

  return (
    <span className={`badge phase-badge badge--tone-${phaseTone[phase] || 'muted'}`}>
      {phase}
    </span>
  );
}

export function StatusBadge({ status }) {
  const statusTone = {
    pass: 'success',
    fail: 'error',
    running: 'info',
    blocked: 'warning',
    pending: 'muted',
    open: 'warning',
    resolved: 'success',
    deferred: 'muted',
  };

  return (
    <span className={`badge status-badge badge--tone-${statusTone[status] || 'muted'}`}>
      {status}
    </span>
  );
}

export function SeverityBadge({ severity }) {
  const severityTone = {
    info: 'info',
    minor: 'warning',
    major: 'warning',
    blocking: 'error',
  };

  return (
    <span className={`badge severity-badge badge--tone-${severityTone[severity] || 'muted'}`}>
      {severity}
    </span>
  );
}
