import React, { useState, useEffect, useRef } from 'react';
import { getServiceLogs } from '../api/client';

const SERVICES = [
  { value: 'user-service', label: 'User Service' },
  { value: 'order-service', label: 'Order Service' },
  { value: 'payment-service', label: 'Payment Service' }
];

export default function LogViewer({ initialService }) {
  const [selectedService, setSelectedService] = useState(initialService || 'user-service');
  const [selectedLevel, setSelectedLevel] = useState('');
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const logEndRef = useRef(null);

  useEffect(() => {
    let active = true;
    let intervalId;

    async function fetchLogs() {
      setLoading(true);
      try {
        const params = {};
        if (selectedLevel) {
          params.level = selectedLevel;
        }
        const data = await getServiceLogs(selectedService, params);
        if (active) {
          setLogs(data);
          setLoading(false);
        }
      } catch (err) {
        console.error('Error fetching logs:', err);
        if (active) setLoading(false);
      }
    }

    fetchLogs();

    if (autoRefresh) {
      intervalId = setInterval(fetchLogs, 5000);
    }

    return () => {
      active = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, [selectedService, selectedLevel, autoRefresh]);

  function getLevelColor(level) {
    switch (level?.toUpperCase()) {
      case 'ERROR':
      case 'CRITICAL':
        return '#ef4444';
      case 'WARN':
      case 'WARNING':
        return '#f59e0b';
      case 'INFO':
        return '#3b82f6';
      default:
        return '#10b981';
    }
  }

  return (
    <div
      style={{
        backgroundColor: '#161922',
        border: '1px solid #2a2d3a',
        borderRadius: 12,
        padding: 20,
        color: '#e8eaf0',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
          marginBottom: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <select
            value={selectedService}
            onChange={(e) => setSelectedService(e.target.value)}
            style={{
              backgroundColor: '#1a1d27',
              color: '#e8eaf0',
              border: '1px solid #3a3d4a',
              borderRadius: 6,
              padding: '8px 12px',
              fontSize: 14,
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            {SERVICES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>

          <select
            value={selectedLevel}
            onChange={(e) => setSelectedLevel(e.target.value)}
            style={{
              backgroundColor: '#1a1d27',
              color: '#e8eaf0',
              border: '1px solid #3a3d4a',
              borderRadius: 6,
              padding: '8px 12px',
              fontSize: 14,
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            <option value="">All Levels</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#8b8fa8', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              style={{ cursor: 'pointer' }}
            />
            Auto-refresh (5s)
          </label>
        </div>
      </div>

      <div
        style={{
          backgroundColor: '#0a0c10',
          borderRadius: 8,
          padding: 16,
          fontFamily: 'monospace',
          fontSize: 13,
          height: 350,
          overflowY: 'auto',
          border: '1px solid #1a1d27',
        }}
      >
        {loading && logs.length === 0 ? (
          <div style={{ color: '#8b8fa8' }}>Fetching logs...</div>
        ) : logs.length === 0 ? (
          <div style={{ color: '#8b8fa8' }}>No logs found for this service/level selection.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {logs.map((log, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', borderBottom: '1px solid #11141a', paddingBottom: 4 }}>
                <span style={{ color: '#5c6370', whiteSpace: 'nowrap' }}>
                  {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : 'N/A'}
                </span>
                <span
                  style={{
                    color: getLevelColor(log.level),
                    fontWeight: 600,
                    minWidth: 70,
                    display: 'inline-block',
                  }}
                >
                  [{log.level}]
                </span>
                <span style={{ color: '#abb2bf', wordBreak: 'break-all' }}>{log.message}</span>
                {log.trace_id && (
                  <span style={{ color: '#56b6c2', fontSize: 11, cursor: 'pointer' }} title="Trace ID">
                    (trace: {log.trace_id.substring(0, 7)})
                  </span>
                )}
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        )}
      </div>
    </div>
  );
}
