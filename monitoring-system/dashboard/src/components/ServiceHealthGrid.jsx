import React, { useState, useEffect } from 'react';
import { getMetricInstant, getStats, isRequestAborted } from '../api/client';
import { incidentCountFromStats, safeNumber } from '../utils/safeRender';

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

function ServiceCard({ service, status, errorRate, p95Latency, incidentCount, lastUpdated }) {
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
          {(errorRate * 100).toFixed(2)}%
        </div>
      </div>

      <div style={{ marginBottom: 8 }}>
        <span style={{ color: '#8b8fa8', fontSize: 12 }}>p95 Latency</span>
        <div style={{ color: '#e8eaf0', fontSize: 20, fontWeight: 600 }}>
          {p95Latency.toFixed(0)} ms
        </div>
      </div>

      <div style={{ marginBottom: 8 }}>
        <span style={{ color: '#8b8fa8', fontSize: 12 }}>Open Incidents</span>
        <div style={{ color: '#e8eaf0', fontSize: 20, fontWeight: 600 }}>
          {incidentCount}
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
            const [errorRateResults, p95Results] = await Promise.all([
              getMetricInstant(
                `sum(rate(http_requests_total{job="${service}",status=~"5.."}[5m])) / sum(rate(http_requests_total{job="${service}"}[5m]))`,
                controller.signal
              ),
              getMetricInstant(
                `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job="${service}"}[5m])) by (le)) * 1000`,
                controller.signal
              ),
            ]);

            const errorRate = safeNumber(errorRateResults[0]?.value, 0);
            const p95Latency = safeNumber(p95Results[0]?.value, 0);
            const incidentCount = incidentCountFromStats(stats.by_service, service);

            return {
              service,
              errorRate,
              p95Latency,
              incidentCount,
              hasCritical: false,
              hasWarning: incidentCount > 0,
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

    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => {
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
          lastUpdated={new Date().toLocaleTimeString()}
        />
      ))}
    </div>
  );
}
