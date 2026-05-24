import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getIncidents,
  updateIncident,
  isRequestAborted,
} from '../api/client';

const STATUS_OPTIONS = ['', 'OPEN', 'ACKNOWLEDGED', 'RESOLVED'];
const SEVERITY_OPTIONS = ['', 'WARNING', 'CRITICAL'];
const SERVICE_OPTIONS = ['', 'user-service', 'order-service', 'payment-service'];

const incidentListStyles = `
  .incident-grid-container {
    max-height: min(580px, 70vh);
    overflow-y: auto;
    padding-right: 6px;
  }
  .incident-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
    gap: 16px;
    padding: 4px;
  }
  .incident-card {
    background: rgba(26, 29, 39, 0.45);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }
  .incident-card:hover {
    transform: translateY(-2px);
    background: rgba(30, 35, 48, 0.6);
    border-color: rgba(255, 255, 255, 0.15);
  }
  .incident-card.critical {
    border-color: rgba(239, 68, 68, 0.3);
    box-shadow: 0 4px 20px rgba(239, 68, 68, 0.08), 0 0 10px rgba(239, 68, 68, 0.03), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }
  .incident-card.critical:hover {
    border-color: rgba(239, 68, 68, 0.55);
    box-shadow: 0 8px 30px rgba(239, 68, 68, 0.15), 0 0 15px rgba(239, 68, 68, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }
  .incident-card.warning {
    border-color: rgba(245, 158, 11, 0.3);
    box-shadow: 0 4px 20px rgba(245, 158, 11, 0.08), 0 0 10px rgba(245, 158, 11, 0.03), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }
  .incident-card.warning:hover {
    border-color: rgba(245, 158, 11, 0.55);
    box-shadow: 0 8px 30px rgba(245, 158, 11, 0.15), 0 0 15px rgba(245, 158, 11, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }
  .incident-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .incident-card-title {
    font-size: 14px;
    font-weight: 600;
    color: #e8eaf0;
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-height: 1.4;
    height: 38px;
  }
  .incident-card-body {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .incident-meta-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
  }
  .incident-label {
    color: #8b8fa8;
  }
  .incident-value {
    color: #e8eaf0;
    font-weight: 500;
  }
  .incident-card-actions {
    display: flex;
    gap: 8px;
    margin-top: 6px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 12px;
  }
  .action-btn {
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    flex: 1;
    text-align: center;
  }
  .action-btn-ack {
    background: rgba(59, 130, 246, 0.15);
    color: #3b82f6;
    border: 1px solid rgba(59, 130, 246, 0.3);
  }
  .action-btn-ack:hover {
    background: #3b82f6;
    color: #fff;
    box-shadow: 0 0 10px rgba(59, 130, 246, 0.3);
  }
  .action-btn-resolve {
    background: rgba(16, 185, 129, 0.15);
    color: #10b981;
    border: 1px solid rgba(16, 185, 129, 0.3);
  }
  .action-btn-resolve:hover {
    background: #10b981;
    color: #fff;
    box-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
  }
  .action-btn-view {
    background: transparent;
    color: #e8eaf0;
    border: 1px solid rgba(255, 255, 255, 0.15);
  }
  .action-btn-view:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.3);
  }
  .custom-select {
    background: rgba(26, 29, 39, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 8px 14px;
    color: #e8eaf0;
    font-size: 13px;
    cursor: pointer;
    outline: none;
    transition: all 0.2s ease;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
  }
  .custom-select:focus {
    border-color: #3b82f6;
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
  }
  .custom-select option {
    background: #1a1d27;
    color: #e8eaf0;
  }
  .resolve-input-container {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 8px;
    padding: 10px;
    margin-top: 8px;
    border: 1px solid rgba(255, 255, 255, 0.05);
  }
  .resolve-input {
    background: rgba(15, 17, 23, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 6px 10px;
    color: #e8eaf0;
    width: 100%;
    font-size: 12px;
    margin-bottom: 8px;
  }
  .resolve-input:focus {
    border-color: #10b981;
  }
`;

