import React, { useState, useEffect, useRef } from 'react';
import { connectLiveLogs, getServiceLogs } from '../api/client';

const SERVICES = [
  { value: 'user-service', label: 'User Service' },
  { value: 'order-service', label: 'Order Service' },
  { value: 'payment-service', label: 'Payment Service' },
];

export default function LogViewer({ initialService }) {
  const [selectedService, setSelectedService] = useState(initialService || 'user-service');
  const [selectedLevel, setSelectedLevel] = useState('');
  const [searchText, setSearchText] = useState('');
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [autoScroll, setAutoScroll] = useState(true);
  const [useWebSocket, setUseWebSocket] = useState(true);
  const logEndRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  useEffect(() => {
    if (!useWebSocket) return undefined;

    setLoading(true);
    const conn = connectLiveLogs({
      service: selectedService,
      level: selectedLevel,
      search: searchText,
      onLogs: (incoming) => {
        setLogs(incoming);
        setLoading(false);
      },
      onError: (err) => {
        console.warn('Log WebSocket error (will retry):', err);
        setLoading(false);
      },
    });
    wsRef.current = conn;

    return () => conn.close();
  }, [selectedService, selectedLevel, searchText, useWebSocket]);

  useEffect(() => {
    if (useWebSocket) return undefined;

    let active = true;
    let intervalId;

    async function fetchLogs() {
      setLoading(true);
      try {
        const params = { limit: 100 };
        if (selectedLevel) params.level = selectedLevel;
        if (searchText) params.search = searchText;
        const data = await getServiceLogs(selectedService, params);
        if (active) setLogs(data);
      } catch (err) {
        console.error('Error fetching logs:', err);
      } finally {
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
  }, [selectedService, selectedLevel, searchText, autoRefresh, useWebSocket]);

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
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
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
            }}
          >
            {SERVICES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
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
            }}
          >
            <option value="">All Levels</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>

          <input
            type="text"
            placeholder="Search logs..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{
              backgroundColor: '#1a1d27',
              color: '#e8eaf0',
              border: '1px solid #3a3d4a',
              borderRadius: 6,
              padding: '8px 12px',
              fontSize: 14,
              minWidth: 160,
            }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 13, color: '#8b8fa8' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} />
            Auto-scroll
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <input type="checkbox" checked={useWebSocket} onChange={(e) => setUseWebSocket(e.target.checked)} />
            Live WS
          </label>
          {!useWebSocket && (
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
              <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
              Poll (5s)
            </label>
          )}
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
          <div style={{ color: '#8b8fa8' }}>
            No logs found. Ensure services are running and load simulator is generating traffic.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {logs.map((log, i) => (
              <div key={`${log.timestamp}-${i}`} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', borderBottom: '1px solid #11141a', paddingBottom: 4 }}>
                <span style={{ color: '#5c6370', whiteSpace: 'nowrap' }}>
                  {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : 'N/A'}
                </span>
                <span style={{ color: getLevelColor(log.level), fontWeight: 600, minWidth: 70 }}>
                  [{log.level}]
                </span>
                {log.endpoint && <span style={{ color: '#c678dd' }}>{log.endpoint}</span>}
                {log.status_code > 0 && <span style={{ color: '#98c379' }}>{log.status_code}</span>}
                {log.latency_ms > 0 && <span style={{ color: '#d19a66' }}>{log.latency_ms}ms</span>}
                <span style={{ color: '#abb2bf', wordBreak: 'break-all' }}>{log.message}</span>
                {log.trace_id && (
                  <a
                    href={`http://localhost:16686/trace/${log.trace_id}`}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: '#56b6c2', fontSize: 11 }}
                  >
                    trace
                  </a>
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
