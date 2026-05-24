/** Coerce API values to safe React children */
export function safeNumber(val, fallback = 0) {
  if (typeof val === 'number' && Number.isFinite(val)) return val;
  if (typeof val === 'string' && val !== '' && !Number.isNaN(Number(val))) {
    return Number(val);
  }
  return fallback;
}

export function safeString(val, fallback = '') {
  if (val === null || val === undefined) return fallback;
  if (typeof val === 'string') return val;
  if (typeof val === 'number' || typeof val === 'boolean') return String(val);
  try {
    return JSON.stringify(val);
  } catch {
    return fallback;
  }
}

export function safeStringList(items) {
  if (!Array.isArray(items)) return [];
  return items
    .map((item) => safeString(item))
    .filter((s) => s.length > 0);
}

export function incidentCountFromStats(byService, service) {
  const val = byService?.[service];
  if (typeof val === 'number') return val;
  if (val && typeof val === 'object' && typeof val.count === 'number') return val.count;
  return 0;
}

export function dedupeLists(debugSteps = [], recommendedActions = []) {
  const debug = safeStringList(debugSteps);
  const actions = safeStringList(recommendedActions);
  const actionSet = new Set(actions.map((s) => s.toLowerCase()));
  const filteredDebug = debug.filter((s) => !actionSet.has(s.toLowerCase()));
  return { debug_steps: filteredDebug, recommended_actions: actions };
}
