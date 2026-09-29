import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    // Pass VITE_MOCK_API through to the client bundle
    define: {
      __MOCK_API__: JSON.stringify(env.VITE_MOCK_API === 'true'),
    },
    server: {
      port: 5173,
      // Proxy /api/* directly to FastAPI — no path rewrite.
      // FastAPI registers routes at /api/status, /api/organize, etc.
      // so the path must be passed through unchanged.
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          // No rewrite: /api/organize → http://localhost:8000/api/organize ✓
        },
      },
    },
  }
})
