import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import HomePage from './pages/HomePage';
import AuthCallbackPage from './pages/AuthCallbackPage';
import RecommendationsPage from './pages/RecommendationsPage';

function App() {
  if (
    typeof window !== 'undefined' &&
    process.env.NODE_ENV === 'development' &&
    window.location.protocol === 'http:' &&
    window.location.hostname === 'localhost'
  ) {
    const normalizedUrl = new URL(window.location.href);
    normalizedUrl.hostname = '127.0.0.1';
    window.location.replace(normalizedUrl.toString());
    return null;
  }

  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route path="/recommendations" element={<RecommendationsPage />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
