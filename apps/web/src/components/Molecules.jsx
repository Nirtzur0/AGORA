import React, { useState } from 'react';
import './Molecules.css';

/**
 * FilterBar - Reusable filter component for lists
 */
export function FilterBar({ filters, onFilterChange, onClear }) {
  return (
    <div className="filter-bar">
      {filters.map((filter) => (
        <div key={filter.id} className="filter-item">
          <label className="filter-label">{filter.label}</label>
          {filter.type === 'text' && (
            <input
              type="text"
              className="filter-input"
              value={filter.value || ''}
              onChange={(e) => onFilterChange(filter.id, e.target.value)}
              placeholder={filter.placeholder}
            />
          )}
          {filter.type === 'select' && (
            <select
              className="filter-select"
              value={filter.value || ''}
              onChange={(e) => onFilterChange(filter.id, e.target.value)}
            >
              <option value="">All</option>
              {filter.options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}
          {filter.type === 'multiselect' && (
            <select
              className="filter-select"
              multiple
              value={filter.value || []}
              onChange={(e) => {
                const selected = Array.from(e.target.selectedOptions).map(o => o.value);
                onFilterChange(filter.id, selected);
              }}
            >
              {filter.options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}
          {filter.type === 'pills' && (
            <div
              className="filter-pills"
              role="group"
              aria-label={filter.label}
            >
              {(() => {
                const isMulti = Boolean(filter.multiple);
                const selected = isMulti
                  ? (Array.isArray(filter.value) ? filter.value : [])
                  : (filter.value ? [filter.value] : []);

                const clearValue = isMulti ? [] : '';
                const isAll = selected.length === 0;

                const toggle = (value) => {
                  if (!isMulti) {
                    onFilterChange(filter.id, selected[0] === value ? '' : value);
                    return;
                  }
                  if (selected.includes(value)) {
                    onFilterChange(filter.id, selected.filter(v => v !== value));
                    return;
                  }
                  onFilterChange(filter.id, [...selected, value]);
                };

                return (
                  <>
                    <button
                      type="button"
                      className={`filter-pill ${isAll ? 'selected' : ''}`}
                      aria-pressed={isAll}
                      onClick={() => onFilterChange(filter.id, clearValue)}
                      title="All"
                    >
                      All
                    </button>
                    {filter.options.map((opt) => {
                      const isSelected = selected.includes(opt.value);
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          className={`filter-pill ${isSelected ? 'selected' : ''}`}
                          aria-pressed={isSelected}
                          onClick={() => toggle(opt.value)}
                          title={opt.label}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </>
                );
              })()}
            </div>
          )}
          {filter.type === 'toggle' && (
            <label className="filter-toggle">
              <input
                type="checkbox"
                checked={filter.value || false}
                onChange={(e) => onFilterChange(filter.id, e.target.checked)}
              />
              <span>{filter.toggleLabel || 'Enabled'}</span>
            </label>
          )}
        </div>
      ))}
      {onClear && (
        <button className="filter-clear-button" onClick={onClear}>
          Clear Filters
        </button>
      )}
    </div>
  );
}

/**
 * SplitPane - Reusable split layout (left list / right details)
 */
export function SplitPane({ left, right, leftWidth = '300px' }) {
  return (
    <div className="split-pane">
      <div className="split-pane-left" style={{ width: leftWidth }}>
        {left}
      </div>
      <div className="split-pane-right">
        {right}
      </div>
    </div>
  );
}

/**
 * JsonViewer - Pretty JSON display with expand/collapse
 */
export function JsonViewer({ data, collapsed = false }) {
  const [isCollapsed, setIsCollapsed] = useState(collapsed);

  if (!data) return <p className="json-viewer-empty">No data</p>;

  return (
    <div className="json-viewer">
      <div className="json-viewer-header">
        <button 
          className="json-viewer-toggle"
          onClick={() => setIsCollapsed(!isCollapsed)}
        >
          {isCollapsed ? '▶ Expand' : '▼ Collapse'}
        </button>
      </div>
      {!isCollapsed && (
        <pre className="json-viewer-content">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}

/**
 * DiffViewer - Line-based diff viewer for comparing two text versions
 */
export function DiffViewer({ oldText, newText, oldLabel = 'Old', newLabel = 'New' }) {
  const computeDiff = (oldText, newText) => {
    const oldLines = oldText.split('\n');
    const newLines = newText.split('\n');
    const diff = [];

    let i = 0, j = 0;
    while (i < oldLines.length || j < newLines.length) {
      if (i < oldLines.length && j < newLines.length && oldLines[i] === newLines[j]) {
        diff.push({ type: 'same', line: oldLines[i], oldNum: i + 1, newNum: j + 1 });
        i++;
        j++;
      } else if (i < oldLines.length && (j >= newLines.length || oldLines[i] !== newLines[j])) {
        diff.push({ type: 'removed', line: oldLines[i], oldNum: i + 1 });
        i++;
      } else if (j < newLines.length) {
        diff.push({ type: 'added', line: newLines[j], newNum: j + 1 });
        j++;
      }
    }

    return diff;
  };

  const diff = computeDiff(oldText || '', newText || '');

  return (
    <div className="diff-viewer">
      <div className="diff-viewer-header">
        <span className="diff-label removed-label">{oldLabel}</span>
        <span className="diff-label added-label">{newLabel}</span>
      </div>
      <div className="diff-viewer-content">
        {diff.map((item, idx) => (
          <div key={idx} className={`diff-line diff-line-${item.type}`}>
            <span className="diff-line-nums">
              <span className="diff-line-num">{item.oldNum || ''}</span>
              <span className="diff-line-num">{item.newNum || ''}</span>
            </span>
            <span className="diff-line-content">{item.line}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * MarkdownViewer - Renders markdown with custom transforms for [[claim:...]] and [[cite:...]]
 */
export function MarkdownViewer({ content, onClaimClick, onCiteClick }) {
  // Parse markdown and extract claim/cite markers
  const parseContent = (text) => {
    const parts = [];
    const claimRegex = /\[\[claim:([^\]]+)\]\]/g;
    const citeRegex = /\[\[cite:([^|]+)\|([^\]]+)\]\]/g;
    
    let lastIndex = 0;
    const markers = [];
    
    // Find all claim markers
    let match;
    while ((match = claimRegex.exec(text)) !== null) {
      markers.push({ type: 'claim', index: match.index, length: match[0].length, claimId: match[1] });
    }
    
    // Find all cite markers
    while ((match = citeRegex.exec(text)) !== null) {
      markers.push({ 
        type: 'cite', 
        index: match.index, 
        length: match[0].length, 
        artifactVersionId: match[1], 
        location: match[2] 
      });
    }
    
    // Sort by index
    markers.sort((a, b) => a.index - b.index);
    
    // Build parts
    markers.forEach((marker) => {
      if (marker.index > lastIndex) {
        parts.push({ type: 'text', content: text.substring(lastIndex, marker.index) });
      }
      parts.push(marker);
      lastIndex = marker.index + marker.length;
    });
    
    if (lastIndex < text.length) {
      parts.push({ type: 'text', content: text.substring(lastIndex) });
    }
    
    return parts;
  };

  const parts = parseContent(content || '');

  return (
    <div className="markdown-viewer">
      {parts.map((part, idx) => {
        if (part.type === 'text') {
          return <span key={idx} dangerouslySetInnerHTML={{ __html: part.content }} />;
        } else if (part.type === 'claim') {
          return (
            <button
              key={idx}
              className="claim-chip"
              onClick={() => onClaimClick && onClaimClick(part.claimId)}
              title={`Claim: ${part.claimId}`}
            >
              📌 Claim
            </button>
          );
        } else if (part.type === 'cite') {
          return (
            <button
              key={idx}
              className="cite-chip"
              onClick={() => onCiteClick && onCiteClick(part.artifactVersionId, part.location)}
              title={`${part.artifactVersionId}: ${part.location}`}
            >
              📎 Cite
            </button>
          );
        }
        return null;
      })}
    </div>
  );
}
