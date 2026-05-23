import React from 'react';

function TraceLink({ traceId }) {
  const shortId = traceId.slice(0, 8);
  const url = `http://localhost:16686/trace/${traceId}`;

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        color: '#3b82f6',
        textDecoration: 'none',
        fontSize: 13,
        padding: '4px 0',
      }}
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
        <polyline points="15 3 21 3 21 9" />
        <line x1="10" y1="14" x2="21" y2="3" />
      </svg>
      View trace {shortId}...
    </a>
  );
}

export default function TraceViewer({ traceIds }) {
  if (!traceIds || traceIds.length === 0) {
    return (
      <div style={{ color: '#8b8fa8', fontSize: 13 }}>
        No traces available
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {traceIds.map((traceId) => (
        <TraceLink key={traceId} traceId={traceId} />
      ))}
    </div>
  );
}
