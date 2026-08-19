import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Without this, Vite silently falls back to 5174+ when 5173 is taken
    // instead of failing - and scripts/run.ps1 health-checks a hardcoded
    // :5173 URL, so that fallback used to look like a startup timeout with
    // no indication of what actually went wrong. Failing fast here means
    // the real cause ("Port 5173 is in use") lands in frontend.err.log,
    // where the launcher's error page already looks for it.
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
