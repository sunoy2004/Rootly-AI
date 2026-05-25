import React, { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { getMetricRange } from '../api/client';

const SERVICES = ['user-service', 'order-service', 'payment-service'];
const COLORS = ['#3b82f6', '#10b981', '#f59e0b']; // Blue, Green, Amber

function formatTime(timestamp) {
  const date = new Date(timestamp * 1000);
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

function ChartCard({ title, data, loading, valueFormatter, strokeWidth = 2.5 }) {
  const seriesByService = {};
  const timeSet = new Set();

  for (const point of data) {
    timeSet.add(point.time);
    if (!seriesByService[point.service]) {
      seriesByService[point.service] = {};
    }
    seriesByService[point.service][point.time] = point.value;
  }

  const times = Array.from(timeSet).sort((a, b) => a - b);
  const chartData = times.map((t) => {
    const row = { time: formatTime(t) };
    SERVICES.forEach((svc) => {
      row[svc] = seriesByService[svc]?.[t] !== undefined ? seriesByService[svc][t] : 0.0;
    });
    return row;
  });

  return (
    <div
      style={{
        background: 'linear-gradient(135deg, rgba(26, 29, 39, 0.6) 0%, rgba(20, 22, 30, 0.7) 100%)',
        backdropFilter: 'blur(8px)',
        border: '1px solid rgba(255, 255, 255, 0.05)',
        borderRadius: 16,
        padding: 20,
        marginBottom: 20,
        boxShadow: '0 4px 20px 0 rgba(0, 0, 0, 0.2)',
      }}
    >
      <h4 style={{ color: '#e8eaf0', margin: '0 0 16px 0', fontSize: 15, fontWeight: 600 }}>{title}</h4>
      {loading && chartData.length === 0 ? (
        <div style={{ color: '#8b8fa8', textAlign: 'center', padding: '60px 0', fontSize: 13 }}>
          Syncing metrics with Prometheus...
        </div>
      ) : chartData.length === 0 ? (
        <div style={{ color: '#8b8fa8', textAlign: 'center', padding: '60px 0', fontSize: 13 }}>
          0.00 (No metric activity. Run load simulator)
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData} margin={{ top: 5, right: 10, left: 15, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
            <XAxis
              dataKey="time"
              stroke="#8b8fa8"
              fontSize={10}
              tickLine={false}
              dy={10}
            />
            <YAxis 
              stroke="#8b8fa8" 
              fontSize={10} 
              tickLine={false} 
              dx={-5}
              tickFormatter={valueFormatter}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1e222b',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 8,
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
              }}
              labelStyle={{ color: '#e8eaf0', fontWeight: 600, fontSize: 12 }}
              itemStyle={{ fontSize: 12, padding: '2px 0' }}
              formatter={(value, name) => [valueFormatter(value), name]}
            />
            <Legend wrapperStyle={{ fontSize: 11, paddingTop: 10 }} />
            {SERVICES.map((svc, idx) => (
              <Line
                key={svc}
                type="monotone"
                dataKey={svc}
                stroke={COLORS[idx]}
                dot={false}
                strokeWidth={strokeWidth}
                activeDot={{ r: 4 }}
                animationDuration={300}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

export default function MetricsPanel() {
  const [errorRateData, setErrorRateData] = useState([]);
  const [p95Data, setP95Data] = useState([]);
  const [volumeData, setVolumeData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [rangeMinutes] = useState(10);

  useEffect(() => {
    let mounted = true;

    async function fetchData() {
      try {
        const [errors, p95, volume] = await Promise.all([
          getMetricRange(
            'sum(rate(http_requests_total{job=~"user-service|order-service|payment-service",status=~"(4xx|5xx|4..|5..)",handler!="/metrics"}[5m])) by (job)',
            rangeMinutes
          ),
          getMetricRange(
            'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job=~"user-service|order-service|payment-service",handler!="/metrics"}[5m])) by (le, job)) * 1000',
            rangeMinutes
          ),
          getMetricRange(
            'sum(rate(http_requests_total{job=~"user-service|order-service|payment-service",handler!="/metrics"}[5m])) by (job)',
            rangeMinutes
          ),
        ]);

        const cutoff = Math.floor(Date.now() / 1000) - rangeMinutes * 60;
        const trim = (points) => points.filter((p) => p.time >= cutoff);

        if (mounted) {
          setErrorRateData(trim(errors));
          setP95Data(trim(p95));
          setVolumeData(trim(volume));
          setLoading(false);
        }
      } catch (err) {
        console.error('Failed to fetch metrics:', err);
        if (mounted) setLoading(false);
      }
    }

    const start = setTimeout(fetchData, 2000);
    const interval = setInterval(fetchData, 30000);

    return () => {
      mounted = false;
      clearTimeout(start);
      clearInterval(interval);
    };
  }, [rangeMinutes]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
      <ChartCard 
        title="Error Rate (errors/sec) — last 10 min" 
        data={errorRateData} 
        loading={loading} 
        valueFormatter={(val) => `${val.toFixed(2)}/s`}
      />
      <ChartCard 
        title="Latency p95 (ms) — last 10 min" 
        data={p95Data} 
        loading={loading} 
        valueFormatter={(val) => `${val.toFixed(0)} ms`}
      />
      <ChartCard 
        title="Throughput (req/sec) — last 10 min" 
        data={volumeData} 
        loading={loading} 
        valueFormatter={(val) => `${val.toFixed(1)}/s`}
      />
    </div>
  );
}
