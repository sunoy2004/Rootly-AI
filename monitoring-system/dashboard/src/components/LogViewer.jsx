import React, { useState, useEffect, useRef, useCallback } from 'react';
import { getLogs } from '../api/client';

const SERVICES = [
  { value: 'all', label: 'All Services' },
  { value: 'user-service', label: 'User Service' },
  { value: 'order-service', label: 'Order Service' },
  { value: 'payment-service', label: 'Payment Service' },
];

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
    case 'DEBUG':
      return '#6b7280';
    default:
      return '#10b981';
  }
}

export default function LogViewer() {
  const [selectedService, setSelectedService] = useState('all');
  const [selectedLevel, setSelectedLevel] = useState('');
  const [searchText, setSearchText] = useState('');
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState(null);
  const logContainerRef = useRef(null);

  const fetchLogs = useCallback(async () => {
    if (paused) return;
    setLoading(true);
    setError(null);
    try {
      const params = { limit: 150 };
      if (selectedService && selectedService !== 'all') {
        params.service = selectedService;
      }
      if (selectedLevel) params.level = selectedLevel;
      if (searchText) params.search = searchText;
      const data = await getLogs(params);
      const list = Array.isArray(data) ? data : [];
      list.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      setLogs(list);
    } catch (err) {
      setError('Failed to load logs. Is incident-manager running on port 8013?');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [selectedService, selectedLevel, searchText, paused]);

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, [fetchLogs]);

  useEffect(() => {
    if (!autoScroll || paused || !logContainerRef.current) return;
    const el = logContainerRef.current;
    el.scrollTop = el.scrollHeight;
  }, [logs, autoScroll, paused]);

  const displayLogs = logs.filter((log) => {
    if (selectedLevel && log.level?.toUpperCase() !== selectedLevel.toUpperCase()) {
      return false;
    }
    if (searchText) {
      const q = searchText.toLowerCase();
      const hay = `${log.message} ${log.endpoint} ${log.trace_id}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

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
      <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <select
            value={selectedService}
            onChange={(e) => setSelectedService(e.target.value)}
            style={selectStyle}
          >
            {SERVICES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <select value={selectedLevel} onChange={(e) => setSelectedLevel(e.target.value)} style={selectStyle}>
            <option value="">All Levels</option>
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>
          <input
            type="text"
            placeholder="Search logs..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ ...selectStyle, minWidth: 180 }}
          />
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', fontSize: 13, color: '#8b8fa8' }}>
          <label style={labelStyle}>
            <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} />
            Auto-scroll
          </label>
          <label style={labelStyle}>
            <input type="checkbox" checked={paused} onChange={(e) => setPaused(e.target.checked)} />
            Pause
          </label>
          <button type="button" onClick={() => setLogs([])} style={btnStyle}>
            Clear
          </button>
          <button type="button" onClick={fetchLogs} style={btnStyle}>
            Refresh
          </button>
          <span>{displayLogs.length} lines</span>
        </div>
      </div>

      {error && (
        <div style={{ color: '#ef4444', marginBottom: 12, fontSize: 13 }}>{error}</div>
      )}

      <div ref={logContainerRef} style={logPanelStyle}>
        {loading && displayLogs.length === 0 ? (
          <div style={{ color: '#8b8fa8' }}>Fetching logs from Elasticsearch...</div>
        ) : displayLogs.length === 0 ? (
          <div style={{ color: '#8b8fa8' }}>
            No logs in Elasticsearch yet. Rebuild microservices (logger flush fix), run load simulator, wait ~5s for Fluent Bit.
          </div>
        ) : (
          displayLogs.map((log, i) => (
            <div
              key={`${log.timestamp}-${log.service}-${i}`}
              style={{
                display: 'grid',
                gridTemplateColumns: '90px 110px 70px 1fr',
                gap: 8,
                padding: '4px 0',
                borderBottom: '1px solid #11141a',
                fontSize: 12,
                alignItems: 'start',
              }}
            >
              <span style={{ color: '#5c6370' }}>
                {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '—'}
              </span>
              <span style={{ color: '#c678dd' }}>{log.service || '—'}</span>
              <span style={{ color: getLevelColor(log.level), fontWeight: 600 }}>{log.level}</span>
              <div>
                {log.endpoint && <span style={{ color: '#98c379', marginRight: 8 }}>{log.endpoint}</span>}
                {log.status_code > 0 && <span style={{ color: '#d19a66', marginRight: 8 }}>{log.status_code}</span>}
                {log.latency_ms > 0 && <span style={{ color: '#d19a66', marginRight: 8 }}>{Math.round(log.latency_ms)}ms</span>}
                <span style={{ color: '#abb2bf' }}>{log.message}</span>
                {log.trace_id && (
                  <a
                    href={`http://localhost:16686/trace/${log.trace_id}`}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: '#56b6c2', marginLeft: 8 }}
                  >
                    trace
                  </a>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

const selectStyle = {
  backgroundColor: '#1a1d27',
  color: '#e8eaf0',
  border: '1px solid #3a3d4a',
  borderRadius: 6,
  padding: '8px 12px',
  fontSize: 14,
};

const labelStyle = { display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' };

const btnStyle = {
  backgroundColor: '#2a2d3a',
  color: '#e8eaf0',
  border: '1px solid #3a3d4a',
  borderRadius: 6,
  padding: '6px 10px',
  cursor: 'pointer',
  fontSize: 12,
};

const logPanelStyle = {
  backgroundColor: '#0a0c10',
  borderRadius: 8,
  padding: 16,
  fontFamily: 'monospace',
  height: 380,
  overflowY: 'auto',
  overflowX: 'hidden',
  border: '1px solid #1a1d27',
};
