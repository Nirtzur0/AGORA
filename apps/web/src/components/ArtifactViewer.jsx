import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { ArtifactTypeIcon, VersionChip, CopyButton } from './Atoms';
import './ArtifactViewer.css';

/**
 * ArtifactViewer - Comprehensive artifact viewer with type-specific rendering
 * Supports PDF (text extraction), repo (file tree), log, dataset, draft, config
 */
export default function ArtifactViewer({ artifactId, versionId, onClose }) {
  const [artifact, setArtifact] = useState(null);
  const [version, setVersion] = useState(null);
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // For repo artifacts
  const [selectedFile, setSelectedFile] = useState(null);
  // For PDF artifacts
  const [selectedPage, setSelectedPage] = useState(1);

  useEffect(() => {
    loadArtifact();
  }, [artifactId, versionId]);

  const loadArtifact = async () => {
    try {
      setLoading(true);
      const artifactData = await apiClient.getArtifact(artifactId);
      setArtifact(artifactData);

      if (versionId) {
        const contentData = await apiClient.getArtifactVersionContent(versionId);
        setContent(contentData);
        
        // If repo, set first file as selected
        if (artifactData.type === 'repo' && contentData.files && contentData.files.length > 0) {
          setSelectedFile(contentData.files[0].path);
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="artifact-viewer-loading">Loading artifact...</div>;
  if (error) return <div className="artifact-viewer-error">Error: {error}</div>;
  if (!artifact) return <div className="artifact-viewer-empty">No artifact found</div>;

  return (
    <div className="artifact-viewer">
      <div className="artifact-viewer-header">
        <div className="artifact-viewer-title">
          <ArtifactTypeIcon type={artifact.type} />
          <span className="artifact-viewer-name">
            {artifact.metadata?.title || artifact.short_id}
          </span>
          {version && <VersionChip version={version.version} />}
        </div>
        <div className="artifact-viewer-actions">
          <CopyButton text={artifact.id} label="Copy ID" />
          {onClose && (
            <button className="artifact-viewer-close" onClick={onClose}>
              ✕
            </button>
          )}
        </div>
      </div>

      <div className="artifact-viewer-content">
        {artifact.type === 'pdf' && <PDFViewer content={content} page={selectedPage} onPageChange={setSelectedPage} />}
        {artifact.type === 'repo' && <RepoViewer content={content} selectedFile={selectedFile} onFileSelect={setSelectedFile} />}
        {artifact.type === 'log' && <LogViewer content={content} />}
        {artifact.type === 'dataset' && <DatasetViewer content={content} />}
        {artifact.type === 'draft' && <DraftViewer content={content} />}
        {artifact.type === 'config' && <ConfigViewer content={content} />}
        {!['pdf', 'repo', 'log', 'dataset', 'draft', 'config'].includes(artifact.type) && (
          <div className="artifact-viewer-unsupported">
            Viewer for type "{artifact.type}" not implemented
          </div>
        )}
      </div>
    </div>
  );
}

function PDFViewer({ content, page, onPageChange }) {
  if (!content || !content.pages) {
    return <div className="viewer-empty">No PDF content available</div>;
  }

  const totalPages = content.pages.length;
  const currentPage = content.pages[page - 1];

  return (
    <div className="pdf-viewer">
      <div className="pdf-viewer-controls">
        <button 
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page === 1}
        >
          ← Previous
        </button>
        <span className="pdf-viewer-page-info">
          Page {page} of {totalPages}
        </span>
        <button 
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          disabled={page === totalPages}
        >
          Next →
        </button>
      </div>
      <div className="pdf-viewer-text">
        <pre>{currentPage?.text || 'No text extracted for this page'}</pre>
      </div>
    </div>
  );
}

function RepoViewer({ content, selectedFile, onFileSelect }) {
  if (!content || !content.files) {
    return <div className="viewer-empty">No repository content available</div>;
  }

  const selectedFileData = content.files.find(f => f.path === selectedFile);

  return (
    <div className="repo-viewer">
      <div className="repo-viewer-tree">
        <h4>Files</h4>
        {content.files.map((file) => (
          <div 
            key={file.path}
            className={`repo-file-item ${selectedFile === file.path ? 'active' : ''}`}
            onClick={() => onFileSelect(file.path)}
          >
            {file.path}
          </div>
        ))}
      </div>
      <div className="repo-viewer-content">
        {selectedFileData ? (
          <>
            <div className="repo-file-header">
              <strong>{selectedFileData.path}</strong>
            </div>
            <pre className="repo-file-content">{selectedFileData.content}</pre>
          </>
        ) : (
          <div className="viewer-empty">Select a file to view</div>
        )}
      </div>
    </div>
  );
}

function LogViewer({ content }) {
  if (!content || !content.text) {
    return <div className="viewer-empty">No log content available</div>;
  }

  return (
    <div className="log-viewer">
      <pre className="log-viewer-text">{content.text}</pre>
    </div>
  );
}

function DatasetViewer({ content }) {
  if (!content || !content.rows) {
    return <div className="viewer-empty">No dataset content available</div>;
  }

  const columns = content.columns || Object.keys(content.rows[0] || {});
  const rows = content.rows.slice(0, 100); // Show first 100 rows

  return (
    <div className="dataset-viewer">
      <div className="dataset-viewer-info">
        Showing {rows.length} of {content.total_rows || rows.length} rows
      </div>
      <table className="dataset-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              {columns.map((col) => (
                <td key={col}>{String(row[col] ?? '')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DraftViewer({ content }) {
  if (!content || !content.text) {
    return <div className="viewer-empty">No draft content available</div>;
  }

  return (
    <div className="draft-viewer">
      <div className="draft-viewer-markdown">
        {content.text}
      </div>
    </div>
  );
}

function ConfigViewer({ content }) {
  if (!content) {
    return <div className="viewer-empty">No config content available</div>;
  }

  return (
    <div className="config-viewer">
      <pre className="config-viewer-json">
        {JSON.stringify(content, null, 2)}
      </pre>
    </div>
  );
}
