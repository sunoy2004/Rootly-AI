import React, { useState, useEffect } from 'react';
import { getMetricInstant, getStats, isRequestAborted } from '../api/client';
import { safeNumber, serviceStatsFromSummary } from '../utils/safeRender';

const SERVICES = ['user-service', 'order-service', 'payment-service'];

const SERVICE_LABELS = {
  'user-service': 'User Service',
  'order-service': 'Order Service',
  'payment-service': 'Payment Service',
};

function getStatusColor(errorRate, hasCritical, hasWarning) {
  if (errorRate > 0.1 || hasCritical) return '#ef4444';
  if (errorRate > 0.01 || hasWarning) return '#f59e0b';
  return '#10b981';
}

function StatusDot({ color }) {
  return (
    <div
      style={{
        width: 16,
        height: 16,
        borderRadius: '50%',
        backgroundColor: color,
        boxShadow: `0 0 8px ${color}`,
      }}
    />
  );
}

function ServiceCard({ service, status, errorRate, p95Latency, incidentCount, criticalCount, lastUpdated }) {
  return (
    <div
      style={{
        backgroundColor: '#1a1d27',
        border: '1px solid #2a2d3a',
        borderRadius: 12,
        padding: 20,
        flex: 1,
        minWidth: 200,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h3 style={{ color: '#e8eaf0', margin: 0, fontSize: 16 }}>
          {SERVICE_LABELS[service] || service}
        </h3>
        <StatusDot color={status} />
      </div>

      <div style={{ marginBottom: 8 }}>
        <span style={{ color: '#8b8fa8', fontSize: 12 }}>Error Rate</span>
        <div style={{ color: '#e8eaf0', fontSize: 20, fontWeight: 600 }}>
          {(safeNumber(errorRate, 0) * 100).toFixed(2)}%
        </div>
        {criticalCount > 0 && (
          <div style={{ color: '#ef4444', fontSize: 11 }}>{criticalCount} critical incident(s)</div>
        )}
      </div>

      <div style={{ marginBottom: 8 }}>
        <span style={{ color: '#8b8fa8', fontSize: 12 }}>p95 Latency</span>
        <div style={{ color: '#e8eaf0', fontSize: 20, fontWeight: 600 }}>
          {safeNumber(p95Latency, 0).toFixed(0)} ms
        </div>
      </div>

      <div style={{ marginBottom: 8 }}>
        <span style={{ color: '#8b8fa8', fontSize: 12 }}>Open Incidents</span>
        <div style={{ color: '#e8eaf0', fontSize: 20, fontWeight: 600 }}>
          {safeNumber(incidentCount, 0)}
        </div>
      </div>

      <div style={{ color: '#8b8fa8', fontSize: 11, marginTop: 12 }}>
        Updated {lastUpdated}
      </div>
    </div>
  );
}

export default function ServiceHealthGrid() {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchData() {
      try {
        const stats = await getStats(controller.signal);

        const servicesData = await Promise.all(
          SERVICES.map(async (service) => {
            const svcStats = serviceStatsFromSummary(stats.by_service, service);

            let prom5xx = 0;
            let prom4xx = 0;
            try {
              const [r5xx, r4xx] = await Promise.all([
                getMetricInstant(
                  `sum(rate(http_requests_total{job="${service}",status=~"5.."}[5m])) / clamp_min(sum(rate(http_requests_total{job="${service}"}[5m])), 0.001)`,
                  controller.signal
                ),
                getMetricInstant(
                  `sum(rate(http_requests_total{job="${service}",status=~"4.."}[5m])) / clamp_min(sum(rate(http_requests_total{job="${service}"}[5m])), 0.001)`,
                  controller.signal
                ),
              ]);
              prom5xx = safeNumber(r5xx[0]?.value, 0);
              prom4xx = safeNumber(r4xx[0]?.value, 0);
            } catch {
              /* Prometheus optional */
            }

            const errorRate = Math.max(
              prom5xx + prom4xx,
              svcStats.error_rate_estimate,
              svcStats.critical > 0 ? 0.05 : 0
            );

            let p95Latency = svcStats.critical > 0 ? 120 : 0;
            try {
              const p95Results = await getMetricInstant(
                `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job="${service}"}[5m])) by (le)) * 1000`,
                controller.signal
              );
              p95Latency = safeNumber(p95Results[0]?.value, p95Latency);
            } catch {
              /* keep estimate */
            }

            return {
              service,
              errorRate,
              p95Latency,
              incidentCount: svcStats.open,
              criticalCount: svcStats.critical,
              hasCritical: svcStats.critical > 0,
              hasWarning: svcStats.open > 0,
            };
          })
        );

        if (!controller.signal.aborted) {
          setServices(servicesData);
          setLoading(false);
        }
      } catch (err) {
        if (!isRequestAborted(err)) {
          console.error('Failed to fetch service health:', err);
        }
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    const startDelay = setTimeout(fetchData, 0);
    const interval = setInterval(fetchData, 45000);
    return () => {
      clearTimeout(startDelay);
      controller.abort();
      clearInterval(interval);
    };
  }, []);

  if (loading) {
    return <div style={{ color: '#8b8fa8', padding: 20 }}>Loading service health...</div>;
  }

  return (
    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
      {services.map((s) => (
        <ServiceCard
          key={s.service}
          service={s.service}
          status={getStatusColor(s.errorRate, s.hasCritical, s.hasWarning)}
          errorRate={s.errorRate}
          p95Latency={s.p95Latency}
          incidentCount={s.incidentCount}
          criticalCount={s.criticalCount}
          lastUpdated={new Date().toLocaleTimeString()}
        />
      ))}
    </div>
  );
}
