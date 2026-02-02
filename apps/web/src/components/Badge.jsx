import React from 'react';
import './Badge.css';

export function PhaseBadge({ phase }) {
  const phaseColors = {
    'INIT': '#6c757d',
    'LIT_REVIEW': '#17a2b8',
    'CLAIM_VALIDATION': '#007bff',
    'HYPOTHESIS_PLANNING': '#6f42c1',
    'EXPERIMENTATION': '#fd7e14',
    'SYNTHESIS': '#20c997',
    'INTERNAL_REVIEW': '#ffc107',
    'FINALIZED': '#28a745',
    'ARCHIVED': '#6c757d'
  };

  return (
    <span className="badge phase-badge" style={{ backgroundColor: phaseColors[phase] || '#6c757d' }}>
      {phase}
    </span>
  );
}

export function StatusBadge({ status }) {
  const statusColors = {
    'pass': '#28a745',
    'fail': '#dc3545',
    'running': '#17a2b8',
    'blocked': '#ffc107',
    'pending': '#6c757d',
    'open': '#ffc107',
    'resolved': '#28a745',
    'deferred': '#6c757d'
  };

  return (
    <span className="badge status-badge" style={{ backgroundColor: statusColors[status] || '#6c757d' }}>
      {status}
    </span>
  );
}

export function SeverityBadge({ severity }) {
  const severityColors = {
    'info': '#17a2b8',
    'minor': '#ffc107',
    'major': '#fd7e14',
    'blocking': '#dc3545'
  };

  return (
    <span className="badge severity-badge" style={{ backgroundColor: severityColors[severity] || '#6c757d' }}>
      {severity}
    </span>
  );
}
