import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The backend may run locally (default) or on a remote VM. The Vite dev server
// proxies /ws (signaling) and /health to it, so the browser only ever talks to
// the local dev server and stays a secure context for getUserMedia.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendWs = env.VITE_BACKEND_WS_URL || "ws://localhost:8000";
  const backendHttp = env.VITE_BACKEND_HTTP_URL || "http://localhost:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        // Proxy the signaling WebSocket to the FastAPI backend.
        "/ws": {
          target: backendWs,
          ws: true,
        },
        "/health": {
          target: backendHttp,
          changeOrigin: true,
        },
      },
    },
  };
});
