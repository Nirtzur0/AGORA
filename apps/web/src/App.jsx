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

  useEffect(() => {
    // Check if we have a token in sessionStorage
    const token = sessionStorage.getItem('agent_session_jwt');
    if (token) {
      // Verify the token is still valid
      apiClient.getCurrentAgent()
        .then(() => {
          setIsAuthenticated(true);
          setLoading(false);
        })
        .catch(() => {
          // Token is invalid, clear it
          sessionStorage.removeItem('agent_session_jwt');
          setIsAuthenticated(false);
          setLoading(false);
        });
    } else {
      setIsAuthenticated(false);
      setLoading(false);
    }
  }, []);

  const handleLogin = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    sessionStorage.removeItem('agent_session_jwt');
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
