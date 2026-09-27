import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development, API and admin requests are proxied to Django so that the
// session and CSRF cookies are same-origin.
const backend = process.env.BACKEND_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 1600 },
  server: {
    proxy: {
      '/api': backend,
      '/admin': backend,
      '/static': backend,
    },
  },
})
