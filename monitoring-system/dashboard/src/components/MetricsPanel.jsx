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
const COLORS = ['#3b82f6', '#10b981', '#f59e0b'];

function formatTime(timestamp) {
  const date = new Date(timestamp * 1000);
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

function ChartCard({ title, data, loading }) {
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
    SERVICES.forEach((svc, idx) => {
      const serviceName = svc;
      row[serviceName] = seriesByService[serviceName]?.[t] ?? null;
    });
    return row;
  });

  return (
    <div
      style={{
        backgroundColor: '#1a1d27',
        border: '1px solid #2a2d3a',
        borderRadius: 12,
        padding: 16,
        marginBottom: 16,
      }}
    >
      <h4 style={{ color: '#e8eaf0', margin: '0 0 16px 0' }}>{title}</h4>
      {loading ? (
        <div style={{ color: '#8b8fa8', textAlign: 'center', padding: 40 }}>
          Loading...
        </div>
      ) : chartData.length === 0 ? (
        <div style={{ color: '#8b8fa8', textAlign: 'center', padding: 40 }}>
          No data available
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
            <XAxis
              dataKey="time"
              stroke="#8b8fa8"
              fontSize={11}
              tickLine={false}
            />
            <YAxis stroke="#8b8fa8" fontSize={11} tickLine={false} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1a1d27',
                border: '1px solid #2a2d3a',
                borderRadius: 8,
              }}
              labelStyle={{ color: '#e8eaf0' }}
            />
            <Legend />
            {SERVICES.map((svc, idx) => (
              <Line
                key={svc}
                type="monotone"
                dataKey={svc}
                stroke={COLORS[idx]}
                dot={false}
                strokeWidth={2}
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

  useEffect(() => {
    let mounted = true;

    async function fetchData() {
      try {
        const [errors, p95, volume] = await Promise.all([
          getMetricRange(
            'sum(rate(http_requests_total{job=~"user-service|order-service|payment-service",status=~"5.."}[5m])) by (job)'
          ),
          getMetricRange(
            'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job=~"user-service|order-service|payment-service"}[5m])) by (le, job)) * 1000'
          ),
          getMetricRange(
            'sum(rate(http_requests_total{job=~"user-service|order-service|payment-service"}[5m])) by (job)'
          ),
        ]);

        if (mounted) {
          setErrorRateData(errors);
          setP95Data(p95);
          setVolumeData(volume);
          setLoading(false);
        }
      } catch (err) {
        console.error('Failed to fetch metrics:', err);
        if (mounted) setLoading(false);
      }
    }

    fetchData();
    const interval = setInterval(fetchData, 30000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div>
      <ChartCard title="Error Rate (errors/sec)" data={errorRateData} loading={loading} />
      <ChartCard title="p95 Latency (ms)" data={p95Data} loading={loading} />
      <ChartCard title="Request Volume (req/sec)" data={volumeData} loading={loading} />
    </div>
  );
}
