import React, { useState } from 'react';

function LogLine({ log }) {
  const isObj = typeof log === 'object' && log !== null;
  if (!isObj) {
    return (
      <pre style={preStyle}>{String(log)}</pre>
    );
  }
  return (
    <div style={{ borderBottom: '1px solid #11141a', padding: '8px 0', fontSize: 12 }}>
      <div style={{ color: '#5c6370' }}>
        {log.timestamp ? new Date(log.timestamp).toLocaleString() : ''}
        {' · '}
        <span style={{ color: '#c678dd' }}>{log.service}</span>
        {' · '}
        <span style={{ color: log.level === 'ERROR' ? '#ef4444' : '#f59e0b' }}>{log.level}</span>
      </div>
      <div style={{ color: '#abb2bf', marginTop: 4 }}>
        {log.endpoint && <span style={{ marginRight: 8 }}>{log.endpoint}</span>}
        {log.message}
      </div>
      {log.trace_id && (
        <a
          href={`http://localhost:16686/trace/${log.trace_id}`}
          target="_blank"
          rel="noreferrer"
          style={{ color: '#56b6c2', fontSize: 11 }}
        >
          Open trace in Jaeger
        </a>
      )}
    </div>
  );
}

export default function RelatedErrorLogs({ logs = [], rawLogs = [] }) {
  const [expanded, setExpanded] = useState(true);
  const [search, setSearch] = useState('');

  const items = rawLogs.length > 0 ? rawLogs : logs;
  const filtered = items.filter((line) => {
    if (!search) return true;
    const text = typeof line === 'string' ? line : JSON.stringify(line);
    return text.toLowerCase().includes(search.toLowerCase());
  });

  return (
    <div style={{ backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12, padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          style={{
            background: 'none',
            border: 'none',
            color: '#e8eaf0',
            fontSize: 16,
            fontWeight: 600,
            cursor: 'pointer',
            padding: 0,
          }}
        >
          Related Error Logs ({filtered.length})
        </button>
        <input
          type="text"
          placeholder="Search logs..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            backgroundColor: '#0f1117',
            border: '1px solid #2a2d3a',
            borderRadius: 6,
            padding: '6px 10px',
            color: '#e8eaf0',
            fontSize: 12,
            width: 180,
          }}
        />
      </div>

      {expanded && (
        <div style={{ maxHeight: 320, overflowY: 'auto', overflowX: 'hidden' }}>
          {filtered.length === 0 ? (
            <p style={{ color: '#8b8fa8', fontSize: 13, margin: 0 }}>
              No related error logs in Elasticsearch for this service/time window.
            </p>
          ) : (
            filtered.map((log, i) => <LogLine key={i} log={log} />)
          )}
        </div>
      )}
    </div>
  );
}

const preStyle = {
  margin: 0,
  color: '#e8eaf0',
  fontSize: 12,
  fontFamily: 'monospace',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
};