function SeverityBadge({ severity }) {
  const isCritical = severity === 'CRITICAL';
  const bgColor = isCritical ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)';
  const color = isCritical ? '#ef4444' : '#f59e0b';
  const border = isCritical ? '1px solid rgba(239, 68, 68, 0.3)' : '1px solid rgba(245, 158, 11, 0.3)';
  
  return (
    <span
      style={{
        backgroundColor: bgColor,
        color,
        border,
        padding: '2px 8px',
        borderRadius: 6,
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.05em',
      }}
    >
      {severity}
    </span>
  );
}

function StatusBadge({ status }) {
  const colors = {
    OPEN: { bg: 'rgba(59, 130, 246, 0.15)', text: '#3b82f6', border: 'rgba(59, 130, 246, 0.3)' },
    ACKNOWLEDGED: { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b', border: 'rgba(245, 158, 11, 0.3)' },
    RESOLVED: { bg: 'rgba(16, 185, 129, 0.15)', text: '#10b981', border: 'rgba(16, 185, 129, 0.3)' },
    CLOSED: { bg: 'rgba(139, 143, 168, 0.15)', text: '#8b8fa8', border: 'rgba(139, 143, 168, 0.3)' },
  };
  const current = colors[status] || colors.CLOSED;
  return (
    <span
      style={{
        backgroundColor: current.bg,
        color: current.text,
        border: `1px solid ${current.border}`,
        padding: '2px 8px',
        borderRadius: 6,
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.05em',
      }}
    >
      {status}
    </span>
  );
}

function SourceBadge({ source }) {
  const isRule = source === 'RULE_ENGINE';
  const bgColor = isRule ? 'rgba(59, 130, 246, 0.12)' : 'rgba(139, 92, 246, 0.12)';
  const color = isRule ? '#3b82f6' : '#a78bfa';
  const border = isRule ? '1px solid rgba(59, 130, 246, 0.25)' : '1px solid rgba(139, 92, 246, 0.25)';
  const label = isRule ? 'RULE' : 'AI';
  
  return (
    <span
      style={{
        backgroundColor: bgColor,
        color,
        border,
        padding: '2px 6px',
        borderRadius: 4,
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: '0.03em',
      }}
    >
      {label}
    </span>
  );
}

function ConfidenceBar({ confidence }) {
  if (confidence === undefined || confidence === null) return null;
  const pct = Math.min(100, Math.max(0, confidence * 100));
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}>
      <span style={{ color: '#8b8fa8', fontSize: 11, width: 32 }}>Conf:</span>
      <div
        style={{
          flex: 1,
          height: 6,
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          borderRadius: 3,
          overflow: 'hidden',
          border: '1px solid rgba(255, 255, 255, 0.05)',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background:
              pct > 70 ? 'linear-gradient(90deg, #059669, #10b981)' : pct > 40 ? 'linear-gradient(90deg, #d97706, #f59e0b)' : 'linear-gradient(90deg, #dc2626, #ef4444)',
            borderRadius: 3,
          }}
        />
      </div>
      <span style={{ color: '#e8eaf0', fontSize: 11, fontWeight: 600, width: 28, textAlign: 'right' }}>{pct.toFixed(0)}%</span>
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
  const [refreshKey, setRefreshKey] = useState(0);
  const [resolvingId, setResolvingId] = useState(null);
  const [resolutionNotes, setResolutionNotes] = useState('');

  useEffect(() => {
    const controller = new AbortController();

    async function fetchIncidents() {
      try {
        const params = {};
        if (filters.status) params.status = filters.status;
        if (filters.severity) params.severity = filters.severity;
        if (filters.service) params.service = filters.service;

        const data = await getIncidents(params, controller.signal);
        if (!controller.signal.aborted) setIncidents(data);
      } catch (err) {
        if (!isRequestAborted(err)) {
          console.error('Failed to fetch incidents:', err);
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    fetchIncidents();
    const interval = setInterval(fetchIncidents, 5000);
    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, [filters, refreshKey]);

  async function handleAcknowledge(id) {
    try {
      await updateIncident(id, { status: 'ACKNOWLEDGED' });
      setRefreshKey((k) => k + 1);
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
      setRefreshKey((k) => k + 1);
    } catch (err) {
      console.error('Failed to resolve:', err);
    }
  }

  return (
    <div>
      <style>{incidentListStyles}</style>
      
      <div
        style={{
          display: 'flex',
          gap: 12,
          marginBottom: 16,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        <span style={{ color: '#8b8fa8', fontSize: 13, fontWeight: 500 }}>Filters:</span>
        <select
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value })}
          className="custom-select"
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
          className="custom-select"
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
          className="custom-select"
        >
          {SERVICE_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s || 'All Services'}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div style={{ color: '#8b8fa8', padding: 20, textAlign: 'center' }}>
          <div style={{ display: 'inline-block', width: 24, height: 24, border: '3px solid rgba(255,255,255,0.1)', borderTopColor: '#3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite', marginBottom: 8 }} />
          <div>Loading incidents...</div>
        </div>
      ) : incidents.length === 0 ? (
        <div
          style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px dashed rgba(255,255,255,0.08)',
            borderRadius: 12,
            padding: '32px',
            textAlign: 'center',
            color: '#8b8fa8',
            fontSize: 14,
          }}
        >
          No active incidents found matching active filters.
        </div>
      ) : (
        <div className="incident-grid-container">
          <div className="incident-grid">
            {incidents.map((incident) => {
              const severityClass = incident.severity === 'CRITICAL' ? 'critical' : 'warning';
              return (
                <div key={incident.id} className={`incident-card ${severityClass}`}>
                  <div className="incident-card-header">
                    <SeverityBadge severity={incident.severity} />
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <SourceBadge source={incident.source} />
                      <StatusBadge status={incident.status} />
                    </div>
                  </div>

                  <h4 className="incident-card-title" title={incident.title}>
                    {incident.title}
                  </h4>

                  <div className="incident-card-body">
                    <div className="incident-meta-row">
                      <span className="incident-label">Service:</span>
                      <span className="incident-value" style={{ fontFamily: 'monospace' }}>
                        {incident.affected_services?.[0] || 'unknown-service'}
                      </span>
                    </div>

                    <div className="incident-meta-row">
                      <span className="incident-label">Detected:</span>
                      <span className="incident-value" style={{ fontSize: 11 }}>
                        {timeAgo(incident.created_at)}
                      </span>
                    </div>

                    <ConfidenceBar confidence={incident.confidence} />
                  </div>

                  <div className="incident-card-actions">
                    {incident.status === 'OPEN' && (
                      <button
                        onClick={() => handleAcknowledge(incident.id)}
                        className="action-btn action-btn-ack"
                      >
                        Ack
                      </button>
                    )}
                    {(incident.status === 'OPEN' || incident.status === 'ACKNOWLEDGED') && (
                      <button
                        onClick={() => setResolvingId(resolvingId === incident.id ? null : incident.id)}
                        className="action-btn action-btn-resolve"
                      >
                        Resolve
                      </button>
                    )}
                    <button
                      onClick={() => navigate(`/incidents/${incident.id}`)}
                      className="action-btn action-btn-view"
                    >
                      View Details
                    </button>
                  </div>

                  {resolvingId === incident.id && (
                    <div className="resolve-input-container">
                      <input
                        type="text"
                        placeholder="Provide resolution notes..."
                        value={resolutionNotes}
                        onChange={(e) => setResolutionNotes(e.target.value)}
                        className="resolve-input"
                        autoFocus
                      />
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          onClick={() => handleResolve(incident.id)}
                          style={{
                            backgroundColor: '#10b981',
                            color: '#fff',
                            border: 'none',
                            borderRadius: 4,
                            padding: '4px 10px',
                            fontSize: 11,
                            fontWeight: 600,
                            cursor: 'pointer',
                            flex: 1,
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
                            border: '1px solid rgba(255,255,255,0.1)',
                            borderRadius: 4,
                            padding: '4px 10px',
                            fontSize: 11,
                            fontWeight: 600,
                            cursor: 'pointer',
                            flex: 1,
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

