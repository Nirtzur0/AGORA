import React from 'react';
import { useNavigate } from 'react-router-dom';
import './Atoms.css';

/**
 * IdentityChip - Shows agent name + optional reputation + role
 * Clickable to navigate to agent profile
 */
export function IdentityChip({ agentId, name, reputation, role, onClick }) {
  const navigate = useNavigate();

  const handleClick = () => {
    if (onClick) {
      onClick();
    } else if (agentId) {
      navigate(`/agents/${agentId}`);
    }
  };

  const isHighTrust = reputation && reputation >= 0.8;

  return (
    <span 
      className={`identity-chip ${agentId ? 'clickable' : ''}`}
      onClick={handleClick}
      title={`${name}${reputation !== undefined ? ` (reputation: ${reputation})` : ''}`}
    >
      <span className="identity-name">{name}</span>
      {reputation !== undefined && (
        <span className={`identity-reputation ${isHighTrust ? 'high-trust' : ''}`}>
          {(reputation * 100).toFixed(0)}%
        </span>
      )}
      {role && <span className="identity-role">{role}</span>}
    </span>
  );
}

/**
 * ArtifactTypeIcon - Icon for artifact types
 */
export function ArtifactTypeIcon({ type }) {
  const icons = {
    pdf: '📄',
    code: '💻',
    repo: '📦',
    log: '📋',
    dataset: '📊',
    draft: '📝',
    config: '⚙️'
  };

  return (
    <span className="artifact-type-icon" title={type}>
      {icons[type] || '📎'}
    </span>
  );
}

/**
 * ShortIdChip - Displays artifact short_id (e.g., A5)
 */
export function ShortIdChip({ shortId, onClick }) {
  return (
    <span 
      className={`short-id-chip ${onClick ? 'clickable' : ''}`}
      onClick={onClick}
      title={`Artifact ${shortId}`}
    >
      {shortId}
    </span>
  );
}

/**
 * VersionChip - Displays version number (e.g., v2)
 */
export function VersionChip({ version, onClick }) {
  return (
    <span 
      className={`version-chip ${onClick ? 'clickable' : ''}`}
      onClick={onClick}
      title={`Version ${version}`}
    >
      v{version}
    </span>
  );
}

/**
 * CopyButton - Reusable copy-to-clipboard button
 */
export function CopyButton({ text, label = 'Copy', title }) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <button 
      className="copy-button"
      onClick={handleCopy}
      title={title || `Copy ${label}`}
    >
      {copied ? '✓ Copied' : `📋 ${label}`}
    </button>
  );
}

/**
 * Timestamp - Relative time with absolute UTC tooltip
 */
export function Timestamp({ date, showRelative = true }) {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  
  const getRelativeTime = (date) => {
    const now = new Date();
    const diffMs = now - date;
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSecs < 60) return `${diffSecs}s ago`;
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
    return `${Math.floor(diffDays / 365)}y ago`;
  };

  const absoluteTime = dateObj.toISOString();
  const displayTime = showRelative ? getRelativeTime(dateObj) : dateObj.toLocaleString();

  return (
    <span className="timestamp" title={absoluteTime}>
      {displayTime}
    </span>
  );
}
