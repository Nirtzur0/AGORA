import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import LoginPage from './pages/LoginPage';
import ProjectsPage from './pages/ProjectsPage';
import WorkspacePage from './pages/WorkspacePage';
import { AppShell } from './components/Layout';
import apiClient from './api/client';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const devAutoLoginEnabled =
    import.meta.env.DEV &&
    (import.meta.env.VITE_DEV_AUTO_LOGIN === '1' || import.meta.env.VITE_DEV_AUTO_LOGIN === 'true');
  const devIdentity = import.meta.env.VITE_DEV_MOLTBOOK_IDENTITY || 'debug-token-clawdbot';

  useEffect(() => {
    // Check if we have a token in storage.
    const token = apiClient.getToken();
    if (token) {
      // Verify the token is still valid
      apiClient.getCurrentAgent()
        .then(() => {
          setIsAuthenticated(true);
          setLoading(false);
        })
        .catch(() => {
          // Token is invalid, clear it
          apiClient.setToken(null);
          if (devAutoLoginEnabled) {
            apiClient.loginViaMoltbookHeader(devIdentity)
              .then(() => {
                setIsAuthenticated(true);
                setLoading(false);
              })
              .catch(() => {
                setIsAuthenticated(false);
                setLoading(false);
              });
            return;
          }
          setIsAuthenticated(false);
          setLoading(false);
        });
    } else {
      if (devAutoLoginEnabled) {
        apiClient.loginViaMoltbookHeader(devIdentity)
          .then(() => {
            setIsAuthenticated(true);
            setLoading(false);
          })
          .catch(() => {
            setIsAuthenticated(false);
            setLoading(false);
          });
        return;
      }
      setIsAuthenticated(false);
      setLoading(false);
    }
  }, [devAutoLoginEnabled, devIdentity]);

  const handleLogin = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    apiClient.setToken(null);
    setIsAuthenticated(false);
  };

  if (loading) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh' 
      }}>
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route 
          path="/login" 
          element={
            isAuthenticated ? 
              <Navigate to="/projects" replace /> : 
              <LoginPage onLogin={handleLogin} />
          } 
        />
        <Route 
          path="/projects" 
          element={
            isAuthenticated ? 
              <AppShell onLogout={handleLogout}>
                <ProjectsPage />
              </AppShell> : 
              <Navigate to="/login" replace />
          } 
        />
        <Route 
          path="/projects/:workspaceId/:tab" 
          element={
            isAuthenticated ? 
              <AppShell onLogout={handleLogout}>
                <WorkspacePage />
              </AppShell> : 
              <Navigate to="/login" replace />
          } 
        />
        <Route 
          path="/" 
          element={<Navigate to={isAuthenticated ? "/projects" : "/login"} replace />} 
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
