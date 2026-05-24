import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8013';
const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8013';

const PROMETHEUS_BASE = 'http://localhost:9090';
const AI_BASE = 'http://localhost:8008';

export const incidentAPI = axios.create({
  baseURL: API_BASE,
  timeout: 20000,
});

export const prometheusAPI = axios.create({
  baseURL: PROMETHEUS_BASE,
  timeout: 15000,
});

export const aiAPI = axios.create({
  baseURL: AI_BASE,
  timeout: 60000,
});

let authHeader = {};

export function isRequestAborted(err) {
  return (
    axios.isCancel(err) ||
    err?.code === 'ERR_CANCELED' ||
    err?.message === 'canceled' ||
    err?.name === 'CanceledError'
  );
}

export function setAuthHeader(header) {
  authHeader = header;
  incidentAPI.defaults.headers.common = {
    ...incidentAPI.defaults.headers.common,
    ...header,
  };
}

incidentAPI.interceptors.request.use((config) => {
  if (authHeader.Authorization) {
    config.headers.Authorization = authHeader.Authorization;
  }
  return config;
});

export async function login(username, password) {
  const response = await incidentAPI.post('/auth/login', {
    username,
    password,
  });
  return response.data;
}

export async function getIncidents(params = {}, signal) {
  const response = await incidentAPI.get('/incidents', { params, signal });
  return response.data;
}

export async function getIncident(id) {
  const response = await incidentAPI.get(`/incidents/${id}`);
  return response.data;
}

export async function updateIncident(id, data) {
  const response = await incidentAPI.patch(`/incidents/${id}`, data);
  return response.data;
}

export async function getStats(signal) {
  const response = await incidentAPI.get('/incidents/stats/summary', { signal });
  return response.data;
}

export async function triggerAIAnalysis(id) {
  const response = await aiAPI.get(`/analyze/${id}`);
  return response.data;
}

export async function getClusters(params = {}, signal) {
  const response = await incidentAPI.get('/clusters', { params, signal });
  return response.data;
}

export async function getAnomalies(params = {}, signal) {
  const response = await incidentAPI.get('/anomalies', { params, signal });
  return response.data;
}

function wsUrl(path) {
  return `${WS_BASE}${path}`;
}

export function connectWebSocket(path, { onMessage, onError, onOpen }) {
  let ws;
  let reconnectTimer;
  let closed = false;
  let backoff = 1000;

  function connect() {
    const url = wsUrl(path);
    ws = new WebSocket(url);

    ws.onopen = () => {
      backoff = 1000;
      onOpen?.(ws);
    };

    ws.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data), ws);
      } catch (e) {
        onError?.(e);
      }
    };

    ws.onerror = (e) => onError?.(e);

    ws.onclose = () => {
      if (!closed) {
        reconnectTimer = setTimeout(connect, backoff);
        backoff = Math.min(backoff * 2, 10000);
      }
    };
  }

  connect();

  return {
    send: (data) => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(data));
      }
    },
    close: () => {
      closed = true;
      clearTimeout(reconnectTimer);
      ws?.close();
    },
  };
}

export function connectLiveLogs({ service, level, search, onLogs, onError }) {
  const conn = connectWebSocket('/ws/logs', {
    onOpen: (ws) => {
      ws.send(JSON.stringify({ service, level: level || '', search: search || '' }));
    },
    onMessage: (data) => {
      if (data.type === 'logs') {
        onLogs(data.logs || []);
      }
    },
    onError,
  });

  return {
    sendFilters: () =>
      conn.send({ service, level: level || '', search: search || '' }),
    close: conn.close,
  };
}

export function connectLiveAnomalies({ onAnomaly, onError }) {
  const seen = new Set();
  return connectWebSocket('/ws/anomalies', {
    onMessage: (data) => {
      if (data.type === 'anomaly' && data.anomaly) {
        const id = `${data.anomaly.service}-${data.anomaly.metric}-${data.anomaly.timestamp}`;
        if (!seen.has(id)) {
          seen.add(id);
          onAnomaly(data.anomaly);
        }
      }
    },
    onError,
  });
}

export function connectLiveIncidents({ onIncident, onError }) {
  return connectWebSocket('/ws/incidents', {
    onMessage: (data) => {
      if (data.type === 'incident' && data.incident) {
        onIncident(data.incident);
      }
    },
    onError,
  });
}

export async function getLogs(params = {}, signal) {
  const response = await incidentAPI.get('/logs', { params, signal });
  return response.data;
}

export async function getServiceLogs(serviceName, params = {}, signal) {
  if (!serviceName || serviceName === 'all') {
    return getLogs(params, signal);
  }
  const response = await incidentAPI.get(`/services/${serviceName}/logs`, { params, signal });
  return response.data;
}

export async function getMetricRange(promql, startMinutesAgo = 30, stepSeconds = 60) {
  const end = Math.floor(Date.now() / 1000);
  const start = end - startMinutesAgo * 60;

  const response = await prometheusAPI.get('/api/v1/query_range', {
    params: { query: promql, start, end, step: stepSeconds },
  });

  const results = response.data?.data?.result || [];
  const points = [];
  for (const series of results) {
    for (const [ts, val] of series.values || []) {
      points.push({
        time: ts,
        value: parseFloat(val),
        service: series.metric?.job || 'unknown',
      });
    }
  }
  return points;
}

export async function getMetricInstant(promql, signal) {
  const response = await prometheusAPI.get('/api/v1/query', {
    params: { query: promql },
    signal,
  });
  const results = response.data?.data?.result || [];
  return results.map((r) => ({
    value: parseFloat(r.value?.[1] || 0),
    service: r.metric?.job || r.metric?.service || 'unknown',
    metric: r.metric,
  }));
}
