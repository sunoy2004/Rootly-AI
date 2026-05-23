import React, { useState, useEffect } from 'react';
import { triggerAIAnalysis, getIncident } from '../api/client';

function ConfidenceProgress({ confidence }) {
  if (!confidence && confidence !== 0) return null;

  const pct = Math.min(100, Math.max(0, confidence * 100));
  let color = '#ef4444';
  if (pct > 70) color = '#10b981';
  else if (pct > 40) color = '#f59e0b';

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ color: '#8b8fa8', fontSize: 12 }}>Confidence</span>
        <span style={{ color: '#e8eaf0', fontSize: 12 }}>{pct.toFixed(0)}%</span>
      </div>
      <div
        style={{
          width: '100%',
          height: 8,
          backgroundColor: '#2a2d3a',
          borderRadius: 4,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            backgroundColor: color,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
    </div>
  );
}

function EvidenceList({ evidence }) {
  if (!evidence || evidence.length === 0) return null;

  return (
    <div style={{ marginBottom: 12 }}>
      <strong style={{ color: '#8b8fa8', fontSize: 12 }}>Evidence:</strong>
      <ul style={{ margin: '4px 0', paddingLeft: 20 }}>
        {evidence.map((item, idx) => (
          <li key={idx} style={{ color: '#e8eaf0', fontSize: 13 }}>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function DebugSteps({ steps }) {
  if (!steps || steps.length === 0) return null;

  return (
    <div style={{ marginBottom: 12 }}>
      <strong style={{ color: '#8b8fa8', fontSize: 12 }}>Debug Steps:</strong>
      <ol style={{ margin: '4px 0', paddingLeft: 20 }}>
        {steps.map((step, idx) => (
          <li
            key={idx}
            style={{
              color: '#e8eaf0',
              fontSize: 13,
              marginBottom: 4,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <span
              style={{
                width: 14,
                height: 14,
                border: '1px solid #2a2d3a',
                borderRadius: 2,
                flexShrink: 0,
              }}
            />
            {step}
          </li>
        ))}
      </ol>
    </div>
  );
}

function SourceTag({ source }) {
  const label = source === 'RULE_ENGINE' ? 'Rule Engine' : 'AI Agent';
  const color = source === 'RULE_ENGINE' ? '#3b82f6' : '#8b5cf6';

  if (source !== 'RULE_ENGINE' && source !== 'AI_AGENT') return null;

  return (
    <span
      style={{
        backgroundColor: color,
        color: '#fff',
        padding: '4px 10px',
        borderRadius: 6,
        fontSize: 11,
        fontWeight: 600,
      }}
    >
      {label}
    </span>
  );
}

export default function RootCauseCard({ incident }) {
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState(null);

  useEffect(() => {
    async function pollAnalysis() {
      if (
        incident.source === 'AI_AGENT' &&
        !incident.root_cause &&
        incident.id
      ) {
        setAnalyzing(true);
        try {
          const result = await triggerAIAnalysis(incident.id);
          setAnalysis(result);
        } catch (err) {
          console.error('Failed to trigger AI analysis:', err);
        }
      }
    }

    pollAnalysis();
  }, [incident]);

  const rootCause = analysis?.probable_cause || incident.root_cause;
  const detailedExplanation =
    analysis?.detailed_explanation || incident.detailed_explanation;
  const confidence = analysis?.confidence ?? incident.confidence;
  const evidence = analysis?.evidence || incident.evidence || [];
  const debugSteps = analysis?.debug_steps || incident.debug_steps || [];

  if (analyzing && !rootCause) {
    return (
      <div
        style={{
          backgroundColor: '#1a1d27',
          border: '1px solid #2a2d3a',
          borderRadius: 12,
          padding: 20,
          textAlign: 'center',
        }}
      >
        <div
          style={{
            width: 24,
            height: 24,
            border: '2px solid #3b82f6',
            borderTopColor: 'transparent',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            margin: '0 auto 12px',
          }}
        />
        <p style={{ color: '#8b8fa8', fontSize: 14 }}>AI is analyzing...</p>
      </div>
    );
  }

  if (!rootCause) {
    return (
      <div
        style={{
          backgroundColor: '#1a1d27',
          border: '1px solid #2a2d3a',
          borderRadius: 12,
          padding: 20,
        }}
      >
        <p style={{ color: '#8b8fa8', fontSize: 14 }}>No root cause analysis available yet.</p>
      </div>
    );
  }

  return (
    <div
      style={{
        backgroundColor: '#1a1d27',
        border: '1px solid #2a2d3a',
        borderRadius: 12,
        padding: 20,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <h3 style={{ color: '#e8eaf0', margin: 0, fontSize: 16 }}>Root Cause Analysis</h3>
        <SourceTag source={incident.source} />
      </div>

      <p style={{ color: '#e8eaf0', fontSize: 18, marginBottom: 12 }}>{rootCause}</p>

      {detailedExplanation && (
        <p style={{ color: '#8b8fa8', fontSize: 14, marginBottom: 12 }}>
          {detailedExplanation}
        </p>
      )}

      <ConfidenceProgress confidence={confidence} />

      <EvidenceList evidence={evidence} />
      <DebugSteps steps={debugSteps} />

      {analysis?.similar_to_past_incident && (
        <div
          style={{
            backgroundColor: '#2a2d3a',
            padding: 10,
            borderRadius: 6,
            marginTop: 12,
          }}
        >
          <span style={{ color: '#8b8fa8', fontSize: 12 }}>Similar to past incident: </span>
          <span style={{ color: '#3b82f6', fontSize: 12 }}>
            {analysis.past_incident_reference}
          </span>
        </div>
      )}
    </div>
  );
}
