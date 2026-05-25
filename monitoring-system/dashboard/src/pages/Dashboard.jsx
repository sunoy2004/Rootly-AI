import React, { useState, useEffect } from 'react';
import ServiceHealthGrid from '../components/ServiceHealthGrid';
import MetricsPanel from '../components/MetricsPanel';
import IncidentList from '../components/IncidentList';
import ClusterView from '../components/ClusterView';
import LogViewer from '../components/LogViewer';
import AnomalyPanel from '../components/AnomalyPanel';
import ErrorBoundary from '../components/ErrorBoundary';
import { useBackendHealth } from '../hooks/useBackendHealth';

function LiveClock() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <span style={{ color: '#e8eaf0', fontSize: 14 }}>
      {time.toLocaleString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })}
    </span>
  );
}

export default function Dashboard() {
  const backendOk = useBackendHealth();

  return (
    <div style={{ backgroundColor: '#0f1117', minHeight: '100vh', paddingBottom: 40 }}>
      {backendOk === false && (
        <div
          style={{
            backgroundColor: '#7f1d1d',
            color: '#fecaca',
            padding: '12px 24px',
            fontSize: 14,
            borderBottom: '1px solid #ef4444',
          }}
        >
          Cannot reach incident-manager at {import.meta.env.VITE_API_URL || 'http://localhost:8013'}.
          Run: <code style={{ background: '#450a0a', padding: '2px 6px' }}>docker compose up -d incident-manager</code>
          {' '}in <code>monitoring-system</code>, then refresh.
        </div>
      )}
      <header
        style={{
          backgroundColor: '#1a1d27',
          borderBottom: '1px solid #2a2d3a',
          padding: '16px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <h1 style={{ color: '#e8eaf0', fontSize: 22, margin: 0 }}>API Monitoring Dashboard</h1>
        <LiveClock />
      </header>

      <div style={{ padding: '24px' }}>
        <section style={{ marginBottom: 32 }}>
          <h2 style={{ color: '#e8eaf0', fontSize: 18, marginBottom: 16 }}>Service Health</h2>
          <ErrorBoundary name="ServiceHealthGrid" title="Service health unavailable">
            <ServiceHealthGrid />
          </ErrorBoundary>
        </section>

        <section style={{ marginBottom: 32 }}>
          <h2 style={{ color: '#e8eaf0', fontSize: 18, marginBottom: 16 }}>Live Metrics (last 10 minutes)</h2>
          <div style={{ backgroundColor: '#1a1d27', borderRadius: 12, padding: 16 }}>
            <ErrorBoundary name="MetricsPanel" title="Metrics unavailable">
              <MetricsPanel />
            </ErrorBoundary>
          </div>
        </section>

        <section style={{ marginBottom: 32 }}>
          <ErrorBoundary name="AnomalyPanel" title="Anomalies unavailable">
            <AnomalyPanel />
          </ErrorBoundary>
        </section>

        <section style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
          <div style={{ flex: '1 1 60%', minWidth: 0 }}>
            <h2 style={{ color: '#e8eaf0', fontSize: 18, marginBottom: 16 }}>Active Incidents</h2>
            <div style={{ backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12, padding: 16 }}>
              <ErrorBoundary name="IncidentList" title="Incidents unavailable">
                <IncidentList />
              </ErrorBoundary>
            </div>
          </div>

          <div style={{ flex: '1 1 40%', minWidth: 0 }}>
            <h2 style={{ color: '#e8eaf0', fontSize: 18, marginBottom: 16 }}>Failure Clusters</h2>
            <div style={{ backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12, padding: 16 }}>
              <ErrorBoundary name="ClusterView" title="Clusters unavailable">
                <ClusterView />
              </ErrorBoundary>
            </div>
          </div>
        </section>

        <section style={{ marginTop: 32 }}>
          <h2 style={{ color: '#e8eaf0', fontSize: 18, marginBottom: 16 }}>Live Log Viewer</h2>
          <ErrorBoundary name="LogViewer" title="Log viewer unavailable">
            <LogViewer />
          </ErrorBoundary>
        </section>
      </div>
    </div>
  );
}
