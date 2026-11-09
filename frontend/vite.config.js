import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the frontend calls `/api/*`, which is proxied to FastAPI
// (with the `/api` prefix stripped) so no CORS setup is needed.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
