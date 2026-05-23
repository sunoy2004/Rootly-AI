import React, { useState, useEffect } from 'react';
import { getClusters } from '../api/client';

function StatusPill({ status }) {
  const color = status === 'open' ? '#f59e0b' : '#10b981';
  return (
    <span
      style={{
        backgroundColor: color,
        color: '#fff',
        padding: '2px 10px',
        borderRadius: 12,
        fontSize: 11,
        fontWeight: 600,
        textTransform: 'lowercase',
      }}
    >
      {status}
    </span>
  );
}

function ServiceTag({ service }) {
  return (
    <span
      style={{
        backgroundColor: '#2a2d3a',
        color: '#e8eaf0',
        padding: '2px 8px',
        borderRadius: 4,
        fontSize: 10,
        marginRight: 4,
      }}
    >
      {service}
    </span>
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
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    async function fetchClusters() {
      try {
        const data = await getClusters({ status: 'open', limit: 20 });
        setClusters(data);
      } catch (err) {
        console.error('Failed to fetch clusters:', err);
      } finally {
        setLoading(false);
      }
    }

    fetchClusters();
    const interval = setInterval(fetchClusters, 60000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <div style={{ color: '#8b8fa8', padding: 20 }}>Loading clusters...</div>;
  }

  if (clusters.length === 0) {
    return <div style={{ color: '#8b8fa8', padding: 20 }}>No open clusters</div>;
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #2a2d3a' }}>
            <th style={{ textAlign: 'left', padding: '8px', color: '#8b8fa8', fontSize: 12 }}>Message</th>
            <th style={{ textAlign: 'left', padding: '8px', color: '#8b8fa8', fontSize: 12 }}>Count</th>
            <th style={{ textAlign: 'left', padding: '8px', color: '#8b8fa8', fontSize: 12 }}>Services</th>
            <th style={{ textAlign: 'left', padding: '8px', color: '#8b8fa8', fontSize: 12 }}>Status</th>
            <th style={{ textAlign: 'left', padding: '8px', color: '#8b8fa8', fontSize: 12 }}>Last Seen</th>
          </tr>
        </thead>
        <tbody>
          {clusters.map((cluster) => (
            <React.Fragment key={cluster.id}>
              <tr
                onClick={() => setExpandedId(expandedId === cluster.id ? null : cluster.id)}
                style={{
                  cursor: 'pointer',
                  borderBottom: '1px solid #2a2d3a',
                  backgroundColor: 'transparent',
                }}
              >
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
                    {cluster.representative_message}
                  </span>
                </td>
                <td style={{ padding: '10px 8px' }}>
                  <span
                    style={{
                      backgroundColor: '#3b82f6',
                      color: '#fff',
                      padding: '2px 8px',
                      borderRadius: 12,
                      fontSize: 12,
                      fontWeight: 600,
                    }}
                  >
                    {cluster.member_count}
                  </span>
                </td>
                <td style={{ padding: '10px 8px' }}>
                  {(cluster.affected_services || []).map((svc) => (
                    <ServiceTag key={svc} service={svc} />
                  ))}
                </td>
                <td style={{ padding: '10px 8px' }}>
                  <StatusPill status={cluster.status} />
                </td>
                <td style={{ padding: '10px 8px', color: '#8b8fa8', fontSize: 12 }}>
                  {timeAgo(cluster.last_seen)}
                </td>
              </tr>
              {expandedId === cluster.id && (
                <tr style={{ backgroundColor: '#1a1d27' }}>
                  <td colSpan={5} style={{ padding: 16 }}>
                    <div style={{ marginBottom: 8 }}>
                      <strong style={{ color: '#8b8fa8', fontSize: 12 }}>Full Message:</strong>
                      <p style={{ color: '#e8eaf0', fontSize: 13, margin: '4px 0' }}>
                        {cluster.representative_message}
                      </p>
                    </div>
                    <div>
                      <strong style={{ color: '#8b8fa8', fontSize: 12 }}>Member Count by Service:</strong>
                      <ul style={{ margin: '4px 0', paddingLeft: 20 }}>
                        {(cluster.affected_services || []).map((svc) => (
                          <li key={svc} style={{ color: '#e8eaf0', fontSize: 12 }}>
                            {svc}: {cluster.member_count}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
