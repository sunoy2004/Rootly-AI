import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getClusters, isRequestAborted } from '../api/client';

const clusterStyles = `
  .cluster-container {
    max-height: min(580px, 70vh);
    overflow-y: auto;
    padding-right: 6px;
  }
  .cluster-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 4px;
  }
  .cluster-card {
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
    cursor: pointer;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }
  .cluster-card:hover {
    transform: translateY(-2px);
    background: rgba(30, 35, 48, 0.6);
    border-color: rgba(255, 255, 255, 0.15);
  }
  .cluster-card.critical {
    border-color: rgba(239, 68, 68, 0.3);
    box-shadow: 0 4px 20px rgba(239, 68, 68, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }
  .cluster-card.critical:hover {
    border-color: rgba(239, 68, 68, 0.55);
    box-shadow: 0 8px 30px rgba(239, 68, 68, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }
  .cluster-card.warning {
    border-color: rgba(245, 158, 11, 0.3);
    box-shadow: 0 4px 20px rgba(245, 158, 11, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }
  .cluster-card.warning:hover {
    border-color: rgba(245, 158, 11, 0.55);
    box-shadow: 0 8px 30px rgba(245, 158, 11, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }
  .cluster-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .cluster-title-container {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
  }
  .cluster-card-title {
    font-size: 13px;
    font-family: monospace;
    font-weight: 600;
    color: #e8eaf0;
    margin: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    background: rgba(0, 0, 0, 0.2);
    padding: 4px 8px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.04);
    flex: 1;
  }
  .cluster-member-count {
    background: #3b82f6;
    color: #fff;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 700;
    box-shadow: 0 0 8px rgba(59, 130, 246, 0.4);
    flex-shrink: 0;
  }
  .cluster-meta-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    gap: 12px;
  }
  .cluster-label {
    color: #8b8fa8;
  }
  .cluster-value {
    color: #e8eaf0;
    font-weight: 500;
  }
  .cluster-expanded-content {
    margin-top: 8px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    display: flex;
    flex-direction: column;
    gap: 12px;
    animation: clusterFadeIn 0.25s ease-out;
  }
  @keyframes clusterFadeIn {
    from { opacity: 0; transform: translateY(-6px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .cluster-services {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .service-tag {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #e8eaf0;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-family: monospace;
  }
  .incident-pill {
    display: inline-flex;
    align-items: center;
    background: rgba(59, 130, 246, 0.1);
    color: #3b82f6;
    border: 1px solid rgba(59, 130, 246, 0.25);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    margin-right: 6px;
    margin-bottom: 6px;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .incident-pill:hover {
    background: #3b82f6;
    color: #fff;
    box-shadow: 0 0 8px rgba(59, 130, 246, 0.3);
  }
  .incident-pill.critical {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
    border-color: rgba(239, 68, 68, 0.25);
  }
  .incident-pill.critical:hover {
    background: #ef4444;
    color: #fff;
    box-shadow: 0 0 8px rgba(239, 68, 68, 0.3);
  }
`;

function StatusPill({ status }) {
  const isOpen = status === 'open';
  const bgColor = isOpen ? 'rgba(245, 158, 11, 0.15)' : 'rgba(16, 185, 129, 0.15)';
  const color = isOpen ? '#f59e0b' : '#10b981';
  const border = isOpen ? '1px solid rgba(245, 158, 11, 0.3)' : '1px solid rgba(16, 185, 129, 0.3)';
  
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
        textTransform: 'uppercase',
      }}
    >
      {status}
    </span>
  );
}

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

