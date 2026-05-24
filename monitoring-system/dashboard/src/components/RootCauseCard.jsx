import React, { useState, useEffect } from 'react';
import { triggerAIAnalysis } from '../api/client';
import { dedupeLists, safeString, safeStringList } from '../utils/safeRender';

function parseAnalysis(incident) {
  const base = incident.ai_analysis || {};
  let raw = base.raw_response;
  if (typeof raw === 'string') {
    try {
      raw = JSON.parse(raw);
    } catch {
      raw = {};
    }
  }
  if (typeof raw !== 'object' || raw === null) raw = {};

  const merged = {
    root_cause: raw.root_cause || base.root_cause || incident.root_cause,
    summary: raw.summary || base.summary || incident.summary,
    debug_steps: raw.debug_steps || base.debug_steps || incident.debug_steps || [],
    recommended_actions:
      raw.recommended_actions || base.recommended_actions || [],
    evidence: raw.evidence || base.evidence || incident.evidence || [],
    affected_services:
      raw.affected_services || base.affected_services || incident.affected_services || [],
    confidence: raw.confidence ?? base.confidence ?? incident.confidence,
  };

  const deduped = dedupeLists(merged.debug_steps, merged.recommended_actions);
  let debugSteps = deduped.debug_steps;
  if (!debugSteps.length) {
    const svc = (merged.affected_services?.[0] || incident.affected_services?.[0] || 'service');
    debugSteps = [
      `Search Elasticsearch for ERROR/WARNING logs on ${svc} (last 30 min)`,
      `Open Jaeger and inspect traces for ${svc}`,
      `Check Prometheus metrics: error rate, p95 latency, DB errors`,
      'Review recent anomalies for matching metric spikes',
      'Verify load patterns and dependency health',
    ];
  }
  return { ...merged, ...deduped, debug_steps: debugSteps };
}

function Section({ title, children, accent = '#3b82f6' }) {
  if (children === null || children === undefined || children === false) return null;
  if (Array.isArray(children) && children.length === 0) return null;
  return (
    <div style={{ marginBottom: 16 }}>
      <div
        style={{
          color: accent,
          fontSize: 12,
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          marginBottom: 8,
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

function ConfidenceProgress({ confidence }) {
  const c = typeof confidence === 'number' ? confidence : 0;
  const pct = Math.min(100, Math.max(0, c * 100));
  let color = '#ef4444';
  if (pct > 70) color = '#10b981';
  else if (pct > 40) color = '#f59e0b';

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ color: '#8b8fa8', fontSize: 12 }}>Confidence</span>
        <span style={{ color: '#e8eaf0', fontSize: 12 }}>{pct.toFixed(0)}%</span>
      </div>
      <div style={{ width: '100%', height: 8, backgroundColor: '#2a2d3a', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', backgroundColor: color }} />
      </div>
    </div>
  );
}

function BulletList({ items, ordered = false }) {
  const list = safeStringList(items);
  if (!list.length) return null;
  const Tag = ordered ? 'ol' : 'ul';
  return (
    <Tag style={{ margin: 0, paddingLeft: 20, color: '#e8eaf0', fontSize: 13, lineHeight: 1.6 }}>
      {list.map((item, idx) => (
        <li key={idx} style={{ marginBottom: 6 }}>{item}</li>
      ))}
    </Tag>
  );
}

export default function RootCauseCard({ incident }) {
  const [analyzing, setAnalyzing] = useState(false);
  const [extra, setExtra] = useState(null);

  useEffect(() => {
    if (incident?.root_cause || incident?.ai_analysis) return undefined;
    if (incident?.source !== 'AI_AGENT' || !incident?.id) return undefined;

    let cancelled = false;
    async function poll() {
      setAnalyzing(true);
      try {
        const result = await triggerAIAnalysis(incident.id);
        if (!cancelled) setExtra(result);
      } catch (err) {
        console.error('Failed to trigger AI analysis:', err);
      } finally {
        if (!cancelled) setAnalyzing(false);
      }
    }
    poll();
    return () => { cancelled = true; };
  }, [incident]);

  if (!incident) {
    return <p style={{ color: '#8b8fa8' }}>No incident data.</p>;
  }

  const data = extra ? parseAnalysis({ ...incident, ...extra }) : parseAnalysis(incident);
  const rootCause = safeString(data.root_cause);

  if (analyzing && !rootCause) {
    return (
      <div style={{ backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12, padding: 20, textAlign: 'center' }}>
        <p style={{ color: '#8b8fa8', fontSize: 14 }}>AI is analyzing...</p>
      </div>
    );
  }

  if (!rootCause) {
    return (
      <div style={{ backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12, padding: 20 }}>
        <p style={{ color: '#8b8fa8', fontSize: 14 }}>No root cause analysis available yet.</p>
      </div>
    );
  }

  return (
    <div style={{ backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12, padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ color: '#e8eaf0', margin: 0, fontSize: 16 }}>Incident Analysis</h3>
        <span
          style={{
            backgroundColor: incident.source === 'RULE_ENGINE' ? '#3b82f6' : '#8b5cf6',
            color: '#fff',
            padding: '4px 10px',
            borderRadius: 6,
            fontSize: 11,
            fontWeight: 600,
          }}
        >
          {incident.source === 'RULE_ENGINE' ? 'Rule Engine' : 'AI Agent'}
        </span>
      </div>

      <ConfidenceProgress confidence={data.confidence} />

      <Section title="Summary" accent="#ef4444">
        <p style={{ color: '#e8eaf0', fontSize: 15, margin: 0, lineHeight: 1.5 }}>
          {safeString(data.summary, rootCause)}
        </p>
      </Section>

      <Section title="Root Cause" accent="#f59e0b">
        <p style={{ color: '#e8eaf0', fontSize: 16, fontWeight: 600, margin: 0 }}>{rootCause}</p>
      </Section>

      {data.affected_services?.length > 0 && (
        <Section title="Affected Services" accent="#8b5cf6">
          <p style={{ color: '#e8eaf0', margin: 0 }}>{data.affected_services.join(', ')}</p>
        </Section>
      )}

      <Section title="Debugging Steps (investigate)" accent="#3b82f6">
        <BulletList items={data.debug_steps} ordered />
      </Section>

      <Section title="Recommended Actions (remediate)" accent="#10b981">
        <BulletList items={data.recommended_actions} ordered />
      </Section>

      <Section title="Evidence" accent="#6b7280">
        <BulletList items={data.evidence} />
      </Section>
    </div>
  );
}
