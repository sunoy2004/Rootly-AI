import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import ServiceHealthGrid from '../components/ServiceHealthGrid';
import MetricsPanel from '../components/MetricsPanel';
import IncidentList from '../components/IncidentList';
import ClusterView from '../components/ClusterView';

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
  const { logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <div
      style={{
        backgroundColor: '#0f1117',
        minHeight: '100vh',
        paddingBottom: 40,
      }}
    >
      {/* Header */}
      <header
        style={{
          backgroundColor: '#1a1d27',
          borderBottom: '1px solid #2a2d3a',
          padding: '16px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <h1
          style={{
            color: '#e8eaf0',
            fontSize: 22,
            margin: 0,
          }}
        >
          API Monitoring Dashboard
        </h1>

        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <LiveClock />
          <button
            onClick={handleLogout}
            style={{
              backgroundColor: 'transparent',
              color: '#8b8fa8',
              border: '1px solid #2a2d3a',
              borderRadius: 6,
              padding: '8px 16px',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            Logout
          </button>
        </div>
      </header>

      <div style={{ padding: '24px' }}>
        {/* Section 1: Service Health */}
        <section style={{ marginBottom: 32 }}>
          <h2
            style={{
              color: '#e8eaf0',
              fontSize: 18,
              marginBottom: 16,
            }}
          >
            Service Health
          </h2>
          <ServiceHealthGrid />
        </section>

        {/* Section 2: Live Metrics */}
        <section style={{ marginBottom: 32 }}>
          <h2
            style={{
              color: '#e8eaf0',
              fontSize: 18,
              marginBottom: 16,
            }}
          >
            Live Metrics (last 30 minutes)
          </h2>
          <div style={{ backgroundColor: '#1a1d27', borderRadius: 12, padding: 16 }}>
            <ServiceHealthGrid />
          </div>
        </section>

        {/* Section 3: Two columns */}
        <section style={{ display: 'flex', gap: 24 }}>
          {/* Left column - Incidents */}
          <div style={{ flex: '0 0 60%' }}>
            <h2
              style={{
                color: '#e8eaf0',
                fontSize: 18,
                marginBottom: 16,
              }}
            >
              Active Incidents
            </h2>
            <div
              style={{
                backgroundColor: '#1a1d27',
                border: '1px solid #2a2d3a',
                borderRadius: 12,
                padding: 16,
              }}
            >
              <IncidentList />
            </div>
          </div>

          {/* Right column - Clusters */}
          <div style={{ flex: '0 0 40%' }}>
            <h2
              style={{
                color: '#e8eaf0',
                fontSize: 18,
                marginBottom: 16,
              }}
            >
              Failure Clusters
            </h2>
            <div
              style={{
                backgroundColor: '#1a1d27',
                border: '1px solid #2a2d3a',
                borderRadius: 12,
                padding: 16,
              }}
            >
              <ClusterView />
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
