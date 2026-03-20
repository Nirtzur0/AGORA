import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import './Layout.css';

const ShellFrameContext = createContext(null);

const DEFAULT_FRAME = {
  eyebrow: 'Evidence-first workspace console',
  title: 'AGORA',
  summary: 'Track provenance, execution, and review state without crossing authority boundaries.',
  search: null,
  actions: null,
};

function getQuickLinks(pathname) {
  const workspaceMatch = pathname.match(/^\/projects\/([^/]+)\//);
  if (workspaceMatch) {
    const workspaceId = workspaceMatch[1];
    return [
      { label: 'Portfolio', to: '/projects' },
      { label: 'Overview', to: `/projects/${workspaceId}/overview` },
      { label: 'Timeline', to: `/projects/${workspaceId}/timeline` },
      { label: 'Search', to: `/projects/${workspaceId}/search` },
    ];
  }

  if (pathname.startsWith('/projects')) {
    return [{ label: 'Portfolio', to: '/projects' }];
  }

  return [];
}

export function useShellFrame(frame) {
  const setFrame = useContext(ShellFrameContext);

  useEffect(() => {
    if (!setFrame) return undefined;
    setFrame(frame);
    return () => setFrame(DEFAULT_FRAME);
  }, [frame, setFrame]);
}

export function AppShell({ children, onLogout }) {
  const location = useLocation();
  const [frame, setFrame] = useState(DEFAULT_FRAME);
  const [searchValue, setSearchValue] = useState('');
  const quickLinks = useMemo(() => getQuickLinks(location.pathname), [location.pathname]);

  useEffect(() => {
    setSearchValue(frame.search?.initialValue || '');
  }, [frame.search?.initialValue, location.pathname, location.search]);

  const searchConfig = frame.search;

  return (
    <ShellFrameContext.Provider value={setFrame}>
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

        <section className="shell-command-deck" aria-label="Workspace command deck">
          <div className="shell-context-card">
            <p className="shell-context-eyebrow">{frame.eyebrow || DEFAULT_FRAME.eyebrow}</p>
            <h2 className="shell-context-title">{frame.title || DEFAULT_FRAME.title}</h2>
            <p className="shell-context-summary">{frame.summary || DEFAULT_FRAME.summary}</p>
            {quickLinks.length ? (
              <nav className="shell-quick-links" aria-label="Quick navigation">
                {quickLinks.map((link) => (
                  <NavLink key={link.to} to={link.to} className={({ isActive }) => `shell-quick-link ${isActive ? 'active' : ''}`}>
                    {link.label}
                  </NavLink>
                ))}
              </nav>
            ) : null}
          </div>

          <div className="shell-command-card">
            <div className="shell-command-header">
              <div>
                <p className="shell-command-eyebrow">Action rail</p>
                <h3>Search and move faster</h3>
              </div>
              {frame.actions ? <div className="shell-command-actions">{frame.actions}</div> : null}
            </div>

            {searchConfig ? (
              <form
                className="shell-search-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (!searchConfig.onSubmit) return;
                  searchConfig.onSubmit(searchValue.trim());
                }}
              >
                <label className="shell-search-label" htmlFor="shell-search-input">
                  Global search
                </label>
                <div className="shell-search-row">
                  <input
                    id="shell-search-input"
                    className="text-input shell-search-input"
                    value={searchValue}
                    onChange={(event) => setSearchValue(event.target.value)}
                    placeholder={searchConfig.placeholder || 'Search'}
                  />
                  <button type="submit" className="btn btn-primary" disabled={!searchValue.trim()}>
                    {searchConfig.buttonLabel || 'Search'}
                  </button>
                </div>
                {searchConfig.hint ? <p className="shell-search-hint">{searchConfig.hint}</p> : null}
              </form>
            ) : (
              <p className="shell-search-hint">Open a workspace to search indexed evidence, drafts, and logs.</p>
            )}
          </div>
        </section>

        <main id="main-content" className="shell-main">
          {children}
        </main>
      </div>
    </ShellFrameContext.Provider>
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
