import React from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Dashboard from './pages/Dashboard';
import IncidentDetail from './pages/IncidentDetail';
import ErrorBoundary from './components/ErrorBoundary';
import './index.css';

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/incidents/:id" element={<IncidentDetail />} />
    </Routes>
  );
}

export default function App() {
  return (
    <ErrorBoundary name="App" title="Dashboard crashed">
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
