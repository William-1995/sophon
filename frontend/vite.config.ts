import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/** Dev proxy target port; must match DEFAULT_API_PORT in ../config/ unless overridden. */
const SOPHON_API_PORT = process.env.VITE_SOPHON_API_PORT || process.env.PORT || '8080'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': `http://127.0.0.1:${SOPHON_API_PORT}`,
    }
  }
})
