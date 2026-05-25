import React, { useState, useEffect, useRef, useCallback } from 'react';
import { getLogs } from '../api/client';

const SERVICES = [
  { value: 'payment-service', label: 'Payment Service' },
  { value: 'order-service', label: 'Order Service' },
  { value: 'user-service', label: 'User Service' },
  { value: 'all', label: 'All Services' },
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
  const [selectedService, setSelectedService] = useState('payment-service');
  const [selectedLevel, setSelectedLevel] = useState('');
  const [searchText, setSearchText] = useState('');
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState(null);
  const logContainerRef = useRef(null);

  const fetchLogs = useCallback(async (signal) => {
    if (paused) return;
    setLoading(true);
    setError(null);
    try {
      const params = { limit: 100 };
      if (selectedService && selectedService !== 'all') {
        params.service = selectedService;
      }
      if (selectedLevel) params.level = selectedLevel;
      if (searchText) params.search = searchText;
      const data = await getLogs(params, signal);
      const list = Array.isArray(data) ? data : [];
      list.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      setLogs(list);
    } catch (err) {
      if (err?.code !== 'ERR_CANCELED' && err?.name !== 'CanceledError') {
        setError('Failed to load logs. Try a single service filter.');
      }
    } finally {
      setLoading(false);
    }
  }, [selectedService, selectedLevel, searchText, paused]);

  useEffect(() => {
    const controller = new AbortController();
    const start = setTimeout(() => fetchLogs(controller.signal), 3000);
    const interval = setInterval(() => fetchLogs(controller.signal), 8000);
    return () => {
      clearTimeout(start);
      clearInterval(interval);
      controller.abort();
    };
  }, [fetchLogs]);

  useEffect(() => {
    if (!autoScroll || paused || !logContainerRef.current) return;
    logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
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
        background: 'linear-gradient(135deg, rgba(22, 25, 34, 0.7) 0%, rgba(15, 17, 23, 0.8) 100%)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: 16,
        padding: 24,
        color: '#e8eaf0',
        boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
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
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', fontSize: 13, color: '#8b8fa8' }}>
          <label style={labelStyle}>
            <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} style={checkboxStyle} />
            Auto-scroll
          </label>
          <label style={labelStyle}>
            <input type="checkbox" checked={paused} onChange={(e) => setPaused(e.target.checked)} style={checkboxStyle} />
            Pause
          </label>
          <button type="button" onClick={() => fetchLogs()} style={btnStyle}>
            Refresh
          </button>
          <button type="button" onClick={() => setLogs([])} style={btnStyle}>
            Clear
          </button>
          <span>{displayLogs.length} lines</span>
        </div>
      </div>

      {error && (
        <div style={{ color: '#ef4444', marginBottom: 12, fontSize: 13 }}>{error}</div>
      )}

      <div ref={logContainerRef} style={logPanelStyle}>
        {loading && displayLogs.length === 0 ? (
          <div style={{ color: '#8b8fa8', padding: 12 }}>Loading logs...</div>
        ) : displayLogs.length === 0 ? (
          <div style={{ color: '#8b8fa8', padding: 12 }}>
            No logs found. Run the load simulator, wait ~10s, then click Refresh.
          </div>
        ) : (
          displayLogs.map((log, i) => (
            <div
              key={`${log.timestamp}-${log.service}-${i}`}
              style={{
                display: 'grid',
                gridTemplateColumns: '100px 130px 80px 1fr',
                gap: 12,
                padding: '8px 12px',
                borderBottom: '1px solid rgba(255, 255, 255, 0.03)',
                fontSize: 12,
                alignItems: 'start',
              }}
            >
              <span style={{ color: '#636d83', fontFamily: 'monospace' }}>
                {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '—'}
              </span>
              <span style={{ color: '#c678dd', fontWeight: 500 }}>{log.service || '—'}</span>
              <span style={{ color: getLevelColor(log.level), fontWeight: 600 }}>{log.level}</span>
              <div>
                {log.endpoint && <span style={{ color: '#98c379', marginRight: 8, fontFamily: 'monospace' }}>{log.endpoint}</span>}
                {log.status_code > 0 && (
                  <span style={{ color: log.status_code >= 400 ? '#ef4444' : '#d19a66', marginRight: 8, fontWeight: 600 }}>
                    {log.status_code}
                  </span>
                )}
                {log.latency_ms > 0 && <span style={{ color: '#56b6c2', marginRight: 8 }}>{Math.round(log.latency_ms)}ms</span>}
                <span style={{ color: '#abb2bf', wordBreak: 'break-all' }}>{log.message}</span>
                {log.trace_id && (
                  <a
                    href={`http://localhost:16686/trace/${log.trace_id}`}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: '#61afef', marginLeft: 8, textDecoration: 'none', fontSize: 11 }}
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
  backgroundColor: '#1e222b',
  color: '#e8eaf0',
  border: '1px solid rgba(255, 255, 255, 0.1)',
  borderRadius: 8,
  padding: '8px 16px',
  fontSize: 13,
  outline: 'none',
  cursor: 'pointer',
};

const labelStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  cursor: 'pointer',
  userSelect: 'none',
};

const checkboxStyle = {
  accentColor: '#3b82f6',
  cursor: 'pointer',
};

const btnStyle = {
  backgroundColor: '#282c34',
  color: '#e8eaf0',
  border: '1px solid rgba(255, 255, 255, 0.1)',
  borderRadius: 8,
  padding: '6px 12px',
  cursor: 'pointer',
  fontSize: 12,
  fontWeight: 500,
};

const logPanelStyle = {
  backgroundColor: '#1e222b',
  borderRadius: 12,
  padding: '12px 6px',
  fontFamily: 'Consolas, Monaco, monospace',
  height: 400,
  overflowY: 'auto',
  overflowX: 'hidden',
  border: '1px solid rgba(255, 255, 255, 0.05)',
};
