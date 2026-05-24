import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8013';

export function useBackendHealth(intervalMs = 10000) {
  const [healthy, setHealthy] = useState(null);

  useEffect(() => {
    let active = true;

    async function check() {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 4000);
        const res = await fetch(`${API_BASE}/health`, { signal: controller.signal });
        clearTimeout(timer);
        if (active) setHealthy(res.ok);
      } catch {
        if (active) setHealthy(false);
      }
    }

    check();
    const id = setInterval(check, intervalMs);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [intervalMs]);

  return healthy;
}
