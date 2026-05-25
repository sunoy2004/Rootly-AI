import React, { useState, useEffect } from 'react';
import { getAnomalies, isRequestAborted } from '../api/client';
import { safeNumber, safeString } from '../utils/safeRender';

function SeverityBadge({ severity }) {
  const color = severity === 'CRITICAL' ? '#ef4444' : '#f59e0b';
  return (
    <span style={{ backgroundColor: color, color: '#fff', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
      {severity}
    </span>
  );
}

export default function AnomalyPanel() {
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchAnomalies() {
      try {
        const data = await getAnomalies({ limit: 20 }, controller.signal);
        setAnomalies(Array.isArray(data) ? data : data.anomalies || []);
      } catch (err) {
        if (!isRequestAborted(err)) {
          console.error('Failed to fetch anomalies:', err);
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    const start = setTimeout(fetchAnomalies, 1500);
    const interval = setInterval(fetchAnomalies, 45000);
    return () => {
      clearTimeout(start);
      controller.abort();
      clearInterval(interval);
    };
  }, []);

  return (
    <div style={{ backgroundColor: '#161922', border: '1px solid #2a2d3a', borderRadius: 12, padding: 20 }}>
      <h3 style={{ color: '#e8eaf0', margin: '0 0 16px', fontSize: 16 }}>Recent Anomalies</h3>
      {loading ? (
        <div style={{ color: '#8b8fa8' }}>Loading anomalies...</div>
      ) : anomalies.length === 0 ? (
        <div style={{ color: '#8b8fa8' }}>No anomalies detected yet. Run the load simulator.</div>
      ) : (
        <div style={{ maxHeight: 300, overflowY: 'auto', overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #2a2d3a' }}>
                <th style={{ textAlign: 'left', padding: 8, color: '#8b8fa8' }}>Service</th>
                <th style={{ textAlign: 'left', padding: 8, color: '#8b8fa8' }}>Metric</th>
                <th style={{ textAlign: 'left', padding: 8, color: '#8b8fa8' }}>Severity</th>
                <th style={{ textAlign: 'left', padding: 8, color: '#8b8fa8' }}>Value</th>
                <th style={{ textAlign: 'left', padding: 8, color: '#8b8fa8' }}>Z-Score</th>
                <th style={{ textAlign: 'left', padding: 8, color: '#8b8fa8' }}>Detector</th>
                <th style={{ textAlign: 'left', padding: 8, color: '#8b8fa8' }}>Time</th>
              </tr>
            </thead>
            <tbody>
              {anomalies.map((a, idx) => (
                <tr key={a.id || `${a.service}-${a.metric}-${idx}`} style={{ borderBottom: '1px solid #1a1d27' }}>
                  <td style={{ padding: 8, color: '#e8eaf0' }}>{safeString(a.service)}</td>
                  <td style={{ padding: 8, color: '#e8eaf0' }}>{safeString(a.metric)}</td>
                  <td style={{ padding: 8 }}><SeverityBadge severity={safeString(a.severity, 'WARNING')} /></td>
                  <td style={{ padding: 8, color: '#e8eaf0' }}>{safeNumber(a.current_value, 0).toFixed(4)}</td>
                  <td style={{ padding: 8, color: '#e8eaf0' }}>{safeNumber(a.z_score, 0).toFixed(2)}</td>
                  <td style={{ padding: 8, color: '#8b8fa8' }}>{safeString(a.detector)}</td>
                  <td style={{ padding: 8, color: '#8b8fa8', fontSize: 12 }}>
                    {a.created_at || a.timestamp
                      ? new Date(a.created_at || a.timestamp).toLocaleTimeString()
                      : '-'}
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