export default function ClusterView() {
  const navigate = useNavigate();
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchClusters() {
      try {
        const data = await getClusters(
          { status: 'open', limit: 20 },
          controller.signal
        );
        if (!controller.signal.aborted) setClusters(data);
      } catch (err) {
        if (!isRequestAborted(err)) {
          console.error('Failed to fetch clusters:', err);
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    fetchClusters();
    const interval = setInterval(fetchClusters, 5000);
    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, []);

  if (loading) {
    return (
      <div style={{ color: '#8b8fa8', padding: 20, textAlign: 'center' }}>
        <div style={{ display: 'inline-block', width: 24, height: 24, border: '3px solid rgba(255,255,255,0.1)', borderTopColor: '#3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite', marginBottom: 8 }} />
        <div>Loading clusters...</div>
      </div>
    );
  }

  if (clusters.length === 0) {
    return (
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
        No active failure clusters found.
      </div>
    );
  }

  return (
    <div className="cluster-container">
      <style>{clusterStyles}</style>
      
      <div className="cluster-list">
        {clusters.map((cluster) => {
          const isCritical = cluster.severity === 'CRITICAL';
          const severityClass = isCritical ? 'critical' : 'warning';
          const isExpanded = expandedId === cluster.id;

          return (
            <div
              key={cluster.id}
              className={`cluster-card ${severityClass}`}
              onClick={() => setExpandedId(isExpanded ? null : cluster.id)}
            >
              <div className="cluster-card-header">
                <div className="cluster-title-container">
                  <span className="cluster-member-count" title="Cluster size">
                    {cluster.member_count}
                  </span>
                  <h4 className="cluster-card-title" title={cluster.representative_message}>
                    {cluster.representative_message}
                  </h4>
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <SeverityBadge severity={cluster.severity} />
                  <StatusPill status={cluster.status} />
                </div>
              </div>

              <div className="cluster-meta-row">
                <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                  <span className="cluster-label">Services:</span>
                  <div className="cluster-services">
                    {(cluster.affected_services || []).map((svc) => (
                      <span key={svc} className="service-tag">
                        {svc}
                      </span>
                    ))}
                  </div>
                </div>
                <div style={{ fontSize: 11, color: '#8b8fa8' }}>
                  Active: {timeAgo(cluster.last_seen)}
                </div>
              </div>

              <ConfidenceBar confidence={cluster.confidence} />

              {isExpanded && (
                <div
                  className="cluster-expanded-content"
                  onClick={(e) => e.stopPropagation()} // Prevent closing card when clicking inside
                >
                  <div>
                    <div style={{ color: '#8b8fa8', fontSize: 11, fontWeight: 600, marginBottom: 4 }}>
                      REPRESENTATIVE MESSAGE:
                    </div>
                    <pre
                      style={{
                        background: 'rgba(0, 0, 0, 0.3)',
                        border: '1px solid rgba(255, 255, 255, 0.05)',
                        borderRadius: 6,
                        padding: 8,
                        color: '#e8eaf0',
                        fontSize: 12,
                        fontFamily: 'monospace',
                        whiteSpace: 'pre-wrap',
                        overflowX: 'auto',
                        maxHeight: 120,
                        overflowY: 'auto',
                      }}
                    >
                      {cluster.representative_message}
                    </pre>
                  </div>

                  {cluster.related_incidents && cluster.related_incidents.length > 0 && (
                    <div>
                      <div style={{ color: '#8b8fa8', fontSize: 11, fontWeight: 600, marginBottom: 6 }}>
                        RELATED INCIDENTS:
                      </div>
                      <div>
                        {cluster.related_incidents.map((inc) => {
                          const isIncCritical = inc.severity === 'CRITICAL';
                          return (
                            <div
                              key={inc.id}
                              className={`incident-pill ${isIncCritical ? 'critical' : ''}`}
                              onClick={() => navigate(`/incidents/${inc.id}`)}
                            >
                              <span style={{ marginRight: 6, fontWeight: 700 }}>
                                {isIncCritical ? '🛑' : '⚠️'}
                              </span>
                              {inc.title}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  <div className="cluster-meta-row" style={{ fontSize: 11, borderTop: '1px solid rgba(255, 255, 255, 0.04)', paddingTop: 8 }}>
                    <div>
                      <span className="cluster-label">First Seen:</span>{' '}
                      <span className="cluster-value">{new Date(cluster.first_seen).toLocaleString()}</span>
                    </div>
                    <div>
                      <span className="cluster-label">Last Seen:</span>{' '}
                      <span className="cluster-value">{new Date(cluster.last_seen).toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
