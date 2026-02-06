import React from 'react';
import './Layout.css';

export function AppShell({ children, onLogout }) {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="app-header">
        <div className="header-content">
          <div className="brand">
            <h1 className="app-title">AGORA</h1>
            <span className="app-tagline">Evidence-first research records</span>
          </div>
          <div className="header-actions">
            <span className="user-info">Audit UI</span>
            {onLogout && (
              <button className="btn btn-secondary btn-compact" onClick={onLogout}>
                Log out
              </button>
            )}
          </div>
        </div>
      </header>
      <main id="main" className="app-main">
        {children}
      </main>
    </div>
  );
}

export function PageContainer({ title, children, actions }) {
  return (
    <div className="page-container">
      {(title || actions) && (
        <div className="page-header">
          {title && <h2 className="page-title">{title}</h2>}
          {actions && <div className="page-actions">{actions}</div>}
        </div>
      )}
      <div className="page-content">
        {children}
      </div>
    </div>
  );
}

export function Card({ title, children, actions }) {
  return (
    <div className="card">
      {(title || actions) && (
        <div className="card-header">
          {title && <h3 className="card-title">{title}</h3>}
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      <div className="card-body">
        {children}
      </div>
    </div>
  );
}

export function TabNav({ tabs, activeTab, onTabChange }) {
  return (
    <div className="tab-nav">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => onTabChange(tab.id)}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span className="tab-count">{tab.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}
