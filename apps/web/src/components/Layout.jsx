import React from 'react';
import './Layout.css';

export function AppShell({ children }) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-content">
          <h1 className="app-title">AGORA</h1>
          <div className="header-actions">
            <span className="user-info">Multi-Agent Research Platform</span>
          </div>
        </div>
      </header>
      <main className="app-main">
        {children}
      </main>
    </div>
  );
}

export function PageContainer({ title, children }) {
  return (
    <div className="page-container">
      {title && <h2 className="page-title">{title}</h2>}
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
