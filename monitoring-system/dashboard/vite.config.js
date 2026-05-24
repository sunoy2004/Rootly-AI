import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// API/WebSocket connect directly to incident-manager (see .env.development).
// Vite proxy is unreliable for WS on Windows + slow backends (ECONNRESET).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
  },
});
