import React, { useState, useEffect } from 'react';
import { getAnomalies, connectLiveAnomalies, isRequestAborted } from '../api/client';

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
    fetchAnomalies();
    const interval = setInterval(fetchAnomalies, 60000);
    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    let conn;
    const timer = setTimeout(() => {
      conn = connectLiveAnomalies({
      onAnomaly: (anomaly) => {
        setAnomalies((prev) => {
          const key = `${anomaly.service}-${anomaly.metric}-${anomaly.timestamp}`;
          if (prev.some((a) => `${a.service}-${a.metric}-${a.timestamp || a.created_at}` === key)) {
            return prev;
          }
          return [anomaly, ...prev].slice(0, 30);
        });
      },
      onError: () => {},
    });
    }, 1000);
    return () => {
      clearTimeout(timer);
      conn?.close();
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
        <div style={{ overflowX: 'auto' }}>
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
                  <td style={{ padding: 8, color: '#e8eaf0' }}>{a.service}</td>
                  <td style={{ padding: 8, color: '#e8eaf0' }}>{a.metric}</td>
                  <td style={{ padding: 8 }}><SeverityBadge severity={a.severity} /></td>
                  <td style={{ padding: 8, color: '#e8eaf0' }}>{a.current_value?.toFixed?.(4) ?? a.current_value}</td>
                  <td style={{ padding: 8, color: '#e8eaf0' }}>{a.z_score?.toFixed?.(2) ?? '-'}</td>
                  <td style={{ padding: 8, color: '#8b8fa8' }}>{a.detector}</td>
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
