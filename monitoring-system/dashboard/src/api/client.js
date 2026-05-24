import axios from 'axios';

const INCIDENT_BASE = 'http://localhost:8013';
const PROMETHEUS_BASE = 'http://localhost:9090';
const AI_BASE = 'http://localhost:8014';

export const incidentAPI = axios.create({
  baseURL: INCIDENT_BASE,
});

export const prometheusAPI = axios.create({
  baseURL: PROMETHEUS_BASE,
});

export const aiAPI = axios.create({
  baseURL: AI_BASE,
});

let authHeader = {};

export function setAuthHeader(header) {
  authHeader = header;
  incidentAPI.defaults.headers.common = {
    ...incidentAPI.defaults.headers.common,
    ...header,
  };
  aiAPI.defaults.headers.common = {
    ...aiAPI.defaults.headers.common,
    ...header,
  };
}

incidentAPI.interceptors.request.use((config) => {
  if (authHeader.Authorization) {
    config.headers.Authorization = authHeader.Authorization;
  }
  return config;
});

aiAPI.interceptors.request.use((config) => {
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

export async function getIncidents(params = {}) {
  const response = await incidentAPI.get('/incidents', { params });
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

export async function getStats() {
  const response = await incidentAPI.get('/incidents/stats/summary');
  return response.data;
}

export async function triggerAIAnalysis(id) {
  const response = await aiAPI.get(`/analyze/${id}`);
  return response.data;
}

export async function getClusters(params = {}) {
  const response = await incidentAPI.get('/clusters', { params });
  return response.data;
}

export async function getServiceLogs(serviceName, params = {}) {
  const response = await incidentAPI.get(`/services/${serviceName}/logs`, { params });
  return response.data;
}

export async function getMetricRange(promql, startMinutesAgo = 30, stepSeconds = 60) {
  const end = Math.floor(Date.now() / 1000);
  const start = end - startMinutesAgo * 60;

  const response = await prometheusAPI.get('/api/v1/query_range', {
    params: {
      query: promql,
      start,
      end,
      step: stepSeconds,
    },
  });

  const results = response.data?.data?.result || [];

  const points = [];
  for (const series of results) {
    const values = series.values || [];
    for (const [ts, val] of values) {
      points.push({
        time: ts,
        value: parseFloat(val),
        service: series.metric?.job || series.metric?.service || 'unknown',
      });
    }
  }

  return points;
}

export async function getMetricInstant(promql) {
  const response = await prometheusAPI.get('/api/v1/query', {
    params: { query: promql },
  });

  const results = response.data?.data?.result || [];

  return results.map((r) => ({
    value: parseFloat(r.value?.[1] || 0),
    service: r.metric?.job || r.metric?.service || 'unknown',
    metric: r.metric,
  }));
}
