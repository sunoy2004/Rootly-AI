import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getIncidents, updateIncident } from '../api/client';

const STATUS_OPTIONS = ['', 'OPEN', 'ACKNOWLEDGED', 'RESOLVED'];
const SEVERITY_OPTIONS = ['', 'WARNING', 'CRITICAL'];
const SERVICE_OPTIONS = ['', 'user-service', 'order-service', 'payment-service'];

function SeverityBadge({ severity }) {
  const color = severity === 'CRITICAL' ? '#ef4444' : '#f59e0b';
  return (
    <span
      style={{
        backgroundColor: color,
        color: '#fff',
        padding: '2px 8px',
        borderRadius: 4,
        fontSize: 11,
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
        padding: '2px 8px',
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 600,
      }}
    >
      {status}
    </span>
  );
}

function SourceBadge({ source }) {
  const color = source === 'RULE_ENGINE' ? '#3b82f6' : '#8b5cf6';
  const label = source === 'RULE_ENGINE' ? 'RULE' : 'AI';
  return (
    <span
      style={{
        backgroundColor: color,
        color: '#fff',
        padding: '2px 6px',
        borderRadius: 4,
        fontSize: 10,
        fontWeight: 600,
      }}
    >
      {label}
    </span>
  );
}

function ConfidenceBar({ confidence }) {
  if (!confidence) return null;
  const pct = Math.min(100, Math.max(0, confidence * 100));
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
      }}
    >
      <div
        style={{
          width: 60,
          height: 6,
          backgroundColor: '#2a2d3a',
          borderRadius: 3,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            backgroundColor:
              pct > 70 ? '#10b981' : pct > 40 ? '#f59e0b' : '#ef4444',
          }}
        />
      </div>
      <span style={{ color: '#8b8fa8', fontSize: 11 }}>{pct.toFixed(0)}%</span>
    </div>
  );
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export default function IncidentList() {
  const navigate = useNavigate();
  const [incidents, setIncidents] = useState([]);
  const [filters, setFilters] = useState({
    status: 'OPEN',
    severity: '',
    service: '',
  });
  const [loading, setLoading] = useState(true);
  const [resolvingId, setResolvingId] = useState(null);
  const [resolutionNotes, setResolutionNotes] = useState('');

  async function fetchIncidents() {
    try {
      const params = {};
      if (filters.status) params.status = filters.status;
      if (filters.severity) params.severity = filters.severity;
      if (filters.service) params.service = filters.service;

      const data = await getIncidents(params);
      setIncidents(data);
    } catch (err) {
      console.error('Failed to fetch incidents:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchIncidents();
    const interval = setInterval(fetchIncidents, 30000);
    return () => clearInterval(interval);
  }, [filters]);

  async function handleAcknowledge(id) {
    try {
      await updateIncident(id, { status: 'ACKNOWLEDGED' });
      fetchIncidents();
    } catch (err) {
      console.error('Failed to acknowledge:', err);
    }
  }

  async function handleResolve(id) {
    if (!resolutionNotes.trim()) return;
    try {
      await updateIncident(id, {
        status: 'RESOLVED',
        resolution_notes: resolutionNotes,
      });
      setResolvingId(null);
      setResolutionNotes('');
      fetchIncidents();
    } catch (err) {
      console.error('Failed to resolve:', err);
    }
  }

  return (
    <div>
      <div
        style={{
          display: 'flex',
          gap: 12,
          marginBottom: 16,
          flexWrap: 'wrap',
        }}
      >
        <select
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value })}
          style={{
            backgroundColor: '#1a1d27',
            border: '1px solid #2a2d3a',
            borderRadius: 6,
            padding: '6px 12px',
            color: '#e8eaf0',
          }}
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s || 'All Statuses'}
            </option>
          ))}
        </select>

        <select
          value={filters.severity}
          onChange={(e) => setFilters({ ...filters, severity: e.target.value })}
          style={{
            backgroundColor: '#1a1d27',
            border: '1px solid #2a2d3a',
            borderRadius: 6,
            padding: '6px 12px',
            color: '#e8eaf0',
          }}
        >
          {SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s || 'All Severities'}
            </option>
          ))}
        </select>

        <select
          value={filters.service}
          onChange={(e) => setFilters({ ...filters, service: e.target.value })}
          style={{
            backgroundColor: '#1a1d27',
            border: '1px solid #2a2d3a',
            borderRadius: 6,
            padding: '6px 12px',
            color: '#e8eaf0',
          }}
        >
          {SERVICE_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s || 'All Services'}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div style={{ color: '#8b8fa8', padding: 20 }}>Loading incidents...</div>
      ) : incidents.length === 0 ? (
        <div style={{ color: '#8b8fa8', padding: 20 }}>No incidents found</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #2a2d3a' }}>
                <th style={{ textAlign: 'left', padding: '10px 8px', color: '#8b8fa8', fontSize: 12 }}>Severity</th>
                <th style={{ textAlign: 'left', padding: '10px 8px', color: '#8b8fa8', fontSize: 12 }}>Service</th>
                <th style={{ textAlign: 'left', padding: '10px 8px', color: '#8b8fa8', fontSize: 12 }}>Title</th>
                <th style={{ textAlign: 'left', padding: '10px 8px', color: '#8b8fa8', fontSize: 12 }}>Status</th>
                <th style={{ textAlign: 'left', padding: '10px 8px', color: '#8b8fa8', fontSize: 12 }}>Confidence</th>
                <th style={{ textAlign: 'left', padding: '10px 8px', color: '#8b8fa8', fontSize: 12 }}>Source</th>
                <th style={{ textAlign: 'left', padding: '10px 8px', color: '#8b8fa8', fontSize: 12 }}>Time</th>
                <th style={{ textAlign: 'left', padding: '10px 8px', color: '#8b8fa8', fontSize: 12 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((incident) => (
                <tr
                  key={incident.id}
                  style={{
                    borderBottom: '1px solid #2a2d3a',
                    backgroundColor: 'transparent',
                  }}
                >
                  <td style={{ padding: '10px 8px' }}>
                    <SeverityBadge severity={incident.severity} />
                  </td>
                  <td style={{ padding: '10px 8px', color: '#e8eaf0', fontSize: 13 }}>
                    {incident.affected_services?.[0] || '-'}
                  </td>
                  <td style={{ padding: '10px 8px', color: '#e8eaf0', fontSize: 13, maxWidth: 200 }}>
                    <span
                      style={{
                        display: 'inline-block',
                        maxWidth: 180,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {incident.title}
                    </span>
                  </td>
                  <td style={{ padding: '10px 8px' }}>
                    <StatusBadge status={incident.status} />
                  </td>
                  <td style={{ padding: '10px 8px' }}>
                    <ConfidenceBar confidence={incident.confidence} />
                  </td>
                  <td style={{ padding: '10px 8px' }}>
                    <SourceBadge source={incident.source} />
                  </td>
                  <td style={{ padding: '10px 8px', color: '#8b8fa8', fontSize: 12 }}>
                    {timeAgo(incident.created_at)}
                  </td>
                  <td style={{ padding: '10px 8px' }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      {incident.status === 'OPEN' && (
                        <button
                          onClick={() => handleAcknowledge(incident.id)}
                          style={{
                            backgroundColor: '#3b82f6',
                            color: '#fff',
                            border: 'none',
                            borderRadius: 4,
                            padding: '4px 8px',
                            fontSize: 11,
                            cursor: 'pointer',
                          }}
                        >
                          Ack
                        </button>
                      )}
                      {(incident.status === 'OPEN' || incident.status === 'ACKNOWLEDGED') && (
                        <button
                          onClick={() => setResolvingId(incident.id)}
                          style={{
                            backgroundColor: '#10b981',
                            color: '#fff',
                            border: 'none',
                            borderRadius: 4,
                            padding: '4px 8px',
                            fontSize: 11,
                            cursor: 'pointer',
                          }}
                        >
                          Resolve
                        </button>
                      )}
                      <button
                        onClick={() => navigate(`/incidents/${incident.id}`)}
                        style={{
                          backgroundColor: 'transparent',
                          color: '#3b82f6',
                          border: '1px solid #3b82f6',
                          borderRadius: 4,
                          padding: '4px 8px',
                          fontSize: 11,
                          cursor: 'pointer',
                        }}
                      >
                        View
                      </button>
                    </div>
                    {resolvingId === incident.id && (
                      <div style={{ marginTop: 8 }}>
                        <input
                          type="text"
                          placeholder="Resolution notes..."
                          value={resolutionNotes}
                          onChange={(e) => setResolutionNotes(e.target.value)}
                          style={{
                            backgroundColor: '#0f1117',
                            border: '1px solid #2a2d3a',
                            borderRadius: 4,
                            padding: '4px 8px',
                            color: '#e8eaf0',
                            width: '100%',
                            marginBottom: 4,
                          }}
                        />
                        <button
                          onClick={() => handleResolve(incident.id)}
                          style={{
                            backgroundColor: '#10b981',
                            color: '#fff',
                            border: 'none',
                            borderRadius: 4,
                            padding: '4px 12px',
                            fontSize: 11,
                            cursor: 'pointer',
                          }}
                        >
                          Confirm
                        </button>
                        <button
                          onClick={() => {
                            setResolvingId(null);
                            setResolutionNotes('');
                          }}
                          style={{
                            backgroundColor: 'transparent',
                            color: '#8b8fa8',
                            border: '1px solid #2a2d3a',
                            borderRadius: 4,
                            padding: '4px 12px',
                            fontSize: 11,
                            cursor: 'pointer',
                            marginLeft: 4,
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
