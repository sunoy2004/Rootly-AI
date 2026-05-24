import React, { useState, useEffect, useRef, useCallback } from 'react';
import { connectLiveLogs } from '../api/client';

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

  useEffect(() => {
    if (paused) return;
    setLoading(true);

    const conn = connectLiveLogs({
      service: selectedService === 'all' ? '' : selectedService,
      level: selectedLevel,
      search: searchText,
      onConnect: () => {
        setError(null);
      },
      onLogs: (newLogs) => {
        console.log("frontend received log event", newLogs);
        setLogs(newLogs);
        setError(null);
        setLoading(false);
      },
      onError: (err) => {
        console.error("WS logs error:", err);
        setError("WebSocket connection failed. Retrying...");
        setLoading(false);
      }
    });

    return () => {
      conn.close();
    };
  }, [selectedService, selectedLevel, searchText, paused]);

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

  console.log(`rendering ${displayLogs.length} logs`);

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
          <div style={{ color: '#8b8fa8', display: 'flex', alignItems: 'center', gap: 8, padding: 12 }}>
            <div className="spinner" />
            <span>Streaming logs from Elasticsearch...</span>
          </div>
        ) : displayLogs.length === 0 ? (
          <div style={{ color: '#8b8fa8', padding: 12 }}>
            No logs found. Start the load simulator to see live events streaming here.
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
                transition: 'background-color 0.2s',
                borderRadius: 4,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.02)' }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
            >
              <span style={{ color: '#636d83', fontFamily: 'monospace' }}>
                {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '—'}
              </span>
              <span style={{ color: '#c678dd', fontWeight: 500 }}>{log.service || '—'}</span>
              <span style={{ color: getLevelColor(log.level), fontWeight: 600 }}>{log.level}</span>
              <div>
                {log.endpoint && <span style={{ color: '#98c379', marginRight: 8, fontFamily: 'monospace' }}>{log.endpoint}</span>}
                {log.status_code > 0 && (
                  <span
                    style={{
                      color: log.status_code >= 400 ? '#ef4444' : '#d19a66',
                      marginRight: 8,
                      fontWeight: 600,
                    }}
                  >
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
                    style={{
                      color: '#61afef',
                      marginLeft: 8,
                      textDecoration: 'none',
                      borderBottom: '1px dashed #61afef',
                      fontSize: 11,
                    }}
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
  transition: 'border-color 0.2s',
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
  transition: 'background-color 0.2s',
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
  boxShadow: 'inset 0 4px 12px 0 rgba(0, 0, 0, 0.5)',
};
