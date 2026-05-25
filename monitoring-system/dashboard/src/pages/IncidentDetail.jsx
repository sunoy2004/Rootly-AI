import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getIncident, updateIncident } from '../api/client';
import RootCauseCard from '../components/RootCauseCard';
import TraceViewer from '../components/TraceViewer';
import RelatedErrorLogs from '../components/RelatedErrorLogs';
import ErrorBoundary from '../components/ErrorBoundary';

function SeverityBadge({ severity }) {
  const color = severity === 'CRITICAL' ? '#ef4444' : '#f59e0b';
  return (
    <span
      style={{
        backgroundColor: color,
        color: '#fff',
        padding: '4px 12px',
        borderRadius: 6,
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      {severity}
    </span>
  );
}

function StatusBadge({ status }) {
  const colors = {
    OPEN: '#3b82f6',
    ACKNOWLEDGED: '#f59e0b',
    RESOLVED: '#10b981',
    CLOSED: '#8b8fa8',
  };
  return (
    <span
      style={{
        backgroundColor: colors[status] || '#8b8fa8',
        color: '#fff',
        padding: '4px 12px',
        borderRadius: 6,
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      {status}
    </span>
  );
}

function formatDate(dateStr) {
  if (!dateStr) return 'N/A';
  return new Date(dateStr).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function StatCard({ label, value, unit }) {
  return (
    <div
      style={{
        backgroundColor: '#1a1d27',
        border: '1px solid #2a2d3a',
        borderRadius: 8,
        padding: 12,
      }}
    >
      <div style={{ color: '#8b8fa8', fontSize: 11 }}>{label}</div>
      <div style={{ color: '#e8eaf0', fontSize: 18, fontWeight: 600 }}>
        {typeof value === 'number' ? value.toFixed(2) : value}
        {unit && <span style={{ fontSize: 12, marginLeft: 4 }}>{unit}</span>}
      </div>
    </div>
  );
}

function Timeline({ incident }) {
  const events = [
    { label: 'Created', time: incident.created_at, color: '#3b82f6' },
    { label: 'Acknowledged', time: incident.acknowledged_at, color: '#f59e0b' },
    { label: 'Resolved', time: incident.resolved_at, color: '#10b981' },
  ].filter((e) => e.time);

  return (
    <div style={{ paddingLeft: 12 }}>
      {events.map((event, idx) => (
        <div
          key={idx}
          style={{
            position: 'relative',
            paddingLeft: 20,
            paddingBottom: idx < events.length - 1 ? 20 : 0,
          }}
        >
          <div
            style={{
              position: 'absolute',
              left: 0,
              top: 4,
              width: 10,
              height: 10,
              borderRadius: '50%',
              backgroundColor: event.color,
            }}
          />
          {idx < events.length - 1 && (
            <div
              style={{
                position: 'absolute',
                left: 4,
                top: 14,
                width: 2,
                height: '100%',
                backgroundColor: '#2a2d3a',
              }}
            />
          )}
          <div style={{ color: '#8b8fa8', fontSize: 11 }}>{event.label}</div>
          <div style={{ color: '#e8eaf0', fontSize: 13 }}>{formatDate(event.time)}</div>
        </div>
      ))}
    </div>
  );
}

export default function IncidentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [incident, setIncident] = useState(null);
  const [cluster, setCluster] = useState(null);
  const [errorLogs, setErrorLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [resolving, setResolving] = useState(false);
  const [resolutionNotes, setResolutionNotes] = useState('');

  useEffect(() => {
    const controller = new AbortController();

    async function fetchIncident() {
      try {
        const data = await getIncident(id, controller.signal);
        const inc = { ...(data.incident || data) };
        if (data.ai_analysis) inc.ai_analysis = data.ai_analysis;
        if (data.metrics) {
          inc.error_rate = data.metrics.error_rate ?? inc.error_rate;
          inc.p95_latency_ms = data.metrics.p95_latency_ms ?? inc.p95_latency_ms;
          inc.db_errors = data.metrics.db_errors ?? inc.db_errors;
          inc.gateway_timeouts = data.metrics.gateway_timeouts ?? inc.gateway_timeouts;
        }
        setIncident(inc);
        setCluster(data.cluster);
        setErrorLogs(data.error_logs_raw || data.error_logs || []);
        if (data.cluster?.member_trace_ids?.length) {
          setCluster({ ...data.cluster, member_trace_ids: data.cluster.member_trace_ids });
        }
      } catch (err) {
        console.error('Failed to fetch incident:', err);
      } finally {
        setLoading(false);
      }
    }

    fetchIncident();
    return () => controller.abort();
  }, [id]);

  async function handleAcknowledge() {
    try {
      await updateIncident(id, { status: 'ACKNOWLEDGED' });
      setIncident({ ...incident, status: 'ACKNOWLEDGED', acknowledged_at: new Date().toISOString() });
    } catch (err) {
      console.error('Failed to acknowledge:', err);
    }
  }

  async function handleResolve() {
    if (!resolutionNotes.trim()) return;
    try {
      await updateIncident(id, {
        status: 'RESOLVED',
        resolution_notes: resolutionNotes,
      });
      setIncident({
        ...incident,
        status: 'RESOLVED',
        resolved_at: new Date().toISOString(),
        resolution_notes: resolutionNotes,
      });
      setResolving(false);
    } catch (err) {
      console.error('Failed to resolve:', err);
    }
  }

  if (loading) {
    return (
      <div style={{ padding: 40, color: '#8b8fa8' }}>Loading incident...</div>
    );
  }

  if (!incident) {
    return (
      <div style={{ padding: 40, color: '#8b8fa8' }}>Incident not found</div>
    );
  }

  const traceIds = cluster?.member_trace_ids || [];

  return (
    <div
      style={{
        backgroundColor: '#0f1117',
        minHeight: '100vh',
        paddingBottom: 40,
      }}
    >
      {/* Top bar */}
      <header
        style={{
          backgroundColor: '#1a1d27',
          borderBottom: '1px solid #2a2d3a',
          padding: '16px 24px',
          display: 'flex',
          alignItems: 'center',
          gap: 16,
        }}
      >
        <button
          onClick={() => navigate('/dashboard')}
          style={{
            backgroundColor: 'transparent',
            color: '#8b8fa8',
            border: '1px solid #2a2d3a',
            borderRadius: 6,
            padding: '8px 12px',
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          Back
        </button>

        <h1
          style={{
            color: '#e8eaf0',
            fontSize: 20,
            margin: 0,
            flex: 1,
          }}
        >
          {incident.title}
        </h1>

        <SeverityBadge severity={incident.severity} />
        <StatusBadge status={incident.status} />

        {(incident.status === 'OPEN' || incident.status === 'ACKNOWLEDGED') && (
          <>
            {incident.status === 'OPEN' && (
              <button
                onClick={handleAcknowledge}
                style={{
                  backgroundColor: '#3b82f6',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 6,
                  padding: '8px 16px',
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                Acknowledge
              </button>
            )}
            <button
              onClick={() => setResolving(true)}
              style={{
                backgroundColor: '#10b981',
                color: '#fff',
                border: 'none',
                borderRadius: 6,
                padding: '8px 16px',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              Resolve
            </button>
          </>
        )}
      </header>

      {resolving && (
        <div
          style={{
            backgroundColor: '#1a1d27',
            borderBottom: '1px solid #2a2d3a',
            padding: '16px 24px',
          }}
        >
          <div style={{ marginBottom: 8 }}>
            <label style={{ color: '#8b8fa8', fontSize: 12 }}>Resolution Notes</label>
          </div>
          <input
            type="text"
            value={resolutionNotes}
            onChange={(e) => setResolutionNotes(e.target.value)}
            placeholder="Enter resolution notes..."
            style={{
              width: '100%',
              maxWidth: 400,
              padding: '10px 12px',
              backgroundColor: '#0f1117',
              border: '1px solid #2a2d3a',
              borderRadius: 6,
              color: '#e8eaf0',
              fontSize: 14,
            }}
          />
          <div style={{ marginTop: 12 }}>
            <button
              onClick={handleResolve}
              style={{
                backgroundColor: '#10b981',
                color: '#fff',
                border: 'none',
                borderRadius: 6,
                padding: '8px 16px',
                fontSize: 13,
                cursor: 'pointer',
                marginRight: 8,
              }}
            >
              Confirm
            </button>
            <button
              onClick={() => setResolving(false)}
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
              Cancel
            </button>
          </div>
        </div>
      )}

      <div style={{ padding: '24px', display: 'flex', gap: 24 }}>
        {/* Left column */}
        <div style={{ flex: '0 0 60%' }}>
          <section style={{ marginBottom: 24 }}>
            <ErrorBoundary name="RootCauseCard" title="Analysis unavailable">
              <RootCauseCard incident={incident} />
            </ErrorBoundary>
          </section>

          <section>
            <RelatedErrorLogs rawLogs={errorLogs} />
          </section>
        </div>

        {/* Right column */}
        <div style={{ flex: '0 0 40%' }}>
          <section style={{ marginBottom: 24 }}>
            <h3
              style={{
                color: '#e8eaf0',
                fontSize: 16,
                marginBottom: 12,
              }}
            >
              Metrics at Time of Incident
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <StatCard
                label="Error Rate"
                value={(incident.error_rate || 0) * 100}
                unit="%"
              />
              <StatCard
                label="p95 Latency"
                value={incident.p95_latency_ms || 0}
                unit="ms"
              />
              <StatCard
                label="DB Errors"
                value={incident.db_errors || 0}
                unit="errors/s"
              />
              <StatCard
                label="Gateway Timeouts"
                value={incident.gateway_timeouts || 0}
                unit="/s"
              />
            </div>
          </section>

          <section style={{ marginBottom: 24 }}>
            <h3
              style={{
                color: '#e8eaf0',
                fontSize: 16,
                marginBottom: 12,
              }}
            >
              Distributed Traces
            </h3>
            <div
              style={{
                backgroundColor: '#1a1d27',
                border: '1px solid #2a2d3a',
                borderRadius: 12,
                padding: 16,
              }}
            >
              <TraceViewer traceIds={traceIds} />
            </div>
          </section>

          <section>
            <h3
              style={{
                color: '#e8eaf0',
                fontSize: 16,
                marginBottom: 12,
              }}
            >
              Incident Timeline
            </h3>
            <div
              style={{
                backgroundColor: '#1a1d27',
                border: '1px solid #2a2d3a',
                borderRadius: 12,
                padding: 16,
              }}
            >
              <Timeline incident={incident} />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
