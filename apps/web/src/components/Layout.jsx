import React from 'react';
import './Layout.css';

export function AppShell({ children, onLogout }) {
  return (
    <div className="shell">
      <a className="shell-skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="shell-header">
        <div className="shell-branding">
          <div className="shell-brand-mark">AG</div>
          <div>
            <p className="shell-overline">Evidence-first workspace console</p>
            <h1 className="shell-title">AGORA</h1>
          </div>
        </div>
        <div className="shell-header-actions">
          <span className="shell-status-pill">Audit + authoring</span>
          {onLogout ? (
            <button className="btn btn-secondary" onClick={onLogout}>
              Log out
            </button>
          ) : null}
        </div>
      </header>
      <main id="main-content" className="shell-main">
        {children}
      </main>
    </div>
  );
}

export function SectionCard({ eyebrow, title, actions, children, tone = 'default' }) {
  return (
    <section className={`section-card section-card-${tone}`}>
      {(eyebrow || title || actions) && (
        <div className="section-card-header">
          <div>
            {eyebrow ? <p className="section-card-eyebrow">{eyebrow}</p> : null}
            {title ? <h2 className="section-card-title">{title}</h2> : null}
          </div>
          {actions ? <div className="section-card-actions">{actions}</div> : null}
        </div>
      )}
      <div className="section-card-body">{children}</div>
    </section>
  );
}

export function TabNav({ tabs, activeTab, onTabChange }) {
  return (
    <div className="console-tab-nav" role="tablist" aria-label="Workspace tabs">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={tab.id === activeTab}
          className={`console-tab ${tab.id === activeTab ? 'active' : ''}`}
          onClick={() => onTabChange(tab.id)}
        >
          <span>{tab.label}</span>
          {tab.count !== undefined ? <span className="console-tab-count">{tab.count}</span> : null}
        </button>
      ))}
    </div>
  );
}
